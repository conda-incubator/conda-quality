# SPDX-License-Identifier: BSD-3-Clause
"""Utilities shared across the suite."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def unique_env_name(prefix: str = "e2e") -> str:
    """Return a unique environment name, e.g. ``e2e-ab12cd34``."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def env_prefix(envs_dir: str | Path, name: str) -> Path:
    """Return the on-disk prefix path for a named environment under ``envs_dir``."""
    return Path(envs_dir) / name


def env_exists(prefix: str | Path) -> bool:
    """Return whether an environment directory exists at ``prefix``."""
    return Path(prefix).is_dir()


def pretty_json(data: Any, *, indent: int = 2, sort_keys: bool = False) -> str:
    """Format ``data`` as indented JSON for debug output or assertion messages.

    ``default=str`` keeps it safe for ad-hoc debugging (``Path`` and other
    non-JSON values are stringified rather than raising); ``ensure_ascii=False``
    keeps unicode readable.

    Args:
        data: Any JSON-serialisable object (e.g. ``result.json()``).
        indent: Number of spaces per nesting level.
        sort_keys: Sort object keys for stable, diff-friendly output.

    Returns:
        str: The indented JSON text.

    """
    return json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False, default=str)
