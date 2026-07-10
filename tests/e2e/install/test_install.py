# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install command."""

from __future__ import annotations

import pytest
from packaging.version import Version

from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import site_packages_dir

NEW_PACKAGES_INSTALLED = "The following NEW packages will be INSTALLED:"
FLASK = "flask"

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
    result = conda("install", flag, target, FLASK).assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert FLASK in result.stdout, f"Install output should mention flask. Got:\n{result.stdout}"

    # Verify flask appears in conda list
    list_result = conda("list", flag, target).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert FLASK in installed, (
        f"flask should be present in {target} after install. Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    python = installed.get("python")
    assert python is not None, "python should be installed as a flask dependency"
    site_packages = site_packages_dir(env_path, python.version)
    assert (site_packages / FLASK / "__init__.py").is_file(), (
        f"flask should be unpacked on disk at {site_packages}"
    )


def test_install_multiple_packages(conda, empty_env):
    """``conda install click six`` installs multiple packages at once."""
    env_name, env_path = empty_env

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

    # Verify both are physically present on disk, not just in conda-meta.
    # click is a package (dir with __init__.py); six is a single module file.
    python = installed.get("python")
    assert python is not None, "python should be installed as a dependency"
    site_packages = site_packages_dir(env_path, python.version)
    assert (site_packages / "click" / "__init__.py").is_file(), (
        f"click should be unpacked on disk at {site_packages}"
    )
    assert (site_packages / "six.py").is_file(), (
        f"six should be unpacked on disk at {site_packages}"
    )


def test_install_from_conda_forge(conda, empty_env):
    """``conda install -c conda-forge <package>`` installs from the conda-forge channel."""
    env_name, env_path = empty_env

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

    # Verify boltons is physically present on disk, not just in conda-meta
    python = installed.get("python")
    assert python is not None, "python should be installed as a dependency"
    site_packages = site_packages_dir(env_path, python.version)
    assert (site_packages / "boltons" / "__init__.py").is_file(), (
        f"boltons should be unpacked on disk at {site_packages}"
    )


def test_install_override_channels(conda, empty_env):
    """``conda install -c conda-forge --override-channels <pkg>`` ignores default channels."""
    env_name, env_path = empty_env

    # With --override-channels: defaults is excluded, and since neo4j isn't
    # on conda-forge either, the install must fail, leaving the env untouched.
    failure = conda(
        "install",
        "-n",
        env_name,
        "-c",
        "conda-forge",
        "--override-channels",
        "neo4j",
    )
    failure.assert_error(code=1, contains="PackagesNotFoundInChannelsError")
    assert not list(env_path.glob("lib/python*")), (
        f"a failed install should not unpack any packages at {env_path}"
    )
    assert not (env_path / "Lib").exists(), (
        f"a failed install should not unpack any packages at {env_path}"
    )

    # Without --override-channels: conda-forge is preferred but neo4j isn't
    # there, so it falls back to defaults and the install now succeeds.
    result = conda("install", "-n", env_name, "-c", "conda-forge", "neo4j").assert_ok()

    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert "neo4j" in installed, (
        f"neo4j should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )

    # Verify neo4j is physically present on disk, not just in conda-meta
    python = installed.get("python")
    assert python is not None, "python should be installed as a dependency"
    site_packages = site_packages_dir(env_path, python.version)
    assert (site_packages / "neo4j" / "__init__.py").is_file(), (
        f"neo4j should be unpacked on disk at {site_packages}"
    )


def test_install_specific_version(conda, empty_env):
    """``conda install flask=<version>`` installs the exact pinned (non-latest) version."""
    env_name, env_path = empty_env

    search_result = conda("search", FLASK, "--json").assert_ok()
    versions = sorted(
        {p["version"] for p in search_result.json().get(FLASK, [])},
        key=Version,
    )
    assert len(versions) >= 2, "need at least 2 flask versions to verify pinning is respected"
    pinned_version = versions[-2]

    # Execute: install the pinned version
    result = conda("install", "-n", env_name, f"{FLASK}={pinned_version}").assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert FLASK in result.stdout, f"Install output should mention flask. Got:\n{result.stdout}"

    # Verify the exact pinned version is installed
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert FLASK in installed, (
        f"flask should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get(FLASK)
    assert record is not None, "flask record should be found in conda list"
    assert record.version == pinned_version, (
        f"flask version should be {pinned_version}. Got: {record.version}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    python = installed.get("python")
    assert python is not None, "python should be installed as a flask dependency"
    site_packages = site_packages_dir(env_path, python.version)
    assert (site_packages / FLASK / "__init__.py").is_file(), (
        f"flask should be unpacked on disk at {site_packages}"
    )


def test_install_no_deps(conda, empty_env):
    """``conda install --no-deps flask`` installs only flask, no dependencies."""
    env_name, env_path = empty_env

    # Execute: install flask without dependencies
    result = conda("install", "-n", env_name, "--no-deps", FLASK).assert_ok()

    # Verify output message
    assert NEW_PACKAGES_INSTALLED in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert FLASK in result.stdout, f"Install output should mention flask. Got:\n{result.stdout}"

    # Verify flask is the only package installed (env started empty)
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert installed.names == (FLASK,), (
        f"--no-deps should install only flask. Installed packages: {installed.names}"
    )

    site_packages = site_packages_dir(env_path)
    assert (site_packages / FLASK / "__init__.py").is_file(), (
        f"flask should be unpacked on disk at {site_packages}"
    )


def test_install_dry_run(conda, empty_env):
    """``conda install --dry-run`` shows what would be installed without making changes."""
    env_name, env_path = empty_env
    files_before = sorted(str(p) for p in env_path.rglob("*"))

    # Execute: dry-run install of flask
    result = conda("install", "-n", env_name, "--dry-run", FLASK).assert_ok()

    # Verify output indicates dry run and lists flask
    assert "DryRunExit" in result.stderr or "Dry run" in result.stderr, (
        f"Output should indicate dry run. Got:\n{result.stderr}"
    )
    assert FLASK in result.stdout, (
        f"Dry-run output should mention flask as a candidate. Got:\n{result.stdout}"
    )

    # Verify flask was not installed in conda's metadata
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert FLASK not in installed, (
        f"flask should NOT be installed after a dry run. Installed packages: {installed.names}"
    )

    # Verify nothing was written to disk either (not just absent from metadata)
    files_after = sorted(str(p) for p in env_path.rglob("*"))
    assert files_after == files_before, (
        f"dry run should not write any files to {env_path}. "
        f"Before: {files_before}, after: {files_after}"
    )


def test_install_reports_full_details(conda, empty_env):
    """``conda install`` output reports the actual channel, platform, and environment location."""
    env_name, env_path = empty_env

    # Ground truth: the platform and channel this conda is actually configured for.
    platform = conda("info", "--json").assert_ok().json()["platform"]
    channels = conda("config", "--show", "channels", "--json").assert_ok().json()["channels"]

    result = conda("install", "-n", env_name, FLASK).assert_ok()

    assert f"environment location: {env_path}" in result.stdout, (
        f"Install output should report the environment location. Got:\n{result.stdout}"
    )
    assert f"Platform: {platform}" in result.stdout, (
        f"Install output should report platform {platform!r}. Got:\n{result.stdout}"
    )
    for channel in channels:
        assert channel in result.stdout, (
            f"Install output should report channel {channel!r}. Got:\n{result.stdout}"
        )

    # Verify flask is physically present on disk, not just in conda-meta
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    python = installed.get("python")
    assert python is not None, "python should be installed as a flask dependency"
    site_packages = site_packages_dir(env_path, python.version)
    assert (site_packages / FLASK / "__init__.py").is_file(), (
        f"flask should be unpacked on disk at {site_packages}"
    )


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.parametrize(
    ("args", "expected_code", "expected_message"),
    [
        (("totally-fake-package-xyz123",), 1, "PackagesNotFoundInChannelsError"),
        ((), 1, "too few arguments"),
        (("--invalid-flag", FLASK), 2, "unrecognized arguments: --invalid-flag"),
    ],
    ids=["nonexistent-package", "no-packages", "invalid-flag"],
)
def test_install_fails(conda, empty_env, args, expected_code, expected_message):
    """``conda install`` fails with the expected exit code and message."""
    env_name, _ = empty_env

    result = conda("install", "-n", env_name, *args)
    result.assert_error(code=expected_code, contains=expected_message)


def test_install_nonexistent_env_fails(conda):
    """``conda install -n <nonexistent-env>`` fails with an environment-not-found error."""
    result = conda("install", "-n", "totally-nonexistent-env-xyz", FLASK)
    result.assert_error(code=1, contains="EnvironmentLocationNotFound")
