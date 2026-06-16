# SPDX-License-Identifier: BSD-3-Clause
"""Global fixtures for the conda E2E suite."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from conda_e2e.runner import CliRunner
from conda_e2e.shells import Shell, ShellRunner
from conda_e2e.utils import IS_WINDOWS

# Shells we attempt to test on the current OS. Unavailable ones are skipped.
_CANDIDATE_SHELLS = (
    (Shell.CMD, Shell.WINDOWS_POWERSHELL, Shell.POWERSHELL)
    if IS_WINDOWS
    else (Shell.BASH, Shell.ZSH, Shell.SH)
)


@pytest.fixture(scope="session")
def conda_exe() -> str:
    """Resolve the conda under test once, failing fast if it is missing.

    Provisioning conda is out of scope (handled outside the suite); this only
    checks it is reachable, turning a missing conda into one clear error.
    """
    candidate = os.environ.get("CONDA_E2E_CONDA", "conda")
    resolved = shutil.which(candidate)
    if resolved is None:
        pytest.fail(
            f"conda executable {candidate!r} not found on PATH or not executable. "
            "Ensure your pre-test setup installed a conda, or set CONDA_E2E_CONDA "
            "to its path.",
            pytrace=False,
        )
    return resolved


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
    create -- pytest's ``tmp_path`` teardown wipes the whole sandbox, registry
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
    env = {k: v for k, v in os.environ.items() if not k.startswith("CONDA_")}
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
def envs_dir(isolated_env_vars: dict[str, str]) -> Path:
    """Return the directory where ``conda create -n <name>`` places environments."""
    return Path(isolated_env_vars["CONDA_ENVS_DIRS"])


@pytest.fixture
def non_interactive_env_vars(isolated_env_vars: dict[str, str]) -> dict[str, str]:
    """``isolated_env_vars`` plus auto-confirm and channel-ToS auto-accept.

    The shared default for exercising conda non-interactively, used by both the
    ``conda`` and ``shell`` fixtures. ``conda_no_tos`` deliberately omits the ToS
    auto-accept to exercise that gate.
    """
    return {
        **isolated_env_vars,
        "CONDA_ALWAYS_YES": "yes",
        "CONDA_PLUGINS_AUTO_ACCEPT_TOS": "yes",
    }


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
    """Like ``conda`` but with ToS auto-accept *absent*, for testing the gate.

    The CI environment variable is removed because the ToS plugin auto-accepts
    the terms when it is set.
    """
    env = {k: v for k, v in isolated_env_vars.items() if k != "CI"}
    env["CONDA_ALWAYS_YES"] = "yes"
    return CliRunner(executable=conda_exe, environ=env)


@pytest.fixture(params=_CANDIDATE_SHELLS, ids=lambda s: s.value)
def shell(request: pytest.FixtureRequest, non_interactive_env_vars: dict[str, str]) -> ShellRunner:
    """Return a ``ShellRunner`` for each shell available on this OS (others skipped).

    For shell-dependent conda behaviour (activate / deactivate / init / hook);
    shell-agnostic commands (incl. ``conda run``) use the ``conda`` fixture. Build
    the activation script with ``conda_activate_script`` -- it differs per shell::

        def test_activate(shell, conda_exe):
            script = conda_activate_script(
                shell.shell, "base", "conda info --json", conda_exe=conda_exe
            )
            shell(script).assert_ok()
    """
    shell_kind: Shell = request.param
    if not shell_kind.is_available():
        pytest.skip(f"{shell_kind.value} not available on this platform")
    return ShellRunner(shell=shell_kind, environ=non_interactive_env_vars)
