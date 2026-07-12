# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda clean command."""

from __future__ import annotations

import re
from pathlib import Path

from conda_e2e.utils import unique_env_name

# Expected content in conda clean --help organized by section
EXPECTED_HELP = {
    "usage": ("usage: conda clean",),
    "description": ("Remove unused packages and caches",),
    "options": ("-h, --help",),
    "removal targets": (
        "Removal Targets:",
        "-a, --all",
        "-i, --index-cache",
        "-p, --packages",
        "-t, --tarballs",
        "-f, --force-pkgs-dirs",
        "--tempfiles",
        "-l, --logfiles",
    ),
    "output options": (
        "Output, Prompt, and Flow Control Options:",
        "--json",
        "-v, --verbose",
        "-q, --quiet",
        "-d, --dry-run",
        "-y, --yes",
    ),
    "examples": (
        "Examples:",
        "conda clean --tarballs",
    ),
}


# =============================================================================
# Helper functions
# =============================================================================


def _get_cache_dir(conda) -> Path:
    """Get the package cache directory from conda info."""
    result = conda("info", "--json").assert_ok()
    info = result.json()
    return Path(info["pkgs_dirs"][0])


def _has_index_cache(cache_dir: Path) -> bool:
    """Check if index cache files exist."""
    cache_subdir = cache_dir / "cache"
    if not cache_subdir.exists():
        return False
    return any(cache_subdir.glob("*.json"))


def _has_tarballs(cache_dir: Path) -> bool:
    """Check if package tarballs exist."""
    if not cache_dir.exists():
        return False
    return any(cache_dir.glob("*.tar.bz2")) or any(cache_dir.glob("*.conda"))


def _has_extracted_packages(cache_dir: Path) -> bool:
    """Check if extracted package directories exist."""
    if not cache_dir.exists():
        return False
    for item in cache_dir.iterdir():
        # Exclude "cache" (index cache metadata) and ".trash" (pending deletion)
        # as these are not extracted packages
        if item.is_dir() and item.name not in ("cache", ".trash"):
            return True
    return False


# =============================================================================
# Positive test cases
# =============================================================================


def test_clean_help(conda):
    """``conda clean --help`` documents all flags, sections, and examples."""
    output = conda("clean", "--help").assert_ok().stdout

    missing = {}
    for section, items in EXPECTED_HELP.items():
        absent = [item for item in items if item not in output]
        if absent:
            missing[section] = absent

    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"


def test_clean_index_cache(conda):
    """``conda clean --index-cache`` removes only the index cache."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: populate the index cache and install a package
    conda("search", "python").assert_ok()
    conda("create", "-n", env_name, "zlib").assert_ok()

    assert _has_index_cache(cache_dir), "Index cache should exist after conda search"
    assert _has_tarballs(cache_dir), "Tarballs should exist after install"
    assert _has_extracted_packages(cache_dir), "Extracted packages should exist after install"

    # Execute
    result = conda("clean", "--index-cache").assert_ok()

    # Verify: index cache removed, other caches untouched
    assert not _has_index_cache(cache_dir), "Index cache should be removed"
    assert _has_tarballs(cache_dir), "Tarballs should NOT be removed by --index-cache"
    assert _has_extracted_packages(cache_dir), (
        "Extracted packages should NOT be removed by --index-cache"
    )

    # Verify output message
    assert re.search(
        r"Will remove \d+ index cache\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_tarballs(conda):
    """``conda clean --tarballs`` removes only cached package tarballs."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: populate caches
    conda("search", "python").assert_ok()
    conda("create", "-n", env_name, "zlib").assert_ok()

    assert _has_index_cache(cache_dir), "Index cache should exist"
    assert _has_tarballs(cache_dir), "Package tarballs should exist after install"
    assert _has_extracted_packages(cache_dir), "Extracted packages should exist after install"

    # Execute
    result = conda("clean", "--tarballs").assert_ok()

    # Verify: tarballs removed, other caches untouched
    assert not _has_tarballs(cache_dir), "Tarballs should be removed"
    assert _has_index_cache(cache_dir), "Index cache should NOT be removed by --tarballs"
    assert _has_extracted_packages(cache_dir), (
        "Extracted packages should NOT be removed by --tarballs"
    )

    # Verify output message (format: "Will remove N (SIZE) tarball(s).")
    assert re.search(
        r"Will remove \d+.*tarball\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_packages(conda):
    """``conda clean --packages`` removes only unused extracted packages."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: populate caches, then remove env to make packages unused
    conda("search", "python").assert_ok()
    conda("create", "-n", env_name, "zlib").assert_ok()
    conda("env", "remove", "-n", env_name).assert_ok()

    assert _has_index_cache(cache_dir), "Index cache should exist"
    assert _has_tarballs(cache_dir), "Tarballs should exist"
    assert _has_extracted_packages(cache_dir), "Extracted packages should exist in cache"

    # Execute
    result = conda("clean", "--packages").assert_ok()

    # Verify: extracted packages removed, other caches untouched
    assert not _has_extracted_packages(cache_dir), "Extracted packages should be removed"
    assert _has_index_cache(cache_dir), "Index cache should NOT be removed by --packages"
    assert _has_tarballs(cache_dir), "Tarballs should NOT be removed by --packages"

    # Verify output message (format: "Will remove N (SIZE) package(s).")
    assert re.search(
        r"Will remove \d+.*package\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_force_pkgs_dirs(conda):
    """``conda clean --force-pkgs-dirs`` removes all writable package caches."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: install a package to populate the cache
    conda("create", "-n", env_name, "zlib").assert_ok()

    assert _has_tarballs(cache_dir), "Tarballs should exist after install"
    assert _has_extracted_packages(cache_dir), "Extracted packages should exist after install"

    # Execute
    result = conda("clean", "--force-pkgs-dirs").assert_ok()

    # Verify filesystem
    assert not _has_tarballs(cache_dir), "Tarballs should be removed"
    assert not _has_extracted_packages(cache_dir), "Extracted packages should be removed"

    # Verify output message
    assert re.search(
        r"Will remove \d+ package cache\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_all(conda):
    """``conda clean --all`` removes index cache, tarballs, and unused packages."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: populate all caches, then remove env to make packages unused
    conda("search", "python").assert_ok()
    conda("create", "-n", env_name, "zlib").assert_ok()
    conda("env", "remove", "-n", env_name).assert_ok()

    assert _has_index_cache(cache_dir), "Index cache should exist"
    assert _has_tarballs(cache_dir), "Tarballs should exist"
    assert _has_extracted_packages(cache_dir), "Extracted packages should exist"

    # Execute
    result = conda("clean", "--all").assert_ok()

    # Verify all caches removed
    assert not _has_index_cache(cache_dir), "Index cache should be removed"
    assert not _has_tarballs(cache_dir), "Tarballs should be removed"
    assert not _has_extracted_packages(cache_dir), "Extracted packages should be removed"

    # Verify output messages
    output = result.stdout
    assert re.search(r"Will remove \d+ index cache\(s\)\.", output), (
        f"Expected index cache removal message. Got:\n{output}"
    )
    assert re.search(r"Will remove \d+.*tarball\(s\)\.", output), (
        f"Expected tarball removal message. Got:\n{output}"
    )


def test_clean_dry_run(conda):
    """``conda clean --all --dry-run`` shows what would be removed without removing."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: populate all caches, then remove env to orphan packages
    conda("search", "python").assert_ok()
    conda("create", "-n", env_name, "zlib").assert_ok()
    conda("env", "remove", "-n", env_name).assert_ok()

    # Verify caches exist before dry-run
    assert _has_index_cache(cache_dir)
    assert _has_tarballs(cache_dir)
    assert _has_extracted_packages(cache_dir)

    # Execute
    result = conda("clean", "--all", "--dry-run").assert_ok()

    # Verify: nothing was actually removed
    assert _has_index_cache(cache_dir), "Index cache state should be unchanged"
    assert _has_tarballs(cache_dir), "Tarballs state should be unchanged"
    assert _has_extracted_packages(cache_dir), "Extracted packages state should be unchanged"

    # Verify output indicates dry run
    assert "DryRunExit" in result.stderr or "Dry run" in result.stderr, (
        f"Output should indicate dry run. Got:\n{result.stderr}"
    )


def test_clean_tempfiles_empty(conda):
    """``conda clean --tempfiles`` with no tempfiles to remove succeeds."""
    result = conda("clean", "--tempfiles").assert_ok()
    assert "There are no tempfile(s) to remove" in result.stdout, (
        f"Output should indicate no tempfiles. Got:\n{result.stdout}"
    )


def test_clean_tempfiles_nonexistent_path(conda, tmp_path):
    """``conda clean --tempfiles`` with nonexistent path succeeds gracefully."""
    nonexistent = tmp_path / "does-not-exist"
    result = conda("clean", "--tempfiles", str(nonexistent)).assert_ok()
    assert "There are no tempfile(s) to remove" in result.stdout, (
        f"Output should indicate no tempfiles. Got:\n{result.stdout}"
    )


# =============================================================================
# Negative test cases
# =============================================================================


def test_clean_no_target_fails(conda):
    """``conda clean`` without any removal target fails."""
    result = conda("clean")
    result.assert_error(
        code=2,
        contains="At least one removal target must be given",
    )


def test_clean_invalid_flag_fails(conda):
    """``conda clean --invalid-flag`` fails with unrecognized argument error."""
    result = conda("clean", "--invalid-flag")
    result.assert_error(
        code=2,
        contains="unrecognized arguments: --invalid-flag",
    )
