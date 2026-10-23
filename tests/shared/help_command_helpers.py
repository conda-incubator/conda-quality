"""Extract the structural contract of conda command help without incidental prose."""

from __future__ import annotations

import re


def normalized(text: str) -> str:
    """Collapse wrapping and repeated whitespace for stable help comparisons."""
    return " ".join(text.split())


def _parse_option(option_line: str) -> tuple[frozenset[str], set[str]]:
    option_definition = option_line.partition("  ")[0]
    choice_values = set()
    for choice_block in re.findall(r"\{[^{}]*\}", option_definition):
        for choice_value in choice_block[1:-1].split(","):
            choice_values.add(normalized(choice_value))
        option_definition = option_definition.replace(choice_block, "")

    option_aliases = set()
    for option_word in option_definition.replace(",", " ").split():
        if option_word.startswith("-"):
            option_aliases.add(option_word)
    return frozenset(option_aliases), choice_values


def _add_positional(line: str, positionals: dict) -> None:
    """Two-space lines are positionals; four-space lines are subcommands of the previous one."""
    match = re.match(r"( {2}| {4})(\S+)", line)
    if match is None:
        return
    leading_spaces, first_word = match.groups()
    if len(leading_spaces) == 2:
        positionals[first_word] = set()
    else:
        positionals[list(positionals)[-1]].add(first_word)


def parse_help(output: str) -> dict:
    """Extract usage, description, sections, alias groups, choices, and positionals.

    Only two-space-indented option definitions contribute flags. Metavariables,
    option descriptions, section prose, and examples are not part of the contract.
    Nested positional entries use four spaces, unlike deeper wrapped descriptions.
    """
    lines = output.splitlines()
    usage_lines = []
    for line in lines:
        if not line.strip():
            break
        usage_lines.append(line)

    description_lines = []
    sections: dict = {}
    section = None
    found_flags = False
    for line in lines[len(usage_lines) :]:
        if line.rstrip().endswith(":") and not line.startswith(" "):
            section = normalized(line)
            if section in {"Example:", "Examples:"}:
                break
            sections[section] = {}
            continue
        if section is None:
            description_lines.append(line)
        elif section == "positional arguments:":
            _add_positional(line, sections[section])
        elif line.startswith("  -"):
            flags, choices = _parse_option(line[2:])
            sections[section][flags] = choices
            found_flags = True

    if not found_flags:
        raise ValueError(
            "No help flags found in two-space-indented option definitions. "
            "ANSI/color output (for example FORCE_COLOR or PYTHON_COLORS) is a possible cause."
        )
    return {
        "usage": normalized(" ".join(usage_lines).partition("[")[0]),
        "description": normalized(" ".join(description_lines)),
        "sections": sections,
    }
