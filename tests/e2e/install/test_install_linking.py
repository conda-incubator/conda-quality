# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Package Linking and Install-time options."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from helpers import PACKAGE_NAME, list_installed_packages
from install_asserts import (
    assert_package_present,
    assert_package_unpacked,
    require_python_version,
)

from conda_e2e.utils import package_init_file

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


def _filesystem_supports_hardlinks(tmp_path: Path) -> bool:
    """Check if the filesystem supports hardlinks, independent of conda."""
    src = tmp_path / "hardlink_test_src"
    dst = tmp_path / "hardlink_test_dst"
    src.write_bytes(b"test")
    try:
        dst.hardlink_to(src)
        return dst.samefile(src)
    except (OSError, NotImplementedError):
        return False
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)


def test_install_copy_creates_file_copies(conda, cache_dir, make_env, tmp_path):
    """``conda install --copy`` creates file copies instead of hardlinks."""
    # Skip only if filesystem doesn't support hardlinks (independent of conda)
    if not _filesystem_supports_hardlinks(tmp_path):
        pytest.skip("Filesystem does not support hardlinks")

    env_name, env_path = make_env()

    # Install normally to baseline env to populate cache and verify hardlinks work
    baseline_env, baseline_path = make_env()
    conda("install", "-n", baseline_env, PACKAGE_NAME).assert_ok()

    # Find the cache file (source for hardlinks)
    cache_files = list(cache_dir.glob(f"**/{PACKAGE_NAME}/__init__.py"))
    assert cache_files, f"Cache should contain {PACKAGE_NAME}/__init__.py after install"
    cache_file = cache_files[0]

    # Verify baseline is hardlinked to cache - if not, conda regressed (fail, don't skip)
    baseline_installed = list_installed_packages(conda, "-n", baseline_env)
    assert_package_present(baseline_installed, PACKAGE_NAME, baseline_env)
    baseline_py_ver = require_python_version(baseline_installed)
    baseline_init = package_init_file(baseline_path, PACKAGE_NAME, baseline_py_ver)

    assert baseline_init.samefile(cache_file), (
        "conda should hardlink to cache by default, but created a copy instead"
    )

    # Install with --copy into the test env
    conda("install", "-n", env_name, "--copy", PACKAGE_NAME).assert_ok()

    installed = list_installed_packages(conda, "-n", env_name)
    copied_py_ver = require_python_version(installed)
    assert_package_unpacked(env_path, PACKAGE_NAME, copied_py_ver)

    init_file = package_init_file(env_path, PACKAGE_NAME, copied_py_ver)

    # Cross-platform: samefile() returns False for copies (different files)
    assert not init_file.samefile(cache_file), (
        "--copy should create independent file, not hardlink to cache"
    )

    # Content integrity: copied file should have same content as cache
    assert init_file.read_bytes() == cache_file.read_bytes(), (
        "--copy should produce file with identical content to cache"
    )


def test_install_clobber_suppresses_overlap_warning(conda, make_env, condarc):
    """``conda install --clobber`` overwrites overlapping files without ClobberWarning."""
    env_name, _ = make_env()
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


def test_install_clobber_overrides_path_conflict_prevent(conda, make_env, condarc):
    """``conda install --clobber`` succeeds where ``path_conflict: prevent`` would block."""
    env_name, _ = make_env()
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
