# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install command — general functionality and negative cases."""

from __future__ import annotations

import pytest
from helpers import (
    PACKAGE_NAME,
    list_installed_packages,
    pick_second_newest_and_latest,
)
from install_asserts import (
    assert_install_output_has_new_packages,
    assert_installed_version,
    assert_package_present,
    assert_package_unpacked,
    require_python_version,
)

from conda_e2e.parsers.config import ConfigShow
from conda_e2e.parsers.info import CondaInfo
from conda_e2e.utils import site_packages_dir

# =============================================================================
# Positive test cases — general functionality
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
    assert_install_output_has_new_packages(result, PACKAGE_NAME)

    # Verify flask appears in conda list
    installed = list_installed_packages(conda, flag, target)
    assert_package_present(installed, PACKAGE_NAME, target)

    # Verify flask is physically present on disk, not just in conda-meta
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_multiple_packages(conda, empty_env):
    """``conda install click six`` installs multiple packages at once."""
    env_name, env_path = empty_env
    packages = ("click", "six")

    # Execute: install multiple packages in one command
    result = conda("install", "-n", env_name, *packages).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify all packages appear in conda list
    installed = list_installed_packages(conda, "-n", env_name)
    for pkg in packages:
        assert_package_present(installed, pkg, env_name)

    # Verify both are physically present on disk, not just in conda-meta.
    # click is a package (dir with __init__.py); six is a single module file.
    py_version = require_python_version(installed)
    assert_package_unpacked(env_path, packages[0], py_version)
    site_packages = site_packages_dir(env_path, py_version)
    assert (site_packages / f"{packages[1]}.py").is_file(), (
        f"{packages[1]} should be unpacked on disk at {site_packages}"
    )


def test_install_specific_version(conda, empty_env):
    """``conda install flask=<version>`` installs the exact pinned (non-latest) version."""
    env_name, env_path = empty_env
    pinned_version, _ = pick_second_newest_and_latest(conda, PACKAGE_NAME)

    # Execute: install the pinned version
    result = conda("install", "-n", env_name, f"{PACKAGE_NAME}={pinned_version}").assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result, PACKAGE_NAME)

    # Verify the exact pinned version is installed
    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_installed_version(installed, PACKAGE_NAME, pinned_version)

    # Verify flask is physically present on disk, not just in conda-meta
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


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
    installed = list_installed_packages(conda, "-n", env_name)
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
    assert config.channels, (
        f"conda should report at least one configured channel. Got: {config.channels}"
    )
    for channel in config.channels:
        assert channel in result.stdout, (
            f"Install output should report channel {channel!r}. Got:\n{result.stdout}"
        )


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.parametrize(
    ("args", "expected_code", "expected_message"),
    [
        (("totally-fake-package-xyz123",), 1, "PackagesNotFoundInChannelsError"),
        ((), 1, "too few arguments"),
        (("--invalid-flag", PACKAGE_NAME), 2, "unrecognized arguments: --invalid-flag"),
        (("--update-all",), 1, "too few arguments"),
        (
            ("--no-deps", "--only-deps", PACKAGE_NAME),
            2,
            "not allowed with argument",
        ),
    ],
    ids=[
        "nonexistent-package",
        "no-packages",
        "invalid-flag",
        "update-all-no-spec",
        "no-deps-conflicts-only-deps",
    ],
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


def test_install_invalid_solver_fails(conda):
    """``conda install --solver <invalid>`` fails with invalid choice error."""
    result = conda("install", "--solver", "fake_solver", PACKAGE_NAME)
    result.assert_error(code=2, contains="invalid choice")
