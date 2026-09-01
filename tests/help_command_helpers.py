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


def option_tokens(output: str) -> set[str]:
    """Return the flags an options section defines, without their metavars.

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


def normalized(text: str) -> str:
    """Collapse wrapping and repeated whitespace for stable help comparisons."""
    return " ".join(text.split())


def has_help_item(item: str | tuple[str, ...], output: str) -> bool:
    """Return whether an item or one of its portable renderings appears in output."""
    norm_output = normalized(output)
    options = item if isinstance(item, tuple) else (item,)
    return any(normalized(option) in norm_output for option in options)
