# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda clean command."""

from __future__ import annotations

from pathlib import Path

from conda_e2e.utils import unique_env_name

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
    """``conda clean --help`` documents available options."""
    result = conda("clean", "--help").assert_ok()
    output = f"{result.stdout}\n{result.stderr}"

    expected = (
        "usage:",
        "conda clean",
        "Remove unused packages and caches",
        "-h, --help",
        "-a, --all",
        "-i, --index-cache",
        "-p, --packages",
        "-t, --tarballs",
        "-f, --force-pkgs-dirs",
        "--tempfiles",
        "-d, --dry-run",
    )
    missing = [e for e in expected if e not in output]
    assert not missing, f"help output missing {missing}. Command output:\n{output}"


def test_clean_index_cache(conda):
    """``conda clean --index-cache`` removes the index cache."""
    cache_dir = _get_cache_dir(conda)

    # Setup: populate the index cache by searching for a package
    conda("search", "python", "--json").assert_ok()
    assert _has_index_cache(cache_dir), "Index cache should exist after conda search"

    # Execute
    result = conda("clean", "--index-cache").assert_ok()

    # Verify filesystem
    assert not _has_index_cache(cache_dir), "Index cache should be removed after clean"

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "Will remove" in output, f"Output should contain 'Will remove'. Got:\n{output}"
    assert "index cache" in output, f"Output should contain 'index cache'. Got:\n{output}"


def test_clean_tarballs(conda):
    """``conda clean --tarballs`` removes cached package tarballs."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: install a package to create tarballs in the cache
    conda("create", "-n", env_name, "zlib").assert_ok()
    assert _has_tarballs(cache_dir), "Package tarballs should exist after install"

    # Execute
    result = conda("clean", "--tarballs").assert_ok()

    # Verify filesystem
    assert not _has_tarballs(cache_dir), "Tarballs should be removed after clean"

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "Will remove" in output, f"Output should contain 'Will remove'. Got:\n{output}"
    assert "tarball" in output, f"Output should contain 'tarball'. Got:\n{output}"


def test_clean_packages(conda):
    """``conda clean --packages`` removes unused extracted packages."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: install then remove a package to leave orphaned cache entries
    conda("create", "-n", env_name, "zlib").assert_ok()
    conda("env", "remove", "-n", env_name).assert_ok()
    assert _has_extracted_packages(cache_dir), "Extracted packages should exist in cache"

    # Execute
    result = conda("clean", "--packages").assert_ok()

    # Verify filesystem
    assert not _has_extracted_packages(cache_dir), (
        "Extracted packages should be removed after clean"
    )

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "Will remove" in output, f"Output should contain 'Will remove'. Got:\n{output}"
    assert "package" in output, f"Output should contain 'package'. Got:\n{output}"


def test_clean_force_pkgs_dirs(conda):
    """``conda clean --force-pkgs-dirs`` removes all writable package caches."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: install a package to populate the cache
    conda("create", "-n", env_name, "zlib").assert_ok()
    has_content = _has_tarballs(cache_dir) or _has_extracted_packages(cache_dir)
    assert has_content, "Package cache should have content after install"

    # Execute
    result = conda("clean", "--force-pkgs-dirs").assert_ok()

    # Verify filesystem
    has_content_after = _has_tarballs(cache_dir) or _has_extracted_packages(cache_dir)
    assert not has_content_after, "Package cache should be empty after force clean"

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "Will remove" in output, f"Output should contain 'Will remove'. Got:\n{output}"
    assert "package cache" in output, f"Output should contain 'package cache'. Got:\n{output}"


def test_clean_all(conda):
    """``conda clean --all`` removes index cache, tarballs, and unused packages."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: populate caches
    conda("search", "python", "--json").assert_ok()
    conda("create", "-n", env_name, "zlib").assert_ok()
    conda("env", "remove", "-n", env_name).assert_ok()
    assert _has_index_cache(cache_dir), "Index cache should exist"
    assert _has_tarballs(cache_dir), "Tarballs should exist"

    # Execute
    result = conda("clean", "--all").assert_ok()

    # Verify filesystem
    assert not _has_index_cache(cache_dir), "Index cache should be removed"
    assert not _has_tarballs(cache_dir), "Tarballs should be removed"

    # Verify output messages
    output = f"{result.stdout}\n{result.stderr}"
    assert "Will remove" in output, f"Output should contain 'Will remove'. Got:\n{output}"
    assert "index cache" in output, f"Output should contain 'index cache'. Got:\n{output}"
    assert "tarball" in output, f"Output should contain 'tarball'. Got:\n{output}"


def test_clean_dry_run(conda):
    """``conda clean --all --dry-run`` shows what would be removed without removing."""
    cache_dir = _get_cache_dir(conda)
    env_name = unique_env_name()

    # Setup: populate caches
    conda("search", "python", "--json").assert_ok()
    conda("create", "-n", env_name, "zlib").assert_ok()
    had_index_cache = _has_index_cache(cache_dir)
    had_tarballs = _has_tarballs(cache_dir)

    # Execute
    result = conda("clean", "--all", "--dry-run").assert_ok()

    # Verify: nothing was actually removed
    assert _has_index_cache(cache_dir) == had_index_cache, "Index cache state should be unchanged"
    assert _has_tarballs(cache_dir) == had_tarballs, "Tarballs state should be unchanged"

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "DryRunExit" in output or "Dry run" in output, (
        f"Output should indicate dry run. Got:\n{output}"
    )


def test_clean_tempfiles_empty(conda):
    """``conda clean --tempfiles`` with no tempfiles to remove succeeds."""
    result = conda("clean", "--tempfiles").assert_ok()
    output = f"{result.stdout}\n{result.stderr}"
    assert "There are no tempfile(s) to remove" in output, (
        f"Output should indicate no tempfiles. Got:\n{output}"
    )


# =============================================================================
# Edge cases
# =============================================================================


def test_clean_tempfiles_nonexistent_path_no_error(conda):
    """``conda clean --tempfiles /nonexistent`` handles bad path gracefully."""
    result = conda("clean", "--tempfiles", "/nonexistent/path").assert_ok()
    output = f"{result.stdout}\n{result.stderr}"
    assert "There are no tempfile(s) to remove" in output, (
        f"Output should indicate no tempfiles. Got:\n{output}"
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
