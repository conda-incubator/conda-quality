# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Channel Customization options."""

from __future__ import annotations

from conda_e2e.parsers.list import PackageList

from .helpers import assert_package_unpacked, python_version

NEW_PKG_INSTALLED_MSG = "The following NEW packages will be INSTALLED:"
PACKAGE_NAME = "flask"


def test_install_from_conda_forge(conda, empty_env):
    """``conda install -c conda-forge <package>`` installs from the conda-forge channel."""
    env_name, env_path = empty_env

    # Execute: install flask from conda-forge
    result = conda("install", "-n", env_name, "-c", "conda-forge", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify flask is installed and came from conda-forge
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get(PACKAGE_NAME)
    assert record is not None, f"{PACKAGE_NAME} record should be found in conda list"
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

    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert package_name in installed, (
        f"{package_name} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get(package_name)
    assert record is not None, f"{package_name} record should be found in conda list"
    assert record.channel == channel_name, (
        f"{package_name} should come from defaults ({channel_name}). Got channel: {record.channel}"
    )

    # Verify neo4j is physically present on disk, not just in conda-meta
    assert_package_unpacked(env_path, package_name, python_version(installed))
