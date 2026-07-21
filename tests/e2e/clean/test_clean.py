# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda clean command."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from conda_e2e.utils import unique_env_name

if TYPE_CHECKING:
    from pathlib import Path

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


def _populate_index_cache(conda) -> None:
    """Populate the index cache only, via a channel search."""
    conda("search", "python").assert_ok()


def _populate_caches(conda, *, orphan_packages: bool = False) -> None:
    """Populate index, tarball, and extracted-package caches.

    Pass ``orphan_packages=True`` to remove the env afterwards, leaving its
    packages unused in the cache (needed to exercise ``--packages``/``--all``).
    """
    env_name = unique_env_name()

    _populate_index_cache(conda)
    conda("create", "-n", env_name, "zlib").assert_ok()

    if orphan_packages:
        conda("env", "remove", "-n", env_name).assert_ok()


def _assert_cache_state(
    cache_dir: Path, *, index_cache: bool, tarballs: bool, extracted: bool
) -> None:
    """Assert whether each cache is present (``True``) or absent (``False``)."""
    assert _has_index_cache(cache_dir) is index_cache, f"Expected index cache present={index_cache}"
    assert _has_tarballs(cache_dir) is tarballs, f"Expected tarballs present={tarballs}"
    assert _has_extracted_packages(cache_dir) is extracted, (
        f"Expected extracted packages present={extracted}"
    )


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


def test_clean_index_cache(conda, cache_dir):
    """``conda clean --index-cache`` removes only the index cache."""
    _populate_caches(conda)
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=True)

    # Execute
    result = conda("clean", "--index-cache").assert_ok()

    # Verify: index cache removed, other caches untouched
    _assert_cache_state(cache_dir, index_cache=False, tarballs=True, extracted=True)

    # Verify output message
    assert re.search(
        r"Will remove \d+ index cache\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_tarballs(conda, cache_dir):
    """``conda clean --tarballs`` removes only cached package tarballs."""
    _populate_caches(conda)
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=True)

    # Execute
    result = conda("clean", "--tarballs").assert_ok()

    # Verify: tarballs removed, other caches untouched
    _assert_cache_state(cache_dir, index_cache=True, tarballs=False, extracted=True)

    # Verify output message (format: "Will remove N (SIZE) tarball(s).")
    assert re.search(
        r"Will remove \d+.*tarball\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_packages(conda, cache_dir):
    """``conda clean --packages`` removes only unused extracted packages."""
    _populate_caches(conda, orphan_packages=True)
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=True)

    # Execute
    result = conda("clean", "--packages").assert_ok()

    # Verify: extracted packages removed, other caches untouched
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=False)

    # Verify output message (format: "Will remove N (SIZE) package(s).")
    assert re.search(
        r"Will remove \d+.*package\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_force_pkgs_dirs(conda, cache_dir):
    """``conda clean --force-pkgs-dirs`` removes the entire writable pkgs_dir.

    Unlike test_clean_all, the env is intentionally kept live to prove
    --force-pkgs-dirs removes even in-use packages. It deletes the whole
    pkgs_dir (tarballs, extracted packages, and the index cache alike).
    """
    # Setup: populate caches (env kept live intentionally)
    _populate_caches(conda)
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=True)

    # Execute
    result = conda("clean", "--force-pkgs-dirs").assert_ok()

    # Verify: the entire pkgs_dir is gone, index cache included
    _assert_cache_state(cache_dir, index_cache=False, tarballs=False, extracted=False)

    # Verify output message
    assert re.search(
        r"Will remove \d+ package cache\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_all(conda):
    """``conda clean --all`` cleans index cache and tarballs.

    Whether conda also removes the still-live env's extracted packages depends
    on the platform's linking strategy (conda only detects a package as "in
    use" via a hardlink refcount, which some filesystems/CI runners don't
    preserve), so this doesn't assert on the packages message either way --
    only on the parts of --all that are guaranteed regardless of linking: the
    index cache and tarballs are never considered "in use" and are always
    removed.
    """
    _populate_caches(conda, orphan_packages=False)

    # Execute
    result = conda("clean", "--all").assert_ok()

    # Verify output messages
    output = result.stdout
    assert re.search(r"Will remove \d+ index cache\(s\)\.", output), (
        f"Expected index cache removal message. Got:\n{output}"
    )
    assert re.search(r"Will remove \d+.*tarball\(s\)\.", output), (
        f"Expected tarball removal message. Got:\n{output}"
    )


def test_clean_all_idempotent(conda, cache_dir):
    """``conda clean --all`` run again reports nothing left to remove.

    First run orphans (env removed) and removes everything; the second run's
    job is to prove --all correctly reports "nothing to do" across all
    targets once there's genuinely nothing left, rather than erroring or
    re-reporting removals.
    """
    _populate_caches(conda, orphan_packages=True)

    # First run: removes tarballs, index cache, and the now-orphaned packages.
    conda("clean", "--all").assert_ok()
    _assert_cache_state(cache_dir, index_cache=False, tarballs=False, extracted=False)

    # Second run: everything above is already gone.
    result = conda("clean", "--all").assert_ok()
    output = result.stdout
    assert "There are no unused tarball(s) to remove." in output, (
        f"Expected no-tarballs message. Got:\n{output}"
    )
    assert "There are no index cache(s) to remove." in output, (
        f"Expected no-index-cache message. Got:\n{output}"
    )
    assert "There are no unused package(s) to remove." in output, (
        f"Expected no-orphan-packages message. Got:\n{output}"
    )


def test_clean_dry_run(conda, cache_dir):
    """``conda clean --all --dry-run`` shows what would be removed without removing."""
    _populate_caches(conda, orphan_packages=True)
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=True)

    # Execute
    result = conda("clean", "--all", "--dry-run").assert_ok()

    # Verify: nothing was actually removed
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=True)

    # Verify output indicates dry run
    assert "DryRunExit" in result.stderr or "Dry run" in result.stderr, (
        f"Output should indicate dry run. Got:\n{result.stderr}"
    )


def test_clean_json(conda, cache_dir):
    """``conda clean --all --json`` reports removal as structured JSON."""
    _populate_caches(conda, orphan_packages=True)
    _assert_cache_state(cache_dir, index_cache=True, tarballs=True, extracted=True)

    # Execute
    result = conda("clean", "--all", "--json").assert_ok()

    # Verify: all caches removed
    _assert_cache_state(cache_dir, index_cache=False, tarballs=False, extracted=False)

    # Verify output is valid JSON with the expected structure
    payload = result.json()
    assert payload["success"] is True, f"Expected success: true. Got:\n{payload}"
    assert "tarballs" in payload, f"Expected 'tarballs' key in JSON. Got:\n{payload}"
    assert "pkg_sizes" in payload["tarballs"], f"Expected 'pkg_sizes' key. Got:\n{payload}"
    assert "index_cache" in payload, f"Expected 'index_cache' key in JSON. Got:\n{payload}"
    assert "packages" in payload, f"Expected 'packages' key in JSON. Got:\n{payload}"


def test_clean_console_classic_prompts_for_confirmation(conda, cache_dir):
    """``conda clean --index-cache --console classic`` prompts and aborts on "no".

    The ``classic`` backend renders an interactive confirmation prompt. Declining it
    must leave the index cache untouched.
    """
    _populate_index_cache(conda)
    assert _has_index_cache(cache_dir), "Index cache should exist"

    # Execute: decline the confirmation prompt, with the fixture's auto-yes overridden off
    result = conda(
        "clean",
        "--index-cache",
        "--console",
        "classic",
        extra_env={"CONDA_ALWAYS_YES": "no"},
        stdin="no\n",
    )

    # Verify: prompt shown, nothing removed
    assert "Proceed ([y]/n)?" in result.stdout, (
        f"Expected a confirmation prompt. Got:\n{result.stdout}"
    )
    assert _has_index_cache(cache_dir), "Index cache should NOT be removed when declined"


def test_clean_console_json_skips_confirmation(conda, cache_dir):
    """``conda clean --index-cache --console json`` proceeds without prompting.

    Even with auto-yes disabled and no stdin available to answer a prompt, the
    ``json`` backend never blocks on confirmation and just proceeds.
    """
    _populate_index_cache(conda)
    assert _has_index_cache(cache_dir), "Index cache should exist"

    # Execute: auto-yes disabled, no stdin available to answer a prompt
    result = conda(
        "clean",
        "--index-cache",
        "--console",
        "json",
        extra_env={"CONDA_ALWAYS_YES": "no"},
    ).assert_ok()

    # Verify: removed without ever prompting
    assert "Proceed ([y]/n)?" not in result.stdout, (
        f"--console json should not prompt for confirmation. Got:\n{result.stdout}"
    )
    assert not _has_index_cache(cache_dir), "Index cache should be removed"


def test_clean_console_invalid_rejected(conda, cache_dir):
    """``conda clean --index-cache --console <invalid>`` rejects the unknown backend."""
    _populate_index_cache(conda)
    assert _has_index_cache(cache_dir), "Index cache should exist"

    # Execute
    result = conda("clean", "--index-cache", "--console", "not-a-real-backend")

    # Verify: rejected at the argument-parsing stage, nothing removed
    result.assert_error(
        code=2,
        contains="argument --console: invalid choice: 'not-a-real-backend'",
    )
    assert _has_index_cache(cache_dir), "Index cache should NOT be removed on failure"


def test_clean_logfiles(conda, cache_dir):
    """``conda clean --logfiles`` removes log files, leaving other caches untouched."""
    # Setup: populate the package cache so it's recognized as writable
    _populate_caches(conda)
    assert _has_tarballs(cache_dir), "Tarballs should exist after install"

    logs_dir = cache_dir / ".logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / "test-package-1.0-0.log"
    logfile.write_text("dummy log content")

    assert logfile.exists(), "Logfile should exist before clean"

    # Execute
    result = conda("clean", "--logfiles").assert_ok()

    # Verify: logfile removed, other cache contents untouched
    assert not logfile.exists(), "Logfile should be removed"
    assert _has_tarballs(cache_dir), "Tarballs should NOT be removed by --logfiles"

    # Verify output message
    assert re.search(
        r"Will remove \d+ logfile\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


def test_clean_logfiles_empty(conda):
    """``conda clean --logfiles`` with no log files to remove succeeds."""
    result = conda("clean", "--logfiles").assert_ok()
    assert "There are no logfile(s) to remove" in result.stdout, (
        f"Output should indicate no logfiles. Got:\n{result.stdout}"
    )


def test_clean_tempfiles_removes_tmp_files_only(conda, tmp_path):
    """``conda clean --tempfiles`` removes only ``.c~``/``.trash`` files at the given path."""
    tempfile_c = tmp_path / "some-package.c~"
    tempfile_trash = tmp_path / "some-package.trash"
    regular_file = tmp_path / "regular-file.txt"
    tempfile_c.write_text("dummy tempfile content")
    tempfile_trash.write_text("dummy tempfile content")
    regular_file.write_text("not a tempfile")

    assert tempfile_c.exists(), "Tempfile should exist before clean"
    assert tempfile_trash.exists(), "Tempfile should exist before clean"
    assert regular_file.exists(), "Regular file should exist before clean"

    # Execute
    result = conda("clean", "--tempfiles", str(tmp_path)).assert_ok()

    # Verify: tempfiles removed, regular file left alone
    assert not tempfile_c.exists(), "Tempfile (.c~) should be removed"
    assert not tempfile_trash.exists(), "Tempfile (.trash) should be removed"
    assert regular_file.exists(), "Regular file should NOT be removed"

    # Verify output message
    assert re.search(
        r"Will remove \d+ tempfile\(s\)\.",
        result.stdout,
    ), f"Expected removal message. Got:\n{result.stdout}"


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
