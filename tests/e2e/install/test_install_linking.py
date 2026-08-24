# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Package Linking and Install-time options."""

from __future__ import annotations

import re
import sys
from textwrap import dedent

import pytest
from helpers import PACKAGE_NAME, list_installed_packages
from install_asserts import (
    assert_package_present,
    assert_package_unpacked,
    require_python_version,
)

from conda_e2e.utils import env_prefix, site_packages_dir, unique_env_name


@pytest.mark.skipif(sys.platform == "win32", reason="st_nlink unreliable on Windows")
def test_install_copy_creates_file_copies(conda, cache_dir, empty_env, envs_dir):
    """``conda install --copy`` creates file copies instead of hardlinks."""
    env_name, env_path = empty_env

    # Install normally to baseline env to populate cache and verify hardlinks work
    baseline_env = unique_env_name()
    conda("create", "-n", baseline_env).assert_ok()
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
    baseline_path = env_prefix(envs_dir, baseline_env)
    baseline_site = site_packages_dir(baseline_path, baseline_py)
    baseline_init = baseline_site / PACKAGE_NAME / "__init__.py"

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

    site_packages = site_packages_dir(env_path, py_version)
    init_file = site_packages / PACKAGE_NAME / "__init__.py"

    # With --copy: different inode proves file was copied, not hardlinked
    assert init_file.stat().st_ino != cache_ino, (
        f"With --copy, file should have different inode from cache (was linked, not copied). "
        f"File inode: {init_file.stat().st_ino}, Cache inode: {cache_ino}"
    )
    assert init_file.stat().st_nlink == 1, (
        f"With --copy, file should have link count of 1. Got: {init_file.stat().st_nlink}"
    )


def test_install_clobber_suppresses_overlap_warning(conda, empty_env, condarc):
    """``conda install --clobber`` overwrites overlapping files without ClobberWarning."""
    env_name, env_path = empty_env
    # conda-forge packages that ship overlapping files; used to exercise --clobber.
    clobber_packages = ("jpeg", "libjpeg-turbo")
    condarc.write_text(
        dedent("""\
        channels:
          - conda-forge
        path_conflict: warn
        """)
    )

    # Baseline: without --clobber, the overlapping packages warn
    baseline_env = unique_env_name()
    conda("create", "-n", baseline_env).assert_ok()
    baseline = conda("install", "-n", baseline_env, *clobber_packages).assert_ok()
    assert "ClobberWarning" in baseline.stderr, (
        f"Without --clobber, overlapping packages should emit ClobberWarning. "
        f"Got stderr:\n{baseline.stderr[:500]}"
    )
    # The warning names a shared path (e.g. bin/cjpeg) relative to the prefix on
    # every platform; reusing it keeps the physical-state check portable.
    path_match = re.search(r"path: '([^']+)'", baseline.stderr)
    assert path_match, (
        f"ClobberWarning should name the shared path. Got stderr:\n{baseline.stderr[:500]}"
    )
    shared_path = path_match.group(1)

    # Execute: with --clobber, the warning is suppressed
    result = conda("install", "-n", env_name, "--clobber", *clobber_packages).assert_ok()
    assert "ClobberWarning" not in result.stderr, (
        f"--clobber should suppress ClobberWarning. Got stderr:\n{result.stderr[:500]}"
    )

    # Verify both packages are installed and the clobbered file physically exists
    installed = list_installed_packages(conda, "-n", env_name)
    for package in clobber_packages:
        assert_package_present(installed, package, env_name)
    assert (env_path / shared_path).exists(), (
        f"--clobber should write the overlapping file {shared_path!r} into {env_path}"
    )
