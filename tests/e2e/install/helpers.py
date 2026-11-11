# SPDX-License-Identifier: BSD-3-Clause
"""Shared helper functions for conda install E2E tests."""

from __future__ import annotations

from pathlib import Path

# Re-exported so existing `from helpers import ...` call sites keep working; the
# implementations are shared with the create suite.
from shared.helpers import list_installed_packages as list_installed_packages
from shared.helpers import pick_second_newest_and_latest as pick_second_newest_and_latest
from shared.helpers import search_versions as search_versions

PACKAGE_NAME = "flask"
DEPENDENCY_PACKAGE_NAME = "werkzeug"
SECONDARY_PACKAGE_NAME = "click"
SINGLE_FILE_PACKAGE_NAME = "six"

# Static test data files
DATA_DIR = Path(__file__).parent.parent.parent / "data"
REQUIREMENTS_FILE = DATA_DIR / "requirements.txt"
ENVIRONMENT_YML_FILE = DATA_DIR / "environment.yml"


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
