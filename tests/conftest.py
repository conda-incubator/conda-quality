# SPDX-License-Identifier: BSD-3-Clause
"""Global fixtures for the conda E2E suite."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pytest

from conda_e2e.runner import CliRunner
from conda_e2e.shells import CondaShellRunner, Shell
from conda_e2e.update import (
    CANARY_DEV_CHANNEL,
    CondaE2EUpdateError,
    update_base_conda,
)
from conda_e2e.utils import IS_WINDOWS, env_prefix, unique_env_name

logger = logging.getLogger(__name__)

# Shells we attempt to test on the current OS. Unavailable ones are skipped.
_CANDIDATE_SHELLS = (
    (Shell.CMD, Shell.WINDOWS_POWERSHELL, Shell.POWERSHELL)
    if IS_WINDOWS
    else (Shell.SH, Shell.BASH, Shell.ZSH, Shell.POWERSHELL)  # pwsh is cross-platform
)

# Env vars that make conda run non-interactively: auto-confirm prompts and
# auto-accept channel ToS.
AUTO_CONFIRM_ENV = {
    "CONDA_ALWAYS_YES": "yes",
    "CONDA_PLUGINS_AUTO_ACCEPT_TOS": "yes",
}


def _env_without_conda_vars() -> dict[str, str]:
    """Return the current environment with all ``CONDA_*`` variables removed."""
    return {k: v for k, v in os.environ.items() if not k.startswith("CONDA_")}


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register conda-selection options; each defaults from its ``CONDA_E2E_*`` env var."""
    parser.addoption(
        "--conda",
        default=os.environ.get("CONDA_E2E_CONDA", "conda"),
        help="conda under test: a name on PATH or a path (default: $CONDA_E2E_CONDA or 'conda').",
    )
    parser.addoption(
        "--conda-version",
        default=os.environ.get("CONDA_E2E_CONDA_VERSION"),
        help=(
            "If set, update base conda to this before the suite: 'latest' or a "
            "version like '26.3.1'. Unset (default): no update."
        ),
    )
    parser.addoption(
        "--conda-channel",
        default=os.environ.get("CONDA_E2E_CONDA_CHANNEL", CANARY_DEV_CHANNEL),
        help=f"Channel/label to install conda from (default: {CANARY_DEV_CHANNEL}).",
    )


@pytest.fixture(scope="session", autouse=True)
def update_conda(request: pytest.FixtureRequest) -> None:
    """Update base conda to ``--conda-version`` once before the suite, if requested.

    A no-op when no version is set (the default). ``conda_exe`` is resolved lazily
    so this autouse fixture doesn't force a real conda on every run.
    Mutates the *real* ``base`` env, so it deliberately runs against the host
    environment (not the per-test sandbox) plus only the auto-confirm/ToS-accept vars.
    """
    version = request.config.getoption("--conda-version")
    if not version:
        return
    logger.info("Updating conda to %s ...", version)
    conda_exe = request.getfixturevalue("conda_exe")
    channel = request.config.getoption("--conda-channel")
    # Strip inherited CONDA_* (e.g. pixi's CONDA_PREFIX under `pixi run`) so the base
    # update isn't skewed by an outer activation.
    clean_env = _env_without_conda_vars()
    runner = CliRunner(executable=conda_exe, environ={**clean_env, **AUTO_CONFIRM_ENV})
    try:
        update_base_conda(runner, version, channel)
    except CondaE2EUpdateError as exc:
        pytest.exit(f"conda update failed:\n{exc}", returncode=1)


@pytest.fixture(scope="session")
def conda_exe(request: pytest.FixtureRequest) -> str:
    """Resolve the conda under test once, failing fast if it is missing.

    Reads the ``--conda`` option (default ``$CONDA_E2E_CONDA`` or ``conda``).
    Only checks reachability, turning a missing conda into one clear error.
    """
    candidate = request.config.getoption("--conda")
    resolved = shutil.which(candidate)
    if resolved is None:
        pytest.fail(
            f"conda executable {candidate!r} not found on PATH or not executable. "
            "Ensure your pre-test setup installed a conda, or pass --conda / set "
            "CONDA_E2E_CONDA to its path.",
            pytrace=False,
        )
    return resolved


@pytest.fixture(scope="session")
def install_root(conda_exe: str) -> Path:
    """Return the root prefix containing the conda executable under test."""
    return Path(conda_exe).resolve().parent.parent


@pytest.fixture
def tmp_conda_root(tmp_path: Path) -> Path:
    """Return a fresh per-test tmp directory for the sandboxed conda state."""
    root = tmp_path / "conda"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def isolated_env_vars(tmp_conda_root: Path) -> dict[str, str]:
    """Return env vars that sandbox conda's state under ``tmp_conda_root``.

    Inherits the host environment minus every ``CONDA_*`` var, then redirects
    conda's locations and ``HOME`` into the tmp dir. Redirects *locations*, not
    behaviour.

    Because ``HOME`` (hence ``~/.conda/environments.txt``), the envs dir, and the
    pkgs cache all live under ``tmp_path``, tests need not remove envs they
    create: pytest's ``tmp_path`` teardown wipes the whole sandbox, registry
    entry included. Use ``conda env remove`` only when removal is the behaviour
    under test, not for cleanup.
    """
    home = tmp_conda_root / "home"
    pkgs_dir = tmp_conda_root / "pkgs"
    envs_dir = tmp_conda_root / "envs"
    condarc = home / ".condarc"
    for directory in (home, pkgs_dir, envs_dir):
        directory.mkdir(parents=True, exist_ok=True)
    condarc.touch(exist_ok=True)

    # Inherit everything except conda's own vars; keep the one selecting which
    # conda is under test.
    env = _env_without_conda_vars()
    if "CONDA_E2E_CONDA" in os.environ:
        env["CONDA_E2E_CONDA"] = os.environ["CONDA_E2E_CONDA"]
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),  # Windows home
            "CONDA_PKGS_DIRS": str(pkgs_dir),
            "CONDA_ENVS_DIRS": str(envs_dir),
            "CONDARC": str(condarc),
            # notices are network-fetched and non-deterministic; silence them
            "CONDA_NOTICES": "false",
        }
    )
    return env


@pytest.fixture
def cache_dir(isolated_env_vars: dict[str, str]) -> Path:
    """Return the directory where conda stores its package cache."""
    return Path(isolated_env_vars["CONDA_PKGS_DIRS"])


@pytest.fixture
def envs_dir(isolated_env_vars: dict[str, str]) -> Path:
    """Return the directory where ``conda create -n <name>`` places environments."""
    return Path(isolated_env_vars["CONDA_ENVS_DIRS"])


@pytest.fixture
def empty_env(conda: CliRunner, envs_dir: Path) -> tuple[str, Path]:
    """Create an empty conda environment and return its (name, path)."""
    env_name = unique_env_name()
    conda("create", "-n", env_name).assert_ok()
    return env_name, env_prefix(envs_dir, env_name)


@pytest.fixture
def condarc(isolated_env_vars: dict[str, str]) -> Path:
    """Path to the sandbox user .condarc."""
    return Path(isolated_env_vars["CONDARC"])


@pytest.fixture
def non_interactive_env_vars(isolated_env_vars: dict[str, str]) -> dict[str, str]:
    """``isolated_env_vars`` plus auto-confirm and channel-ToS auto-accept.

    The shared default for exercising conda non-interactively, used by both the
    ``conda`` and ``conda_shell`` fixtures. ``conda_no_tos`` deliberately omits
    the ToS auto-accept to exercise that gate.
    """
    return {**isolated_env_vars, **AUTO_CONFIRM_ENV}


@pytest.fixture
def conda(conda_exe: str, non_interactive_env_vars: dict[str, str]) -> CliRunner:
    """Return a runner for the conda under test: sandboxed, non-interactive, ToS-accepted.

    The default for exercising conda commands. It auto-confirms prompts
    (``CONDA_ALWAYS_YES``) and accepts channel ToS, so commands need no ``--yes``.
    Use ``conda_no_tos`` for the ToS gate; override ``CONDA_ALWAYS_YES`` per call
    to test the confirmation prompt.
    """
    return CliRunner(executable=conda_exe, environ=non_interactive_env_vars)


@pytest.fixture
def conda_no_tos(conda_exe: str, isolated_env_vars: dict[str, str]) -> CliRunner:
    """Like ``conda`` but with ToS auto-accept disabled, to exercise the gate.

    The ToS plugin auto-accepts when it detects CI, and detection checks many
    signals (``CI``, ``GITHUB_ACTIONS``, …), so removing ``CI`` alone isn't enough
    on GitHub Actions and thus setting ``CI=false``.
    """
    env = {**isolated_env_vars, "CI": "false", "CONDA_ALWAYS_YES": "yes"}
    return CliRunner(executable=conda_exe, environ=env)


@pytest.fixture(params=_CANDIDATE_SHELLS, ids=lambda s: s.value)
def conda_shell(
    request: pytest.FixtureRequest,
    conda_exe: str,
    non_interactive_env_vars: dict[str, str],
) -> CondaShellRunner:
    """Return a ``CondaShellRunner`` for each shell available on this OS (others skipped).

    For shell-dependent conda behaviour (activate / deactivate / init / hook);
    shell-agnostic commands (incl. ``conda run``) use the ``conda`` fixture. Use
    ``run_in_activated_env`` to activate an env and run commands in it::

        def test_activate(conda_shell):
            conda_shell.run_in_activated_env("base", "conda info --json").assert_ok()
    """
    shell_kind: Shell = request.param
    if not shell_kind.is_available():
        pytest.skip(f"{shell_kind.value} not available on this platform")
    return CondaShellRunner(shell=shell_kind, environ=non_interactive_env_vars, conda_exe=conda_exe)
