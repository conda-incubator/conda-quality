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


def site_packages_dir(prefix: str | Path, python_version: str) -> Path:
    """Return the site-packages directory for ``python_version`` under ``prefix``."""
    if IS_WINDOWS:
        return Path(prefix) / "Lib" / "site-packages"
    major_minor = ".".join(python_version.split(".")[:2])
    return Path(prefix) / "lib" / f"python{major_minor}" / "site-packages"


def pretty_json(data: Any, *, indent: int = 2, sort_keys: bool = False) -> str:
    """Format ``data`` as indented JSON for debug output or assertion messages.

    Non-JSON values (e.g. ``Path``) are stringified, and non-ASCII characters
    are preserved.

    Args:
        data: Any JSON-serialisable object (e.g. ``result.json()``).
        indent: Number of spaces per nesting level.
        sort_keys: Sort object keys for stable, diff-friendly output.

    Returns:
        str: The indented JSON text.

    """
    return json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False, default=str)
