# SPDX-License-Identifier: BSD-3-Clause
"""Shared helper functions for conda install E2E tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from conda_e2e.parsers.list import PackageList

PACKAGE_NAME = "flask"
DEPENDENCY_PACKAGE_NAME = "werkzeug"
SECONDARY_PACKAGE_NAME = "click"
SINGLE_FILE_PACKAGE_NAME = "six"

# Static test data files
DATA_DIR = Path(__file__).parent.parent.parent / "data"
REQUIREMENTS_FILE = DATA_DIR / "requirements.txt"
ENVIRONMENT_YML_FILE = DATA_DIR / "environment.yml"


def list_installed_packages(conda, flag: str, target: str) -> PackageList:
    """Return parsed JSON ``conda list`` output for a target env name/path."""
    list_result = conda("list", flag, target, "--json").assert_ok()
    return PackageList.from_json(list_result)


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


def download_table_rows(stdout: str) -> list[str]:
    """Extract download table rows from conda install output.

    Returns lines from the "packages will be downloaded" section that contain
    the ``|`` separator and are actual package data rows (excludes header and separator).
    """
    lines = stdout.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if "will be downloaded" in line)
    except StopIteration:
        return []
    rows = []
    for line in lines[start:]:
        if not (line.startswith("  ") and "|" in line):
            continue
        # Skip header row (contains "package" or "build" as column names)
        if "package" in line.lower() and "build" in line.lower():
            continue
        # Skip separator row (only dashes after the pipe)
        after_pipe = line.split("|")[-1].strip()
        if after_pipe.replace("-", "") == "":
            continue
        rows.append(line)
    return rows
