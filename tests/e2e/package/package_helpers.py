# SPDX-License-Identifier: BSD-3-Clause
"""Setup and assertion helpers for ``conda package`` tests.

Kept local to the ``package`` test module since these are only needed here: planting an
untracked file, deriving the archive path ``conda package`` writes from its metadata flags,
asserting a file is present in a created archive, and reducing help text to a comparable
set of option tokens.
"""

from __future__ import annotations

import re
import tarfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# Shared across the --prefix and --name package-creation tests: both invoke `conda package`
# with identical metadata flags, differing only in how the target environment is specified.
PACKAGE_METADATA_NAME = "e2e-package"
PACKAGE_METADATA_VERSION = "1.2.3"
PACKAGE_METADATA_BUILD = "7"

EXPECTED_HELP = {
    "text": (
        "usage: conda package",
        "Create low-level conda packages. (EXPERIMENTAL)",
    ),
    "headers": (
        "options:",
        "Target Environment Specification:",
    ),
    "flags": (
        "-h",
        "--help",
        "-w",
        "--which",
        "-r",
        "--reset",
        "-u",
        "--untracked",
        "--pkg-name",
        "--pkg-version",
        "--pkg-build",
        "-n",
        "--name",
        "-p",
        "--prefix",
    ),
    "option arguments": (
        "--which PATH [PATH ...]",
        "--pkg-name PKG_NAME",
        "--pkg-version PKG_VERSION",
        "--pkg-build PKG_BUILD",
        "--name ENVIRONMENT",
        "--prefix PATH",
    ),
}

# Matches a short (`-x`) or long (`--long-flag`) option spelling, so help output and our
# own expected-flags text can both be reduced to a comparable set of option tokens.
_OPTION_TOKEN_RE = re.compile(r"(?<!\w)(--[a-z][a-z0-9-]*|-[a-zA-Z])(?!\w)")


def option_tokens(text: str) -> set[str]:
    """Return every ``-x``/``--long-flag`` token found in `text`."""
    return set(_OPTION_TOKEN_RE.findall(text))


def create_untracked_file(env_prefix) -> Path:
    """Create and return a nested file absent from the environment manifest."""
    untracked_file = env_prefix / "nested" / "untracked.txt"
    untracked_file.parent.mkdir()
    untracked_file.write_text("untracked package test\n")
    return untracked_file


def package_archive_path(tmp_path: Path, package_name: str = PACKAGE_METADATA_NAME) -> Path:
    """Return the archive path conda derives from `package_name` and the shared version/build."""
    return tmp_path / f"{package_name}-{PACKAGE_METADATA_VERSION}-{PACKAGE_METADATA_BUILD}.tar.bz2"


def assert_archive_contains(archive: Path, relative_path: str) -> None:
    """Assert `relative_path` is a member of the created package archive."""
    with tarfile.open(archive) as created_package:
        archived_names = created_package.getnames()
    assert relative_path in archived_names, (
        f"Expected {relative_path!r} in archive contents: {archived_names}"
    )
