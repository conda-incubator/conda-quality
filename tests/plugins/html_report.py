# SPDX-License-Identifier: BSD-3-Clause
"""pytest plugin: adds conda details and each test's conda commands to the HTML report.

Loaded by ``tests/conftest.py`` through ``pytest_plugins``.
"""

from __future__ import annotations

import logging
import re
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pytest_html import extras as html_extras
from pytest_metadata.plugin import metadata_key

from conda_e2e.parsers.info import CondaInfo
from conda_e2e.runner import CliRunner, observe_results
from conda_e2e.shells import Shell
from conda_e2e.utils import env_without_conda_vars

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from conda_e2e.result import CommandResult

logger = logging.getLogger(__name__)

# Where each test keeps its command blocks until they're attached to its report row.
_CLI_EXTRAS_KEY = pytest.StashKey[list[dict[str, Any]]]()

# Max characters kept per stdout/stderr, so one noisy command can't bloat the HTML file.
_MAX_STREAM_CHARS = 8_000

# Max heading length. The full command is always in the expanded block.
_MAX_LABEL_CHARS = 100

# Executable names of the shells that conda_shell runs commands through.
_SHELL_EXECUTABLES = frozenset(shell.value for shell in Shell)


def pytest_configure(config: pytest.Config) -> None:
    """Add the requested conda channel and version to the report's Environment table.

    The installed conda's details are added later, by ``report_conda_metadata``.
    """
    metadata = config.stash.setdefault(metadata_key, {})
    # pytest-metadata's ``Python`` is the one running pytest, which is not the
    # conda under test's; relabel it so the two Python rows can't be confused.
    if "Python" in metadata:
        metadata["Harness Python"] = metadata.pop("Python")
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
    """Add the conda under test's path, version, base Python and platform to the report.

    pytest-html reads the table before this runs, but it keeps a reference to the
    same dict, so these rows still show up. This wouldn't work under pytest-xdist.
    """
    metadata = request.config.stash[metadata_key]
    try:
        # Resolved lazily so a missing conda doesn't fail every test
        conda_exe: str = request.getfixturevalue("conda_exe")
        # Query the host conda (not the per-test sandbox) with inherited CONDA_* stripped,
        # so an outer activation doesn't skew the result.
        runner = CliRunner(executable=conda_exe, environ=env_without_conda_vars())
        info = CondaInfo.from_json(runner("info", "--json"))
    # These rows are optional, so log any failure instead of erroring every test.
    except (Exception, pytest.fail.Exception):
        logger.exception("could not record conda metadata for the report")
        return
    metadata["Conda under test"] = conda_exe
    metadata["Conda version"] = info.conda_version
    metadata["Conda base Python"] = info.python_version
    metadata["Conda platform"] = info.platform


@pytest.fixture(autouse=True)
def record_cli_calls(request: pytest.FixtureRequest) -> Iterator[None]:
    """Record every command this test runs, for its row in the report.

    This includes conda_shell runs and commands from the test's fixtures, because
    autouse fixtures are set up first and torn down last. Commands from session- or
    module-scoped fixtures aren't recorded.
    """
    extras: list[dict[str, Any]] = []
    request.node.stash[_CLI_EXTRAS_KEY] = extras

    def record(result: CommandResult) -> None:
        extras.append(_cli_extra(len(extras) + 1, result))

    with observe_results(record):
        yield


def _cli_label(result: CommandResult) -> str:
    """Return a short heading naming the command that ran."""
    program, *argv = result.cmd
    name = Path(program).stem
    if argv and name.lower() not in _SHELL_EXECUTABLES:
        text = " ".join([name, *argv])
    else:
        # Shell run: the script is the last argument. On cmd the whole command line is
        # one string, `"cmd.exe" /d /s /c "<script>"`, so drop its closing quote.
        script = argv[-1] if argv else program.removesuffix('"')
        # Strip conda's hook setup, which ends at the first " && " (bash, zsh, sh, cmd)
        # or "}; " (PowerShell).
        text = re.split(r" && |\}; ", script, maxsplit=1)[-1]
    return text if len(text) <= _MAX_LABEL_CHARS else f"{text[: _MAX_LABEL_CHARS - 1]}…"


def _cli_extra(number: int, result: CommandResult) -> dict[str, Any]:
    """Render one command as a collapsed block for the test's report row.

    Collapsed because a failed test's traceback already shows the failing command.
    """
    summary = escape(f"{number}. {_cli_label(result)} (exit {result.returncode})")
    body = escape(result.describe(max_stream_chars=_MAX_STREAM_CHARS))
    return html_extras.html(f"<details><summary>{summary}</summary><pre>{body}</pre></details>")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Attach the test's recorded commands to its report row."""
    report = yield
    # pytest-html builds the row after teardown from the extras of all phases,
    # so we attach all commands once, here.
    if report.when == "teardown" and (extras := item.stash.get(_CLI_EXTRAS_KEY, None)):
        report.extras = [*getattr(report, "extras", []), *extras]
    return report
