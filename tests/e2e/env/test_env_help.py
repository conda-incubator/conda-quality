# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda env``."""

from __future__ import annotations

import re

from help_command_helpers import normalized

EXPECTED_HELP = {
    "usage": "usage: conda env [-h] command ...",
    "positional_arguments": {
        "config": "Configure a conda environment.",
        "create": "Create an environment based on an environment definition file.",
        "export": "Export a conda environment to a file.",
        "list": "An alias for `conda info --envs`. Lists all conda environments.",
        "remove": "Remove an environment.",
        "update": "Update the current environment based on environment file.",
    },
    "options": {
        "-h, --help": "Show this help message and exit.",
    },
}


def _section_body(output: str, header: str) -> str:
    """Return the lines of the section starting at ``header``, up to the next blank line."""
    lines = output.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        return ""
    body = []
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        body.append(line)
    return "\n".join(body)


def _entries(section_body: str) -> dict[str, str]:
    """Map each ``name  description`` line to a name->description pair."""
    entries = {}
    for line in section_body.splitlines():
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) == 2:
            entries[parts[0]] = parts[1]
    return entries


def _parsed_help(output: str) -> dict:
    """Reduce ``conda env --help`` output to the structure of ``EXPECTED_HELP``."""
    return {
        "usage": normalized(output.partition("\n\n")[0]),
        "positional_arguments": _entries(_section_body(output, "positional arguments:")),
        "options": _entries(_section_body(output, "options:")),
    }


# =============================================================================
# Positive test cases
# =============================================================================


def test_env_help_matches_contract(conda):
    """``conda env --help`` documents exactly the expected subcommands and options."""
    output = conda("env", "--help").assert_ok().stdout
    assert _parsed_help(output) == EXPECTED_HELP, f"Output:\n{output}"


def test_env_help_short_flag_matches_long_form(conda):
    """``conda env -h`` renders identically to ``--help``."""
    long_form = conda("env", "--help").assert_ok().stdout
    short_form = conda("env", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"


def test_env_without_subcommand_prints_help(conda):
    """``conda env`` with no subcommand prints its help, matching ``--help`` exactly."""
    bare = conda("env").assert_ok().stdout
    help_output = conda("env", "--help").assert_ok().stdout
    assert bare == help_output, "bare `conda env` should render the same help as --help"


# =============================================================================
# Negative test cases
# =============================================================================


def test_env_rejects_unknown_subcommand(conda):
    """``conda env <unknown>`` reports the invalid choice on stderr."""
    conda("env", "not-a-subcommand").assert_error(
        code=2, contains="argument command: invalid choice"
    )
