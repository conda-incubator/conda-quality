# SPDX-License-Identifier: BSD-3-Clause
"""Global fixtures for the conda E2E suite."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from conda_e2e.runner import CliRunner
from conda_e2e.shells import CondaShellRunner, Shell
from conda_e2e.update import (
    CANARY_DEV_CHANNEL,
    CondaE2EUpdateError,
    update_base_conda,
)
from conda_e2e.utils import IS_WINDOWS, env_prefix, env_without_conda_vars, unique_env_name

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

pytest_plugins = ["plugins.html_report"]

pytest.register_assert_rewrite(
    "create_asserts",
    "info_asserts",
    "install_asserts",
    "package_helpers",
    "search_asserts",
    "shared.package_asserts",
)

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
    parser.addoption(
        "--pkgs-cache",
        choices=("shared", "isolated"),
        default=os.environ.get("CONDA_E2E_PKGS_CACHE", "shared"),
        help=(
            "Package cache for tests: 'shared' (default) gives all tests one cache (one per "
            "pytest-xdist worker), the way conda works for regular users. 'isolated' gives "
            "every test its own empty cache, so every test downloads its packages again."
        ),
    )


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    """Update base conda to ``--conda-version`` once before any test runs, if requested.

    A no-op when no version is set (the default), when only collecting tests, or
    when conda isn't found (the ``conda_exe`` fixture then reports it in every test).
    Runs in the main pytest process only: with pytest-xdist it finishes before the
    workers start, and the workers skip it.
    Mutates the *real* ``base`` env, so it deliberately runs against the host
    environment (not the per-test sandbox) plus only the auto-confirm/ToS-accept vars.
    """
    config = session.config
    version = config.getoption("--conda-version")
    if not version or config.option.collectonly or hasattr(config, "workerinput"):
        return
    conda_exe = shutil.which(config.getoption("--conda"))
    if conda_exe is None:
        return
    logger.info("Updating conda to %s ...", version)
    channel = config.getoption("--conda-channel")
    # Strip inherited CONDA_* (e.g. pixi's CONDA_PREFIX under `pixi run`) so the base
    # update isn't skewed by an outer activation.
    clean_env = env_without_conda_vars()
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
def conda_version(conda_exe: str) -> str:
    """Return the version reported by the selected conda executable."""
    result = CliRunner(executable=conda_exe)("--version").assert_ok()
    return result.stdout.strip().removeprefix("conda ").strip()


@pytest.fixture
def tmp_conda_root(tmp_path: Path) -> Path:
    """Return a fresh per-test tmp directory for the sandboxed conda state."""
    root = tmp_path / "conda"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="session")
def shared_pkgs_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return a package cache directory shared by all tests in the session.

    conda then downloads each package and channel index once per session instead
    of once per test. With pytest-xdist every worker runs its own session, so it gets
    its own cache. That's required: conda locks only parts of its package cache, so
    two conda processes using one cache at once can break it.
    """
    return tmp_path_factory.mktemp("pkgs")


def _uses_shared_pkgs_cache(request: pytest.FixtureRequest) -> bool:
    """Return whether the test uses the shared package cache instead of its own."""
    return (
        request.config.getoption("--pkgs-cache") == "shared"
        and request.node.get_closest_marker("isolated_pkgs_cache") is None
    )


@pytest.fixture
def isolated_env_vars(
    request: pytest.FixtureRequest, tmp_conda_root: Path, shared_pkgs_dir: Path
) -> dict[str, str]:
    """Return env vars that sandbox conda's state under ``tmp_conda_root``.

    Inherits the host environment minus every ``CONDA_*`` var, then redirects
    conda's locations and ``HOME`` into the tmp dir. Redirects *locations*, not
    behaviour.

    Because ``HOME`` (hence ``~/.conda/environments.txt``) and the envs dir live
    under ``tmp_path``, tests need not remove envs they create: pytest's
    ``tmp_path`` teardown wipes the whole sandbox, registry entry included. Use
    ``conda env remove`` only when removal is the behaviour under test, not for
    cleanup.

    The package cache is ``shared_pkgs_dir``, shared by all tests. A test marked
    ``isolated_pkgs_cache``, or every test when run with ``--pkgs-cache=isolated``,
    gets its own empty cache under ``tmp_conda_root`` instead.
    """
    home = tmp_conda_root / "home"
    appdata = home / "AppData" / "Roaming"
    pkgs_dir = shared_pkgs_dir if _uses_shared_pkgs_cache(request) else tmp_conda_root / "pkgs"
    envs_dir = tmp_conda_root / "envs"
    condarc = home / ".condarc"
    for directory in (home, pkgs_dir, envs_dir, appdata):
        directory.mkdir(parents=True, exist_ok=True)
    condarc.touch(exist_ok=True)

    # Inherit everything except conda's own vars; keep the one selecting which
    # conda is under test.
    env = env_without_conda_vars()
    if "CONDA_E2E_CONDA" in os.environ:
        env["CONDA_E2E_CONDA"] = os.environ["CONDA_E2E_CONDA"]
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),  # Windows home
            "APPDATA": str(appdata),  # Windows appdata
            "XDG_CACHE_HOME": str(home / ".cache"),  # Linux user cache, replaces any host value
            "CONDA_PKGS_DIRS": str(pkgs_dir),
            "CONDA_ENVS_DIRS": str(envs_dir),
            "CONDARC": str(condarc),
            # notices are network-fetched and non-deterministic; silence them
            "CONDA_NUMBER_CHANNEL_NOTICES": "0",
        }
    )
    return env


@pytest.fixture
def cache_dir(request: pytest.FixtureRequest, isolated_env_vars: dict[str, str]) -> Path:
    """Return the directory where conda stores this test's package cache.

    Only for tests marked ``isolated_pkgs_cache``. The shared cache also holds the
    packages that earlier tests downloaded, so a test can't assert on its contents.
    """
    if request.node.get_closest_marker("isolated_pkgs_cache") is None:
        pytest.fail(
            "tests that inspect the package cache need @pytest.mark.isolated_pkgs_cache",
            pytrace=False,
        )
    return Path(isolated_env_vars["CONDA_PKGS_DIRS"])


@pytest.fixture
def envs_dir(isolated_env_vars: dict[str, str]) -> Path:
    """Return the directory where ``conda create -n <name>`` places environments."""
    return Path(isolated_env_vars["CONDA_ENVS_DIRS"])


@pytest.fixture
def make_env(conda: CliRunner, envs_dir: Path) -> Callable[[], tuple[str, Path]]:
    """Return a factory creating an empty env, each call returning its (name, path)."""

    def _make_env() -> tuple[str, Path]:
        env_name = unique_env_name()
        # The env has no packages, so conda needs nothing from the channels. Create it
        # offline, so tests that only need an empty env don't use the network at all.
        conda("create", "-n", env_name, extra_env={"CONDA_OFFLINE": "true"}).assert_ok()
        return env_name, env_prefix(envs_dir, env_name)

    return _make_env


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
