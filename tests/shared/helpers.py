# SPDX-License-Identifier: BSD-3-Clause
"""Helpers shared across the conda E2E suites."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conda_e2e.parsers.list import PackageList

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

import pytest
from packaging.version import Version


def list_installed_packages(conda: Callable, *target: str) -> PackageList:
    """Return parsed JSON ``conda list`` output for a target env name/path.

    Args:
        conda: The conda runner fixture.
        target: The environment selector conda expects, e.g. ``("-n", name)``
            or ``("-p", str(prefix))``.
    """
    return PackageList.from_json(conda("list", *target, "--json").assert_ok())


def search_versions(conda: Callable, package_name: str) -> list[str]:
    """Return all available versions for ``package_name``, sorted ascending."""
    search_result = conda("search", package_name, "--json").assert_ok()
    return sorted(
        {p["version"] for p in search_result.json().get(package_name, [])},
        key=Version,
    )


def pick_second_newest_and_latest(conda: Callable, package_name: str) -> tuple[str, str]:
    """Return ``(old_version, latest_version)`` for ``package_name``, picked dynamically.

    ``old_version`` is the second-newest available version, so it's guaranteed to
    be older than ``latest_version`` (validated below) without hardcoding a version
    that could age out.
    """
    versions = search_versions(conda, package_name)
    if len(versions) < 2:
        pytest.fail(f"need at least 2 {package_name} versions to pick from")
    old_version, latest_version = versions[-2], versions[-1]
    if Version(old_version) >= Version(latest_version):
        pytest.fail(
            f"{package_name}: expected old_version ({old_version}) to be older than "
            f"latest_version ({latest_version})"
        )
    return old_version, latest_version


def freeze_env(env_path: Path) -> None:
    """Mark an environment frozen by creating conda's ``conda-meta/frozen`` marker file.

    ``touch()`` raises on its own if it can't create the file, so its return
    is itself the success check; no follow-up existence assert is needed.
    """
    (env_path / "conda-meta" / "frozen").touch()
