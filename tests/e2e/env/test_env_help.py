# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda env``."""

from __future__ import annotations

import re

from help_command_helpers import has_help_item, normalized, option_tokens

EXPECTED_SUBCOMMAND_DESCRIPTIONS = {
    "config": "Configure a conda environment.",
    "create": "Create an environment based on an environment definition file.",
    "export": "Export a conda environment to a file.",
    "list": "An alias for `conda info --envs`. Lists all conda environments.",
    "remove": "Remove an environment.",
    "update": "Update the current environment based on environment file.",
}

EXPECTED_HELP = {
    "usage": ("usage: conda env [-h] command ...",),
    "positional arguments": ("positional arguments:",),
    "options": (
        "options:",
        "Show this help message and exit.",
    ),
}

# Tokens from the options: section only (list's description mentions --envs).
EXPECTED_OPTION_TOKENS = {"-h", "--help"}

# A name's help text is set off by 2+ spaces; wrapped continuation lines aren't.
_SUBCOMMAND_NAME_RE = re.compile(r"^\s*(\S+)  ", re.MULTILINE)


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


# =============================================================================
# Positive test cases
# =============================================================================


def test_env_help_documents_sections_and_options(conda):
    """``conda env --help`` documents every section and option."""
    output = conda("env", "--help").assert_ok().stdout
    collapsed = normalized(output)
    missing = {}
    for section, items in EXPECTED_HELP.items():
        section_missing = [item for item in items if not has_help_item(item, collapsed)]
        if section_missing:
            missing[section] = section_missing
    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"

    actual_options = option_tokens(_section_body(output, "options:"))
    assert actual_options == EXPECTED_OPTION_TOKENS, (
        f"missing options: {sorted(EXPECTED_OPTION_TOKENS - actual_options)}, "
        f"added options: {sorted(actual_options - EXPECTED_OPTION_TOKENS)}\nOutput:\n{output}"
    )


def test_env_help_subcommand_descriptions_pair_correctly(conda):
    """Each subcommand in ``conda env --help`` is paired with its own description.

    Comparing the full name set (not just checking known names are present) also
    catches a subcommand added or renamed without matching test coverage.
    """
    output = conda("env", "--help").assert_ok().stdout
    collapsed = normalized(output)

    actual_names = set(_SUBCOMMAND_NAME_RE.findall(_section_body(output, "positional arguments:")))
    assert actual_names == EXPECTED_SUBCOMMAND_DESCRIPTIONS.keys(), (
        f"missing subcommands: {EXPECTED_SUBCOMMAND_DESCRIPTIONS.keys() - actual_names}, "
        f"added subcommands: {actual_names - EXPECTED_SUBCOMMAND_DESCRIPTIONS.keys()}\n"
        f"Output:\n{output}"
    )

    mispaired = [
        f"{name}: {description}"
        for name, description in EXPECTED_SUBCOMMAND_DESCRIPTIONS.items()
        if not has_help_item(f"{name} {description}", collapsed)
    ]
    assert not mispaired, f"Subcommand not paired with its description: {mispaired}\n{output}"


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
