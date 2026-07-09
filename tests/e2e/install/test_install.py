# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install command."""

from __future__ import annotations

import pytest
from packaging.version import Version

from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import site_packages_dir

NEW_PACKAGES_INSTALLED = "The following NEW packages will be INSTALLED:"

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.parametrize("use_path", [False, True], ids=["name", "path"])
def test_install_package(conda, empty_env, use_path):
    """``conda install`` by env name or path installs flask and it appears in ``conda list``."""
    env_name, env_path = empty_env
    target = str(env_path) if use_path else env_name
    flag = "-p" if use_path else "-n"

    # Execute: install flask into the env
    result = conda("install", flag, target, "flask").assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert "flask" in result.stdout, f"Install output should mention flask. Got:\n{result.stdout}"

    # Verify flask appears in conda list
    list_result = conda("list", flag, target).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert "flask" in installed, (
        f"flask should be present in {target} after install. Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    python = installed.get("python")
    assert python is not None, "python should be installed as a flask dependency"
    site_packages = site_packages_dir(env_path, python.version)
    assert (site_packages / "flask").is_dir(), (
        f"flask package directory should exist on disk at {site_packages}"
    )


def test_install_multiple_packages(conda, empty_env):
    """``conda install click six`` installs multiple packages at once."""
    env_name, _ = empty_env

    # Execute: install multiple packages in one command
    result = conda("install", "-n", env_name, "click", "six").assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify all packages appear in conda list
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    for pkg in ("click", "six"):
        assert pkg in installed, (
            f"{pkg} should be present in {env_name} after install. "
            f"Installed packages: {installed.names}"
        )


def test_install_from_conda_forge(conda, empty_env):
    """``conda install -c conda-forge <package>`` installs from the conda-forge channel."""
    env_name, _ = empty_env

    # Execute: install boltons from conda-forge
    result = conda("install", "-n", env_name, "-c", "conda-forge", "boltons").assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify boltons is installed and came from conda-forge
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert "boltons" in installed, (
        f"boltons should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get("boltons")
    assert record is not None, "boltons record should be found in conda list"
    assert record.channel == "conda-forge", (
        f"boltons should come from conda-forge. Got channel: {record.channel}"
    )


def test_install_override_channels(conda, empty_env):
    """``conda install -c conda-forge --override-channels <pkg>`` ignores default channels."""
    env_name, _ = empty_env

    # Execute: install httpx from conda-forge only, ignoring defaults
    result = conda(
        "install",
        "-n",
        env_name,
        "-c",
        "conda-forge",
        "--override-channels",
        "httpx",
    ).assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify httpx is installed and came from conda-forge
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert "httpx" in installed, (
        f"httpx should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get("httpx")
    assert record is not None, "httpx record should be found in conda list"
    assert record.channel == "conda-forge", (
        f"httpx should come from conda-forge. Got channel: {record.channel}"
    )


def test_install_specific_version(conda, empty_env):
    """``conda install flask=<version>`` installs the exact pinned (non-latest) version."""
    env_name, _ = empty_env

    # Setup: resolve available flask versions and pin to one that is NOT the
    # latest, so a solver that ignores the pin and grabs the latest anyway
    # would make this test fail (pinning to the latest could not tell the
    # two cases apart). Sort semantically since version strings don't sort
    # correctly as plain text (e.g. "2.10.0" < "2.9.0" lexicographically).
    search_result = conda("search", "flask", "--json").assert_ok()
    versions = sorted(
        {p["version"] for p in search_result.json().get("flask", [])},
        key=Version,
    )
    assert len(versions) >= 2, "need at least 2 flask versions to verify pinning is respected"
    pinned_version = versions[-2]

    # Execute: install the pinned version
    result = conda("install", "-n", env_name, f"flask={pinned_version}").assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert "flask" in result.stdout, f"Install output should mention flask. Got:\n{result.stdout}"

    # Verify the exact pinned version is installed
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert "flask" in installed, (
        f"flask should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get("flask")
    assert record is not None, "flask record should be found in conda list"
    assert record.version == pinned_version, (
        f"flask version should be {pinned_version}. Got: {record.version}"
    )


def test_install_no_deps(conda, empty_env):
    """``conda install --no-deps flask`` installs only flask, no dependencies."""
    env_name, _ = empty_env

    # Execute: install flask without dependencies
    result = conda("install", "-n", env_name, "--no-deps", "flask").assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert "flask" in result.stdout, f"Install output should mention flask. Got:\n{result.stdout}"

    # Verify flask is the only package installed (env started empty, so no
    # dependency names need to be hardcoded here)
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert installed.names == ("flask",), (
        f"--no-deps should install only flask. Installed packages: {installed.names}"
    )


def test_install_dry_run(conda, empty_env):
    """``conda install --dry-run`` shows what would be installed without making changes."""
    env_name, env_path = empty_env
    files_before = sorted(str(p) for p in env_path.rglob("*"))

    # Execute: dry-run install of flask
    result = conda("install", "-n", env_name, "--dry-run", "flask").assert_ok()

    # Verify output indicates dry run and lists flask
    assert "DryRunExit" in result.stderr or "Dry run" in result.stderr, (
        f"Output should indicate dry run. Got:\n{result.stderr}"
    )
    assert "flask" in result.stdout, (
        f"Dry-run output should mention flask as a candidate. Got:\n{result.stdout}"
    )

    # Verify flask was not installed in conda's metadata
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert "flask" not in installed, (
        f"flask should NOT be installed after a dry run. Installed packages: {installed.names}"
    )

    # Verify nothing was written to disk either (not just absent from metadata)
    files_after = sorted(str(p) for p in env_path.rglob("*"))
    assert files_after == files_before, (
        f"dry run should not write any files to {env_path}. "
        f"Before: {files_before}, after: {files_after}"
    )


def test_install_reports_full_details(conda, empty_env):
    """``conda install`` output reports the channel, platform, and environment location."""
    env_name, env_path = empty_env

    result = conda("install", "-n", env_name, "flask").assert_ok()

    assert f"environment location: {env_path}" in result.stdout, (
        f"Install output should report the environment location. Got:\n{result.stdout}"
    )
    assert "Platform:" in result.stdout, (
        f"Install output should report the platform. Got:\n{result.stdout}"
    )
    assert "Channels:" in result.stdout, (
        f"Install output should report the channels. Got:\n{result.stdout}"
    )


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.parametrize(
    ("args", "expected_code", "expected_message"),
    [
        (("totally-fake-package-xyz123",), 1, "PackagesNotFoundInChannelsError"),
        ((), 1, "too few arguments"),
        (("--invalid-flag", "flask"), 2, "unrecognized arguments: --invalid-flag"),
    ],
    ids=["nonexistent-package", "no-packages", "invalid-flag"],
)
def test_install_fails(conda, empty_env, args, expected_code, expected_message):
    """``conda install`` fails with the expected exit code and message."""
    env_name, _ = empty_env

    result = conda("install", "-n", env_name, *args)
    result.assert_error(code=expected_code, contains=expected_message, stream="stderr")


def test_install_nonexistent_env_fails(conda):
    """``conda install -n <nonexistent-env>`` fails with an environment-not-found error."""
    result = conda("install", "-n", "totally-nonexistent-env-xyz", "flask")
    result.assert_error(code=1, contains="EnvironmentLocationNotFound", stream="stderr")
