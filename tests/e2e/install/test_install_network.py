# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Networking options."""

from __future__ import annotations

from helpers import PACKAGE_NAME, list_installed_packages
from install_asserts import (
    assert_install_output_has_new_packages,
    assert_package_present,
    assert_package_unpacked,
    require_python_version,
)


def test_install_offline_uses_cached_packages(conda, empty_env):
    """``conda install --offline`` installs from cache populated by ``--download-only``."""
    env_name, env_path = empty_env

    download_result = conda("install", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()
    assert "CondaExitZero" in download_result.stderr, (
        f"--download-only should trigger CondaExitZero exit path. "
        f"Got stderr:\n{download_result.stderr}"
    )

    after_download = list_installed_packages(conda, "-n", env_name)
    assert PACKAGE_NAME not in after_download, (
        f"{PACKAGE_NAME} should NOT be installed after --download-only. Got: {after_download.names}"
    )

    result = conda("install", "-n", env_name, "--offline", PACKAGE_NAME).assert_ok()

    assert_install_output_has_new_packages(result, PACKAGE_NAME)

    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_offline_fails_when_package_not_cached(conda, empty_env):
    """``conda install --offline`` fails when the package is not in cache."""
    env_name, _ = empty_env

    uncached_pkg = "totally-obscure-package-xyz123"

    result = conda("install", "-n", env_name, "--offline", uncached_pkg)
    result.assert_error(code=1, contains="PackagesNotFoundInChannelsError")
