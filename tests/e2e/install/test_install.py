# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from packaging.version import Version

from conda_e2e.parsers.config import ConfigShow
from conda_e2e.parsers.info import CondaInfo
from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import site_packages_dir

if TYPE_CHECKING:
    from pathlib import Path

NEW_PKG_INSTALLED_MSG = "The following NEW packages will be INSTALLED:"
PACKAGE_NAME = "flask"

# =============================================================================
# Helper functions
# =============================================================================


def _python_version(installed: PackageList) -> str:
    """Return the installed ``python`` package's version, asserting it's present."""
    python = installed.get("python")
    assert python is not None, "python should be installed as a dependency"
    return python.version


def _assert_package_unpacked(
    env_path: Path,
    package_name: str,
    python_version: str | None = None,
) -> None:
    """Assert ``package_name`` is physically unpacked on disk (as a package dir)."""
    site_packages = site_packages_dir(env_path, python_version)
    init_file = site_packages / package_name / "__init__.py"
    assert init_file.is_file(), f"{package_name} should be unpacked on disk at {site_packages}"


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
    result = conda("install", flag, target, PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Install output should mention {PACKAGE_NAME}. Got:\n{result.stdout}"
    )

    # Verify flask appears in conda list
    list_result = conda("list", flag, target).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {target} after install. "
        f"Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


def test_install_multiple_packages(conda, empty_env):
    """``conda install click six`` installs multiple packages at once."""
    env_name, env_path = empty_env
    packages = ("click", "six")

    # Execute: install multiple packages in one command
    result = conda("install", "-n", env_name, *packages).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify all packages appear in conda list
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    for pkg in packages:
        assert pkg in installed, (
            f"{pkg} should be present in {env_name} after install. "
            f"Installed packages: {installed.names}"
        )

    # Verify both are physically present on disk, not just in conda-meta.
    # click is a package (dir with __init__.py); six is a single module file.
    python_version = _python_version(installed)
    _assert_package_unpacked(env_path, packages[0], python_version)
    site_packages = site_packages_dir(env_path, python_version)
    assert (site_packages / f"{packages[1]}.py").is_file(), (
        f"{packages[1]} should be unpacked on disk at {site_packages}"
    )


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
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


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
    _assert_package_unpacked(env_path, package_name, _python_version(installed))


def test_install_specific_version(conda, empty_env):
    """``conda install flask=<version>`` installs the exact pinned (non-latest) version."""
    env_name, env_path = empty_env

    search_result = conda("search", PACKAGE_NAME, "--json").assert_ok()
    versions = sorted(
        {p["version"] for p in search_result.json().get(PACKAGE_NAME, [])},
        key=Version,
    )
    assert len(versions) >= 2, (
        f"need at least 2 {PACKAGE_NAME} versions to verify pinning is respected"
    )
    pinned_version = versions[-2]  # not latest, so we can tell the pin was actually respected

    # Execute: install the pinned version
    result = conda("install", "-n", env_name, f"{PACKAGE_NAME}={pinned_version}").assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Install output should mention {PACKAGE_NAME}. Got:\n{result.stdout}"
    )

    # Verify the exact pinned version is installed
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get(PACKAGE_NAME)
    assert record is not None, f"{PACKAGE_NAME} record should be found in conda list"
    assert record.version == pinned_version, (
        f"{PACKAGE_NAME} version should be {pinned_version}. Got: {record.version}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


def test_install_no_deps(conda, empty_env):
    """``conda install --no-deps flask`` installs only flask, no dependencies."""
    env_name, env_path = empty_env

    # Execute: install flask without dependencies
    result = conda("install", "-n", env_name, "--no-deps", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Install output should mention {PACKAGE_NAME}. Got:\n{result.stdout}"
    )

    # Verify flask is the only package installed (env started empty)
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert installed.names == (PACKAGE_NAME,), (
        f"--no-deps should install only {PACKAGE_NAME}. Installed packages: {installed.names}"
    )

    _assert_package_unpacked(env_path, PACKAGE_NAME)


def test_install_dry_run(conda, empty_env):
    """``conda install --dry-run`` shows what would be installed without making changes."""
    env_name, env_path = empty_env
    files_before = sorted(str(p) for p in env_path.rglob("*"))

    # Execute: dry-run install of flask
    result = conda("install", "-n", env_name, "--dry-run", PACKAGE_NAME).assert_ok()

    # Verify output indicates dry run and lists flask
    assert "DryRunExit" in result.stderr or "Dry run" in result.stderr, (
        f"Output should indicate dry run. Got:\n{result.stderr}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Dry-run output should mention {PACKAGE_NAME} as a candidate. Got:\n{result.stdout}"
    )

    # Verify flask was not installed in conda's metadata
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME not in installed, (
        f"{PACKAGE_NAME} should NOT be installed after a dry run. "
        f"Installed packages: {installed.names}"
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
    info_result = conda("info", "--json").assert_ok()
    info = CondaInfo.from_json(info_result)
    config_result = conda("config", "--show", "channels", "--json").assert_ok()
    config = ConfigShow.from_json(config_result)

    result = conda("install", "-n", env_name, PACKAGE_NAME).assert_ok()

    assert f"environment location: {env_path}" in result.stdout, (
        f"Install output should report the environment location. Got:\n{result.stdout}"
    )
    assert f"Platform: {info.platform}" in result.stdout, (
        f"Install output should report platform {info.platform!r}. Got:\n{result.stdout}"
    )
    for channel in config.channels:
        assert channel in result.stdout, (
            f"Install output should report channel {channel!r}. Got:\n{result.stdout}"
        )


@pytest.mark.parametrize("solver", ["classic", "libmamba", "rattler"])
def test_install_with_solver(conda, empty_env, solver):
    """``conda install --solver <solver>`` uses the specified solver backend."""
    env_name, env_path = empty_env

    # Execute: install flask using the specified solver with max verbose output
    # -vvv is needed to get DEBUG logs which show solver-specific module names
    result = conda("install", "-n", env_name, "--solver", solver, PACKAGE_NAME, "-vvv").assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify solver-specific output in verbose logs
    # Each solver produces DEBUG/INFO logs with its unique module name
    if solver == "classic":
        assert "conda.resolve" in result.stderr, (
            f"Verbose output should mention classic solver module. Got:\n{result.stderr}"
        )
    elif solver == "libmamba":
        assert "conda.conda_libmamba_solver" in result.stderr, (
            f"Verbose output should mention libmamba solver. Got:\n{result.stderr}"
        )
    elif solver == "rattler":
        assert "conda.conda_rattler_solver" in result.stderr, (
            f"Verbose output should mention rattler solver. Got:\n{result.stderr}"
        )

    # Verify flask appears in conda list
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.parametrize(
    ("args", "expected_code", "expected_message"),
    [
        (("totally-fake-package-xyz123",), 1, "PackagesNotFoundInChannelsError"),
        ((), 1, "too few arguments"),
        (("--invalid-flag", PACKAGE_NAME), 2, "unrecognized arguments: --invalid-flag"),
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
    result = conda("install", "-n", "totally-nonexistent-env-xyz", PACKAGE_NAME)
    result.assert_error(code=1, contains="EnvironmentLocationNotFound")
