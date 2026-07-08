# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import env_prefix, unique_env_name

if TYPE_CHECKING:
    from pathlib import Path

# =============================================================================
# Positive test cases
# =============================================================================


def test_install_help(conda):
    """``conda install --help`` documents available options."""
    result = conda("install", "--help").assert_ok()
    output = f"{result.stdout}\n{result.stderr}"

    expected = (
        "usage:",
        "conda install",
        "Install a list of packages into a specified conda environment.",
        "-h, --help",
        "-n, --name",
        "-p, --prefix",
        "-c, --channel",
        "--revision",
        "--no-deps",
        "--only-deps",
        "--freeze-installed",
        "--update-deps",
        "--update-all",
        "--force-reinstall",
        "--solver",
        "--dry-run",
        "--json",
        "--offline",
        "--yes",
        "--file",
        "--copy",
        "--clobber",
        "--override-channels",
        "--strict-channel-priority",
        "--no-channel-priority",
        "--download-only",
    )
    missing = [e for e in expected if e not in output]
    assert not missing, f"help output missing {missing}. Command output:\n{output}"


def test_install_package(conda):
    """``conda install package`` installs flask and it appears in ``conda list``."""
    env_name = unique_env_name()

    # Setup: create a bare env with python (flask requires it)
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute: install flask into the env
    result = conda("install", "-n", env_name, "flask").assert_ok()

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "The following NEW packages will be INSTALLED:" in output, (
        f"Install output should confirm new packages. Got:\n{output}"
    )
    assert "flask" in output, f"Install output should mention flask. Got:\n{output}"

    # Verify flask appears in conda list
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert "flask" in installed, (
        f"flask should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )


def test_install_by_path(conda, envs_dir: Path):
    """``conda install -p <path> <package>`` installs into an env specified by path."""
    env_name = unique_env_name()
    env_path = env_prefix(envs_dir, env_name)

    # Setup: create env by name, then install via its path
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute: install rich using -p (prefix path) instead of -n
    result = conda("install", "-p", str(env_path), "rich").assert_ok()

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "The following NEW packages will be INSTALLED:" in output, (
        f"Install output should confirm new packages. Got:\n{output}"
    )
    assert "rich" in output, f"Install output should mention rich. Got:\n{output}"

    # Verify rich appears in conda list
    list_result = conda("list", "-p", str(env_path)).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert "rich" in installed, (
        f"rich should be present at {env_path} after install. Installed packages: {installed.names}"
    )


def test_install_multiple_packages(conda):
    """``conda install python=3.10 numpy pandas`` installs multiple packages at once."""
    env_name = unique_env_name()

    # Setup: create a bare env
    conda("create", "-n", env_name, "python=3.10").assert_ok()

    # Execute: install multiple packages in one command
    result = conda("install", "-n", env_name, "numpy", "pandas").assert_ok()

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "The following NEW packages will be INSTALLED:" in output, (
        f"Install output should confirm new packages. Got:\n{output}"
    )

    # Verify all packages appear in conda list
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    for pkg in ("numpy", "pandas"):
        assert pkg in installed, (
            f"{pkg} should be present in {env_name} after install. "
            f"Installed packages: {installed.names}"
        )


def test_install_from_conda_forge(conda):
    """``conda install -c conda-forge <package>`` installs from the conda-forge channel."""
    env_name = unique_env_name()

    # Setup: create a bare env with python
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute: install boltons from conda-forge
    result = conda("install", "-n", env_name, "-c", "conda-forge", "boltons").assert_ok()

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "The following NEW packages will be INSTALLED:" in output, (
        f"Install output should confirm new packages. Got:\n{output}"
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


def test_install_override_channels(conda):
    """``conda install -c conda-forge --override-channels <pkg>`` ignores default channels."""
    env_name = unique_env_name()

    # Setup: create a bare env with python
    conda("create", "-n", env_name, "python").assert_ok()

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
    output = f"{result.stdout}\n{result.stderr}"
    assert "The following NEW packages will be INSTALLED:" in output, (
        f"Install output should confirm new packages. Got:\n{output}"
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


def test_install_specific_version(conda):
    """``conda install flask=<version>`` installs the exact pinned version."""
    env_name = unique_env_name()

    # Setup: resolve the latest available flask version dynamically so the
    # test doesn't break if a specific version is yanked from the channel
    search_result = conda("search", "flask", "--json").assert_ok()
    versions = sorted({p["version"] for p in search_result.json().get("flask", [])})
    assert versions, "conda search should return at least one flask version"
    pinned_version = versions[-1]

    conda("create", "-n", env_name, "python").assert_ok()

    # Execute: install the resolved version
    result = conda("install", "-n", env_name, f"flask={pinned_version}").assert_ok()

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "The following NEW packages will be INSTALLED:" in output, (
        f"Install output should confirm new packages. Got:\n{output}"
    )
    assert "flask" in output, f"Install output should mention flask. Got:\n{output}"

    # Verify the exact version is installed
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


def test_install_no_deps(conda):
    """``conda install --no-deps flask`` installs flask without its dependencies."""
    env_name = unique_env_name()

    # Setup: create a bare env with python
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute: install flask without dependencies
    result = conda("install", "-n", env_name, "--no-deps", "flask").assert_ok()

    # Verify output message
    output = f"{result.stdout}\n{result.stderr}"
    assert "The following NEW packages will be INSTALLED:" in output, (
        f"Install output should confirm new packages. Got:\n{output}"
    )

    # Verify flask is installed but its core deps (werkzeug, jinja2) are not
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert "flask" in installed, (
        f"flask should be present in {env_name} after --no-deps install. "
        f"Installed packages: {installed.names}"
    )
    assert "werkzeug" not in installed, (
        f"werkzeug should NOT be installed when using --no-deps. "
        f"Installed packages: {installed.names}"
    )
    assert "jinja2" not in installed, (
        f"jinja2 should NOT be installed when using --no-deps. "
        f"Installed packages: {installed.names}"
    )


def test_install_dry_run(conda):
    """``conda install --dry-run`` shows what would be installed without making changes."""
    env_name = unique_env_name()

    # Setup: create a bare env with python
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute: dry-run install of flask
    result = conda("install", "-n", env_name, "--dry-run", "flask").assert_ok()

    # Verify output indicates dry run and lists flask
    output = f"{result.stdout}\n{result.stderr}"
    assert "DryRunExit" in output or "Dry run" in output, (
        f"Output should indicate dry run. Got:\n{output}"
    )
    assert "flask" in output, f"Dry-run output should mention flask as a candidate. Got:\n{output}"

    # Verify flask was NOT actually installed
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert "flask" not in installed, (
        f"flask should NOT be installed after a dry run. Installed packages: {installed.names}"
    )


# =============================================================================
# Negative test cases
# =============================================================================


def test_install_nonexistent_package_fails(conda):
    """``conda install <nonexistent>`` fails with a packages-not-found error."""
    env_name = unique_env_name()

    # Setup: create a bare env
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute and verify failure
    result = conda("install", "-n", env_name, "totally-fake-package-xyz123")
    result.assert_error(
        code=1,
        contains="PackagesNotFoundInChannelsError",
    )


def test_install_nonexistent_env_fails(conda):
    """``conda install -n <nonexistent-env>`` fails with an environment-not-found error."""
    result = conda("install", "-n", "totally-nonexistent-env-xyz", "flask")
    result.assert_error(
        code=1,
        contains="EnvironmentLocationNotFound",
    )


def test_install_no_packages_fails(conda):
    """``conda install`` with no package specified fails with a too-few-arguments error."""
    env_name = unique_env_name()

    # Setup: create a bare env
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute and verify failure
    result = conda("install", "-n", env_name)
    result.assert_error(
        code=1,
        contains="too few arguments",
    )


def test_install_invalid_flag_fails(conda):
    """``conda install --invalid-flag`` fails with an unrecognized-arguments error."""
    env_name = unique_env_name()

    # Setup: create a bare env
    conda("create", "-n", env_name, "python").assert_ok()

    # Execute and verify failure
    result = conda("install", "-n", env_name, "--invalid-flag", "flask")
    result.assert_error(
        code=2,
        contains="unrecognized arguments: --invalid-flag",
    )
