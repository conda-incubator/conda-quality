# SPDX-License-Identifier: BSD-3-Clause
"""Shared helper functions for conda install E2E tests."""

from __future__ import annotations

from packaging.version import Version

from conda_e2e.parsers.list import PackageList

NEW_PKG_INSTALLED_MSG = "The following NEW packages will be INSTALLED:"
PACKAGE_NAME = "flask"
DEPENDENCY_PACKAGE_NAME = "werkzeug"


def list_installed_packages(conda, flag: str, target: str, *, as_json: bool = False) -> PackageList:
    """Return parsed ``conda list`` output for a target env name/path."""
    args = ("list", flag, target, "--json") if as_json else ("list", flag, target)
    list_result = conda(*args).assert_ok()
    return PackageList.from_json(list_result) if as_json else PackageList.from_stdout(list_result)


def search_versions(conda, package_name: str) -> list[str]:
    """Return all available versions for ``package_name``, sorted ascending."""
    search_result = conda("search", package_name, "--json").assert_ok()
    return sorted(
        {p["version"] for p in search_result.json().get(package_name, [])},
        key=Version,
    )


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
