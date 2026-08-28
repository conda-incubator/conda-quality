# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Package Linking and Install-time options."""

from __future__ import annotations

import sys
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from helpers import PACKAGE_NAME, list_installed_packages
from install_asserts import (
    assert_package_present,
    assert_package_unpacked,
    package_init_file,
    require_python_version,
)

if TYPE_CHECKING:
    from pathlib import Path

# conda-forge packages that ship overlapping files; used to exercise --clobber.
CLOBBER_PACKAGES = ("jpeg", "libjpeg-turbo")


def _write_clobber_condarc(condarc: Path, path_conflict: str) -> None:
    """Write a .condarc selecting conda-forge and the given path_conflict mode."""
    condarc.write_text(
        dedent(f"""\
        channels:
          - conda-forge
        path_conflict: {path_conflict}
        """)
    )


@pytest.mark.skipif(sys.platform == "win32", reason="st_nlink unreliable on Windows")
def test_install_copy_creates_file_copies(conda, cache_dir, empty_env, make_env):
    """``conda install --copy`` creates file copies instead of hardlinks."""
    env_name, env_path = empty_env

    # Install normally to baseline env to populate cache and verify hardlinks work
    baseline_env, baseline_path = make_env()
    conda("install", "-n", baseline_env, PACKAGE_NAME).assert_ok()

    # Find the cache file (source for hardlinks)
    cache_files = list(cache_dir.glob(f"**/{PACKAGE_NAME}/__init__.py"))
    assert cache_files, f"Cache should contain {PACKAGE_NAME}/__init__.py after install"
    cache_file = cache_files[0]
    cache_ino = cache_file.stat().st_ino

    # Verify baseline is hardlinked to cache (same inode)
    baseline_installed = list_installed_packages(conda, "-n", baseline_env)
    assert_package_present(baseline_installed, PACKAGE_NAME, baseline_env)
    baseline_py = require_python_version(baseline_installed)
    baseline_init = package_init_file(baseline_path, PACKAGE_NAME, baseline_py)

    if baseline_init.stat().st_ino != cache_ino:
        pytest.skip(
            "Baseline did not hardlink to cache; --copy test meaningless on this filesystem"
        )

    # Install with --copy into the test env
    conda("install", "-n", env_name, "--copy", PACKAGE_NAME).assert_ok()

    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    py_version = require_python_version(installed)
    assert_package_unpacked(env_path, PACKAGE_NAME, py_version)

    init_file = package_init_file(env_path, PACKAGE_NAME, py_version)

    # With --copy: different inode proves file was copied, not hardlinked
    assert init_file.stat().st_ino != cache_ino, (
        f"With --copy, file should have different inode from cache (was linked, not copied). "
        f"File inode: {init_file.stat().st_ino}, Cache inode: {cache_ino}"
    )
    assert init_file.stat().st_nlink == 1, (
        f"With --copy, file should have link count of 1. Got: {init_file.stat().st_nlink}"
    )


def test_install_clobber_suppresses_overlap_warning(conda, empty_env, make_env, condarc):
    """``conda install --clobber`` overwrites overlapping files without ClobberWarning."""
    env_name, _ = empty_env
    _write_clobber_condarc(condarc, path_conflict="warn")

    # Baseline: without --clobber, the overlapping packages warn (but still install,
    # since path_conflict: warn overwrites the shared files regardless of --clobber).
    baseline_env, _ = make_env()
    baseline = conda("install", "-n", baseline_env, *CLOBBER_PACKAGES).assert_ok()
    assert "ClobberWarning" in baseline.stderr, (
        f"Without --clobber, overlapping packages should emit ClobberWarning. "
        f"Got stderr:\n{baseline.stderr[:500]}"
    )

    # Execute: with --clobber, the warning is suppressed
    result = conda("install", "-n", env_name, "--clobber", *CLOBBER_PACKAGES).assert_ok()
    assert "ClobberWarning" not in result.stderr, (
        f"--clobber should suppress ClobberWarning. Got stderr:\n{result.stderr[:500]}"
    )

    # Verify both packages are installed
    installed = list_installed_packages(conda, "-n", env_name)
    for package in CLOBBER_PACKAGES:
        assert_package_present(installed, package, env_name)


def test_install_clobber_overrides_path_conflict_prevent(conda, empty_env, make_env, condarc):
    """``conda install --clobber`` succeeds where ``path_conflict: prevent`` would block."""
    env_name, _ = empty_env
    # path_conflict: prevent makes the overlap fatal instead of just a warning --
    # this is the setting --clobber must actually override, not merely a noisier warning.
    _write_clobber_condarc(condarc, path_conflict="prevent")

    # Baseline: without --clobber, path_conflict: prevent refuses to overwrite and fails
    baseline_env, _ = make_env()
    baseline = conda("install", "-n", baseline_env, *CLOBBER_PACKAGES)
    baseline.assert_error(code=1, contains="ClobberError")

    # Execute: --clobber overrides path_conflict: prevent and installs successfully
    conda("install", "-n", env_name, "--clobber", *CLOBBER_PACKAGES).assert_ok()

    # Verify both packages are installed despite path_conflict: prevent
    installed = list_installed_packages(conda, "-n", env_name)
    for package in CLOBBER_PACKAGES:
        assert_package_present(installed, package, env_name)
