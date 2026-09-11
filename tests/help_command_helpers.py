# SPDX-License-Identifier: BSD-3-Clause
"""Shared helpers for reading and comparing conda ``--help`` text.

These extract or normalize text; they don't assert themselves (contrast with a
``<command>_asserts.py`` module, whose functions perform the assertion directly).
Callers use the return values in their own ``assert`` expressions.

Not command-local: multiple command-area help tests
(e.g. ``env``, and ``list``/``install``) compare against the same ``--help``
conventions.
"""

from __future__ import annotations

import re

# Option entries are indented by exactly 2 spaces; descriptions and wraps sit deeper.
_ENTRY_START_RE = re.compile(r"^ {2}(?! )")

# Recognized by name: its unindented captions can end in ':' and its commands are deeper-indented.
_EXAMPLES_HEADER = "Examples:"

# In argparse's positional group any 2-space-indented token is an entry, and entries may
# nest (``conda env`` lists subcommands under the bare ``command``).
_POSITIONAL_HEADER = "positional arguments:"

# Rendered identically in every command's help, so the expected text is shared.
HELP_OPTION = {"-h, --help": "Show this help message and exit."}

# The shared entries of the "Output, Prompt, and Flow Control Options:" group.
OUTPUT_CONTROL_OPTIONS = {
    "--console": "Select the backend to use for normal output rendering.",
    "--json": "Report all output as json. Suitable for using conda programmatically.",
    "-q, --quiet": "Do not display progress bar.",
    "-v, --verbose": (
        "Can be used multiple times. Once for detailed output, twice for INFO "
        "logging, thrice for DEBUG logging, four times for TRACE logging."
    ),
}

# The shared "Target Environment Specification:" group.
TARGET_ENVIRONMENT_OPTIONS = {
    "-n, --name": "Name of environment.",
    "-p, --prefix": "Full path to environment location (i.e. prefix).",
}

# Shared between list (options group) and install (Output group).
SHOW_CHANNEL_URLS_OPTION = {
    "--show-channel-urls": (
        "Show channel urls. Overrides the value given by `conda config --show show_channel_urls`."
    ),
}


def option_flags(output: str) -> set[str]:
    """Return every flag defined in the help output, without their metavars.

    Only flag-column tokens are read, so a flag named in a description isn't counted.
    """
    tokens = set()
    for line in output.splitlines():
        if not line.startswith("  -"):
            continue
        flags_column = line[2:].split("  ")[0].replace(",", " ")
        tokens.update(word for word in flags_column.split() if word.startswith("-"))
    return tokens


def signature_flags(signature: str) -> str:
    """Return a signature's flags in render order, dropping metavars and choices.

    ``-c [TEMPFILES ...], --tempfiles [TEMPFILES ...]`` and
    ``-c, --tempfiles [TEMPFILES ...]`` both reduce to ``-c, --tempfiles``, so
    the comparison survives argparse's metavar-placement presentation changes.
    """
    words = re.sub(r"[,\[\]{}]", " ", signature).split()
    return ", ".join(word for word in words if word.startswith("-"))


def normalized(text: str) -> str:
    """Collapse wrapping and repeated whitespace for stable help comparisons."""
    return " ".join(text.split())


def has_help_item(item: str | tuple[str, ...], output: str) -> bool:
    """Return whether an item or one of its portable renderings appears in output."""
    options = item if isinstance(item, tuple) else (item,)
    if any(not option.strip() for option in options):
        return False
    norm_output = normalized(output)
    return any(normalized(option) in norm_output for option in options)


def _is_section_header(lines: list[str], index: int) -> bool:
    """Return whether ``lines[index]`` opens a section (``options:``, ...)."""
    line = lines[index]
    if line[:1].isspace() or not line.rstrip().endswith(":"):
        return False
    if line.strip() == _EXAMPLES_HEADER:
        return True
    # A section body opens with a 2-space-indented line; example captions end in
    # ':' but precede deeper-indented commands.
    for following in lines[index + 1 :]:
        if following.strip():
            return bool(_ENTRY_START_RE.match(following))
    return False


def _parse_section(body_lines: list[str], *, positional: bool) -> dict:
    """Reduce one section's body to its ``entries`` and/or ``prose``.

    Entries are the 2-space-indented ``signature  description`` pairs (options,
    or metavars in the positional-arguments section); option keys are normalized
    via :func:`signature_flags` and wrapped lines rejoined. Everything else
    accumulates into whitespace-normalized prose paragraphs. Empty keys are
    omitted, so a section is compared for exactly the content it renders.
    """
    entries: dict[str, str] = {}
    prose: list[str] = []
    key: str | None = None
    parts: list[str] = []
    paragraph: list[str] = []

    def close_entry() -> None:
        nonlocal key, parts
        if key is not None:
            name = signature_flags(key) if key.startswith("-") else key
            entries[name] = normalized(" ".join(parts))
            key = None
            parts = []

    def close_paragraph() -> None:
        if paragraph:
            prose.append(normalized(" ".join(paragraph)))
            paragraph.clear()

    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            close_entry()
            close_paragraph()
            continue
        is_entry_start = _ENTRY_START_RE.match(line) and (positional or stripped.startswith("-"))
        if is_entry_start:
            close_entry()
            close_paragraph()
            split = re.split(r"\s{2,}", stripped, maxsplit=1)
            key = split[0]
            parts = [split[1]] if len(split) > 1 else []
            continue
        if len(line) - len(line.lstrip()) > 2 and key is not None:
            # Positional group: a deeper name/description pair under a bare metavar
            # is a subcommand entry (``conda env``); otherwise a wrapped continuation.
            sub = re.split(r"\s{2,}", stripped, maxsplit=1) if positional else []
            if len(sub) > 1:
                close_entry()
                key, parts = sub[0], [sub[1]]
            else:
                parts.append(stripped)
            continue
        close_entry()
        paragraph.append(stripped)
    close_entry()
    close_paragraph()

    section = {}
    if entries:
        section["entries"] = entries
    if prose:
        section["prose"] = prose
    return section


def _usage_flags(usage: str) -> set[str]:
    """Return the flags named in a usage block, without metavars or choices.

    Layout characters (brackets, mutex pipes, commas, braces) are stripped, so
    ``[-c [TEMPFILES ...]]`` yields ``-c`` and the set is stable across
    argparse's per-Python-version usage renderings.
    """
    words = re.sub(r"[,\[\]{}|]", " ", usage).split()
    return {word for word in words if word.startswith("-")}


def parse_help(output: str) -> dict:
    """Reduce ``conda <command> --help`` output to the shape of ``EXPECTED_HELP``.

    Returns a dict like::

        {
            "usage": "usage: conda clean",
            "usage_flags": {"-h", "-a", ...},
            "description": "Remove unused packages and caches.",
            "sections": {
                "options:": {"entries": {"-h, --help": "Show this help message and exit."}},
                "Examples:": {"prose": ["conda clean --tarballs"]},
            },
        }

    ``usage`` is cut after the program name and ``usage_flags`` holds only the
    flag names: the option layout that follows is argparse's own rendering
    (metavar placement, group brackets, wrapping) and varies across Python
    versions; the options themselves are locked under ``sections``.
    ``description`` is the whitespace-normalized paragraph block between the
    usage and the first section.
    """
    lines = output.splitlines()
    index = 0

    usage_lines = []
    while index < len(lines) and lines[index].strip():
        usage_lines.append(lines[index])
        index += 1
    usage_block = normalized(" ".join(usage_lines))

    while index < len(lines) and not lines[index].strip():
        index += 1
    description_lines = []
    while index < len(lines) and not _is_section_header(lines, index):
        if lines[index].strip():
            description_lines.append(lines[index])
        index += 1

    sections: dict[str, dict] = {}
    while index < len(lines):
        if not _is_section_header(lines, index):
            index += 1
            continue
        header = lines[index].strip()
        index += 1
        body_lines = []
        while index < len(lines) and not _is_section_header(lines, index):
            body_lines.append(lines[index])
            index += 1
        sections[header] = _parse_section(body_lines, positional=header == _POSITIONAL_HEADER)

    return {
        "usage": usage_block.split(" [", 1)[0],
        "usage_flags": _usage_flags(usage_block),
        "description": normalized(" ".join(description_lines)),
        "sections": sections,
    }
