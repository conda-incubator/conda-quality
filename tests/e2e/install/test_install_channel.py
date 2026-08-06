# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Channel Customization options."""

from __future__ import annotations

from helpers import PACKAGE_NAME, list_installed_packages
from install_asserts import (
    assert_install_output_has_new_packages,
    assert_package_present,
    assert_package_unpacked,
    python_version,
    require_installed_record,
)


def test_install_from_conda_forge(conda, empty_env):
    """``conda install -c conda-forge <package>`` installs from the conda-forge channel."""
    env_name, env_path = empty_env

    # Execute: install flask from conda-forge
    result = conda("install", "-n", env_name, "-c", "conda-forge", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify flask is installed and came from conda-forge
    installed = list_installed_packages(conda, "-n", env_name, as_json=True)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    record = require_installed_record(installed, PACKAGE_NAME)
    assert record.channel == "conda-forge", (
        f"{PACKAGE_NAME} should come from conda-forge. Got channel: {record.channel}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    assert_package_unpacked(env_path, PACKAGE_NAME, python_version(installed))


def test_install_override_channels_excludes_defaults(conda, empty_env):
    """``conda install -c conda-forge --override-channels <pkg>`` excludes defaults."""
    env_name, env_path = empty_env
    package_name = "neo4j"

    # defaults is excluded, and since neo4j isn't on conda-forge either, the
    # install must fail, leaving the env untouched.
    failure = conda(
        "install",
        "-n",
        env_name,
        "-c",
        "conda-forge",
        "--override-channels",
        package_name,
    )
    failure.assert_error(code=1, contains="PackagesNotFoundInChannelsError")
    assert not list(env_path.glob("lib/python*")), (
        f"a failed install should not unpack any packages at {env_path}"
    )
    assert not (env_path / "Lib").exists(), (
        f"a failed install should not unpack any packages at {env_path}"
    )


def test_install_channel_fallback_to_defaults(conda, empty_env):
    """``conda install -c conda-forge <pkg>`` falls back to defaults when absent."""
    env_name, env_path = empty_env
    package_name = "neo4j"
    channel_name = "pkgs/main"

    # conda-forge is preferred but neo4j isn't there, so it falls back to
    # defaults and the install succeeds.
    result = conda("install", "-n", env_name, "-c", "conda-forge", package_name).assert_ok()

    assert_install_output_has_new_packages(result)
    installed = list_installed_packages(conda, "-n", env_name, as_json=True)
    assert_package_present(installed, package_name, env_name)
    record = require_installed_record(installed, package_name)
    assert record.channel == channel_name, (
        f"{package_name} should come from defaults ({channel_name}). Got channel: {record.channel}"
    )

    # Verify neo4j is physically present on disk, not just in conda-meta
    assert_package_unpacked(env_path, package_name, python_version(installed))
