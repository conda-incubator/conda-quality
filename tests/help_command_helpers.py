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

# A 2-space-indented option signature line (e.g. "  -h, --help").
_OPTION_ENTRY_RE = re.compile(r"^ {2}(?! )-")


def option_flags(output: str) -> set[str]:
    """Return every flag defined in the help output, without their metavars.

    Only flag-column tokens are read, so a flag named in a description isn't counted.
    """
    tokens = set()
    for line in output.splitlines():
        # argparse indents an option definition by exactly 2 spaces and sets its
        # description off by 2+ more. Wrapped description lines are indented deeper.
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


def _strip_default(description: str) -> str:
    """Drop a trailing ``(default: ...)`` clause, a Python-version-dependent artifact."""
    return re.sub(r"\s*\(default: [^)]*\)\s*$", "", description).strip()


def option_pairs_from_help(output: str) -> dict[str, str]:
    """Return each option's flag pair mapped to its description.

    Keys are normalized via :func:`signature_flags` and trailing
    ``(default: ...)`` clauses are dropped, so metavar placement, choice
    spells, and Python-version-dependent default suffixes don't affect the
    comparison.
    """
    pairs: dict[str, str] = {}
    current: str | None = None
    parts: list[str] = []
    for line in output.splitlines():
        if _OPTION_ENTRY_RE.match(line):
            if current is not None:
                pairs[current] = " ".join(parts)
            split = re.split(r"\s{2,}", line.strip(), maxsplit=1)
            current = split[0]
            parts = [split[1].strip()] if len(split) > 1 else []
        elif not line.strip():
            if current is not None:
                pairs[current] = " ".join(parts)
                current = None
        elif len(line) - len(line.lstrip()) > 2 and current is not None:
            parts.append(line.strip())
        elif current is not None:
            pairs[current] = " ".join(parts)
            current = None
    if current is not None:
        pairs[current] = " ".join(parts)
    return {signature_flags(key): _strip_default(value) for key, value in pairs.items()}


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
