# SPDX-License-Identifier: BSD-3-Clause
"""Shared helper functions for conda install E2E tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.version import Version

if TYPE_CHECKING:
    from conda_e2e.parsers.list import PackageList, PackageRecord

from conda_e2e.utils import site_packages_dir

if TYPE_CHECKING:
    from pathlib import Path


def python_version(installed: PackageList) -> str:
    """Return the installed ``python`` package's version, asserting it's present."""
    python = installed.get("python")
    assert python is not None, "python should be installed as a dependency"
    return python.version


def assert_package_unpacked(
    env_path: Path,
    package_name: str,
    python_version: str | None = None,
) -> None:
    """Assert ``package_name`` is physically unpacked on disk (as a package dir)."""
    site_packages = site_packages_dir(env_path, python_version)
    init_file = site_packages / package_name / "__init__.py"
    assert init_file.is_file(), f"{package_name} should be unpacked on disk at {site_packages}"


def search_versions(conda, package_name: str) -> list[str]:
    """Return all available versions for ``package_name``, sorted ascending."""
    search_result = conda("search", package_name, "--json").assert_ok()
    return sorted(
        {p["version"] for p in search_result.json().get(package_name, [])},
        key=Version,
    )


def require_installed_record(installed: PackageList, package_name: str) -> PackageRecord:
    """Return ``package_name``'s record from ``installed``, asserting it's present."""
    record = installed.get(package_name)
    assert record is not None, f"{package_name} record should be found in conda list"
    return record


def assert_installed_version(
    installed: PackageList,
    package_name: str,
    expected_version: str,
    context: str | None = None,
) -> None:
    """Assert ``package_name`` is present in ``installed`` at exactly ``expected_version``.

    ``context`` is prefixed to the failure message to explain why this version was
    expected (e.g. a specific flag's documented behavior), for tests where the
    generic "expected X==Y" message alone wouldn't be diagnostic enough.
    """
    record = require_installed_record(installed, package_name)
    message = f"expected {package_name}=={expected_version}. Got: {record.version}"
    if context:
        message = f"{context} {message}"
    assert record.version == expected_version, message


def pick_second_newest_and_latest(conda, package_name: str) -> tuple[str, str]:
    """Return ``(old_version, latest_version)`` for ``package_name``, picked dynamically.

    ``old_version`` is the second-newest available version, so it's guaranteed to
    be older than ``latest_version`` (asserted below) without hardcoding a version
    that could age out.
    """
    versions = search_versions(conda, package_name)
    assert len(versions) >= 2, f"need at least 2 {package_name} versions to pick from"
    old_version, latest_version = versions[-2], versions[-1]
    assert Version(old_version) < Version(latest_version), (
        f"{package_name}: expected old_version ({old_version}) to be older than "
        f"latest_version ({latest_version})"
    )
    return old_version, latest_version
