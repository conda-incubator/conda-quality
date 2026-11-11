# SPDX-License-Identifier: BSD-3-Clause
"""Assertion helpers for on-disk package state, shared across the conda E2E suites."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def require_cached_package_init_file(cache_dir: Path, package_name: str) -> Path:
    """Return the single extracted ``__init__.py`` for ``package_name`` in the package cache."""
    cache_files = list(cache_dir.glob(f"**/{package_name}/__init__.py"))
    assert len(cache_files) == 1, (
        f"Expected one cached {package_name}/__init__.py, got: {cache_files}"
    )
    return cache_files[0]
