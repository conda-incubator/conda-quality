# SPDX-License-Identifier: BSD-3-Clause
"""Global fixtures for the conda E2E suite."""

from __future__ import annotations

import logging
import os
import shutil
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pytest_html import extras as html_extras
from pytest_metadata.plugin import metadata_key

from conda_e2e.parsers.info import CondaInfo
from conda_e2e.runner import CliRunner, observe_results
from conda_e2e.shells import CondaShellRunner, Shell
from conda_e2e.update import (
    CANARY_DEV_CHANNEL,
    CondaE2EUpdateError,
    update_base_conda,
)
from conda_e2e.utils import IS_WINDOWS, env_prefix, unique_env_name

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from conda_e2e.result import CommandResult

pytest.register_assert_rewrite("install_asserts")
pytest.register_assert_rewrite("info_asserts", "package_helpers")
pytest.register_assert_rewrite("help_command_helpers")

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
    appdata = home / "AppData" / "Roaming"
    pkgs_dir = tmp_conda_root / "pkgs"
    envs_dir = tmp_conda_root / "envs"
    condarc = home / ".condarc"
    for directory in (home, pkgs_dir, envs_dir, appdata):
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
            "APPDATA": str(appdata),  # Windows appdata
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


# --------------------------------------------------------------------------
# HTML report (pytest-html): the Environment table, plus each test's conda
# commands attached to its row.
# --------------------------------------------------------------------------

# Invocations as ``(label, body)``, rendered when recorded so whole conda
# outputs aren't held all session, plus how many are already in the report.
_CLI_ENTRIES_KEY = pytest.StashKey[list[tuple[str, str]]]()
_CLI_ATTACHED_KEY = pytest.StashKey[int]()

# Per stream, per command: stops one noisy command bloating the HTML file.
_MAX_STREAM_CHARS = 8_000

_MAX_LABEL_CHARS = 60

_SHELL_EXECUTABLES = frozenset(shell.value for shell in Shell)


def pytest_configure(config: pytest.Config) -> None:
    """Record what this run asked for in the report's Environment table.

    The resolved conda facts are added later, by ``report_conda_metadata``.
    """
    metadata = config.stash.setdefault(metadata_key, {})
    # pytest-metadata's ``Python`` is the one running pytest, which is not the
    # conda under test's; relabel it so the two Python rows can't be confused.
    if "Python" in metadata:
        metadata["Harness Python"] = metadata.pop("Python")
    # Capitalised to match pytest-metadata's own rows in the same table.
    metadata.update(
        {
            "Conda channel": config.getoption("--conda-channel"),
            "Conda version requested": config.getoption("--conda-version") or "(no update)",
        }
    )


@pytest.fixture(scope="session", autouse=True)
def report_conda_metadata(
    request: pytest.FixtureRequest,
    update_conda: None,  # noqa: ARG001 - ordering only: report the post-update conda
) -> None:
    """Add the resolved conda facts to the report's Environment table.

    ``Conda base Python`` is not pytest-metadata's ``Python``: that one is the
    harness's, identical on every job, while the matrix varies this one.

    Rows added this late reach the table only because pytest-html holds a
    reference to the metadata dict; under pytest-xdist they would be lost.
    """
    metadata = request.config.stash[metadata_key]
    try:
        # Resolved inside the try rather than as a parameter: pytest resolves
        # parameters before the body, so a missing conda would error every test.
        conda_exe: str = request.getfixturevalue("conda_exe")
        # The host conda, not the per-test sandbox, minus inherited ``CONDA_*``
        # so an outer activation can't skew what it reports.
        runner = CliRunner(executable=conda_exe, environ=_env_without_conda_vars())
        info = CondaInfo.from_json(runner("info", "--json"))
    # Narrow on purpose: an absent, unreadable or changed conda must not sink
    # the run, but a bug in the lines below should be loud.
    except (ValueError, KeyError, OSError, pytest.fail.Exception) as exc:
        logger.warning("could not record conda metadata for the report: %r", exc)
        return
    metadata["Conda under test"] = conda_exe
    metadata["Conda version"] = info.conda_version
    metadata["Conda base Python"] = info.python_version
    metadata["Conda platform"] = info.platform


@pytest.fixture(autouse=True)
def record_cli_calls(request: pytest.FixtureRequest) -> Iterator[None]:
    """Record this test's CLI invocations for its row in the report.

    Records every command the test runs, including those issued through
    ``conda_shell``, which uses its own ``CliRunner``. Commands from the test's
    other fixtures are recorded too: pytest sets autouse fixtures up first and
    tears them down last, so this one stays subscribed through their setup and
    teardown. Session-scoped fixtures run earlier and are not recorded.
    """
    entries: list[tuple[str, str]] = []
    request.node.stash[_CLI_ENTRIES_KEY] = entries

    def record(result: CommandResult) -> None:
        entries.append((_cli_label(result), result.describe(max_stream_chars=_MAX_STREAM_CHARS)))

    with observe_results(record):
        yield


def _cli_label(result: CommandResult) -> str:
    """Return a short label naming what one invocation ran."""
    argv = result.cmd[1:]
    if argv:
        text = " ".join(argv)
        is_shell = Path(result.cmd[0]).stem.lower() in _SHELL_EXECUTABLES
    else:
        # No argv to join means ``run_raw``, which only the shell runner uses.
        text = result.cmd[0]
        is_shell = True
    # A shell invocation buries the real command in hook boilerplate.
    if is_shell and (conda_at := text.rfind("conda ")) > 0:
        text = text[conda_at:]
    return text if len(text) <= _MAX_LABEL_CHARS else f"{text[: _MAX_LABEL_CHARS - 1]}…"


def _cli_extras(entries: list[tuple[str, str]], start: int = 1) -> list[dict[str, Any]]:
    """Turn recorded invocations into report content, one block per command.

    Blocks start collapsed because a failed test's traceback already shows the failing command.

    Args:
        entries: ``(label, body)`` pairs, already rendered.
        start: Number to label the first one with, so numbering stays
            continuous across a test's setup, call and teardown phases.

    """
    extras = []
    for number, (label, body) in enumerate(entries, start=start):
        summary = escape(f"{number}. {label}")
        block = f"<details><summary>{summary}</summary><pre>{escape(body)}</pre></details>"
        extras.append(html_extras.html(block))
    return extras


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Attach the test's recorded CLI output to its report row."""
    report = yield
    entries = item.stash.get(_CLI_ENTRIES_KEY, [])
    attached = item.stash.get(_CLI_ATTACHED_KEY, 0)
    # Attach only what this phase added: pytest-html pools a test's extras
    # across phases, so re-sending earlier commands would list them twice.
    if new_entries := entries[attached:]:
        item.stash[_CLI_ATTACHED_KEY] = len(entries)
        report.extras = [
            *getattr(report, "extras", []),
            *_cli_extras(new_entries, start=attached + 1),
        ]
    return report
