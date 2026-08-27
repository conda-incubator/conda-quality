# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda env``."""

from __future__ import annotations

from conda_e2e.parsers.help import has_help_item, normalized, option_tokens

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
        "-h, --help",
        "Show this help message and exit.",
    ),
}

# Tokens from the options: section only (list's description mentions --envs).
EXPECTED_OPTION_TOKENS = {"-h", "--help"}


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


def subcommand_descriptions_from_help(output: str) -> dict[str, str]:
    """Map each subcommand to its description (shallowest-indent entries, deeper wraps)."""
    body = _section_body(output, "positional arguments:")
    lines = body.splitlines()
    entries = [line for line in lines if line.strip().partition(" ")[0] != "command"]
    if not entries:
        return {}
    entry_indent = min(len(line) - len(line.lstrip()) for line in entries)
    descriptions: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        token, _, rest = line.strip().partition(" ")
        if token == "command":
            continue
        if len(line) - len(line.lstrip()) == entry_indent:
            current = token
            descriptions[current] = [rest.strip()] if rest.strip() else []
        elif current is not None:
            descriptions[current].append(line.strip())
    return {name: " ".join(parts) for name, parts in descriptions.items()}


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
    """Each subcommand is paired with its own description."""
    output = conda("env", "--help").assert_ok().stdout
    actual = subcommand_descriptions_from_help(output)
    assert actual == EXPECTED_SUBCOMMAND_DESCRIPTIONS, (
        f"subcommand help pairs mismatch\n"
        f"  expected: {EXPECTED_SUBCOMMAND_DESCRIPTIONS}\n"
        f"  actual:   {actual}\nOutput:\n{output}"
    )


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
