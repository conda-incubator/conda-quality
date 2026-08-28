# SPDX-License-Identifier: BSD-3-Clause
"""Shared helpers for reading and comparing conda ``--help`` text.

These extract or normalize text; they don't assert themselves (contrast with a
``<command>_asserts.py`` module, whose functions perform the assertion directly).
Callers use the return values in their own ``assert`` expressions.

Not command-local: multiple command-area help tests 
(E.g., ``env``, and ``list``/``install``) compare against the same ``--help`` 
conventions. Registered with ``pytest.register_assert_rewrite`` in ``tests/conftest.py``.
"""

from __future__ import annotations

import re

# Short (`-x`) or long (`--long-flag`) option tokens.
_OPTION_TOKEN_RE = re.compile(r"(?<!\w)(--[a-z][a-z0-9-]*|-[a-zA-Z])(?!\w)")


def option_tokens(text: str) -> set[str]:
    """Return every ``-x``/``--long-flag`` token found in ``text``."""
    return set(_OPTION_TOKEN_RE.findall(text))


def normalized(text: str) -> str:
    """Collapse wrapping and repeated whitespace for stable help comparisons."""
    return " ".join(text.split())


def has_help_item(item: str | tuple[str, ...], collapsed_output: str) -> bool:
    """Return whether an item or one of its portable renderings appears in collapsed output.

    Args:
        item: One expected literal, or a tuple of version-specific alternative literals.
        collapsed_output: Help text already passed through :func:`normalized`.

    """
    options = item if isinstance(item, tuple) else (item,)
    return any(normalized(option) in collapsed_output for option in options)
