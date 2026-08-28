# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Output, Prompt, and Flow Control options."""

from __future__ import annotations

from textwrap import dedent

import pytest
from helpers import PACKAGE_NAME, download_table_rows, list_installed_packages
from install_asserts import (
    assert_package_present,
    assert_package_unpacked,
    require_python_version,
)

from conda_e2e.parsers.config import ConfigShow
from conda_e2e.parsers.install import InstallResult

# =============================================================================
# Output format tests
# =============================================================================


def test_install_json_output(conda, empty_env):
    """``conda install --json`` produces valid JSON with expected structure."""
    env_name, env_path = empty_env

    result = conda("install", "-n", env_name, "--json", PACKAGE_NAME).assert_ok()

    install_result = InstallResult.from_json(result)
    assert install_result.success, "JSON install result should report success."
    assert any(package.name == PACKAGE_NAME for package in install_result.link_packages), (
        f"actions.LINK should contain {PACKAGE_NAME}. Got: "
        f"{[package.name for package in install_result.link_packages]}"
    )

    # Verify LINK packages come from configured channels
    # "defaults" maps to pkgs/main and pkgs/r, so check default_channels for actual names
    default_channels_result = conda("config", "--show", "default_channels", "--json").assert_ok()
    default_channels = ConfigShow.from_json(default_channels_result).default_channels
    channels_result = conda("config", "--show", "channels", "--json").assert_ok()
    config = ConfigShow.from_json(channels_result)
    # Valid channels: configured channel names + default_channels names (for "defaults" alias)
    valid_channels = set(config.channels) | set(default_channels)
    for package in install_result.link_packages:
        pkg_channel = package.channel
        matches_config = any(ch in pkg_channel for ch in valid_channels)
        assert matches_config, (
            f"Package {package.name} channel {pkg_channel!r} should match "
            f"one of valid channels {valid_channels}"
        )

    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


@pytest.mark.parametrize("flag", ["-q", "--quiet"])
def test_install_quiet_suppresses_progress_output(conda, empty_env, make_env, flag):
    """``conda install -q`` / ``--quiet`` suppresses progress bar output."""
    env_name, env_path = empty_env

    # Baseline: verify banner appears without quiet flag
    baseline_env, _ = make_env()
    baseline = conda("install", "-n", baseline_env, PACKAGE_NAME).assert_ok()
    assert "Downloading and Extracting Packages" in baseline.stdout, (
        f"Baseline (no quiet flag) should show progress banner. Got:\n{baseline.stdout}"
    )

    # Test: quiet flag should suppress the banner
    result = conda("install", "-n", env_name, flag, PACKAGE_NAME).assert_ok()

    assert "Downloading and Extracting Packages" not in result.stdout, (
        f"Quiet mode ({flag}) should suppress progress output. Got:\n{result.stdout}"
    )

    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


@pytest.mark.parametrize(("flag", "level"), [("-vv", "INFO"), ("-vvv", "DEBUG")])
def test_install_verbose_produces_logging(conda, empty_env, flag, level):
    """``conda install -vv/-vvv`` produces INFO/DEBUG logging on stderr."""
    env_name, env_path = empty_env

    result = conda("install", "-n", env_name, flag, PACKAGE_NAME).assert_ok()

    assert level in result.stderr, (
        f"Verbose mode ({flag}) should produce {level} logging on stderr. "
        f"Got stderr:\n{result.stderr[:500]}"
    )

    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_download_only_populates_cache_without_installing(conda, cache_dir, empty_env):
    """``conda install --download-only`` populates cache but does not install packages."""
    env_name, _ = empty_env

    cache_before = set(cache_dir.glob("*"))

    result = conda("install", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()

    assert "will be downloaded" in result.stdout, (
        f"Download-only output should show download table. Got:\n{result.stdout}"
    )

    cache_after = set(cache_dir.glob("*"))
    new_cached = cache_after - cache_before
    assert new_cached, (
        f"--download-only should populate cache with new packages. "
        f"Cache dir: {cache_dir}, before: {len(cache_before)}, after: {len(cache_after)}"
    )
    package_cached = any(PACKAGE_NAME in str(f.name) for f in new_cached)
    assert package_cached, (
        f"Cache should contain {PACKAGE_NAME}. New entries: {[f.name for f in new_cached]}"
    )

    installed = list_installed_packages(conda, "-n", env_name)
    assert PACKAGE_NAME not in installed, (
        f"{PACKAGE_NAME} should NOT be installed after --download-only. "
        f"Installed: {installed.names}"
    )


def test_install_show_channel_urls_overrides_config(conda, condarc, empty_env):
    """``conda install --show-channel-urls`` shows channel name even when config disables it."""
    env_name, _ = empty_env

    condarc.write_text(
        dedent("""\
        show_channel_urls: false
        """)
    )

    baseline = conda("install", "-n", env_name, "--dry-run", PACKAGE_NAME).assert_ok()
    rows_off = download_table_rows(baseline.stdout)
    assert rows_off, f"Baseline should have download table rows. Got:\n{baseline.stdout}"
    # Without channel: "build_string  size_num  size_unit" = 3 tokens after "|"
    assert all(len(row.split("|")[-1].split()) == 3 for row in rows_off), (
        f"With show_channel_urls: false, all rows should have 3 tokens after '|'. "
        f"Got rows:\n{rows_off}"
    )

    result = conda(
        "install", "-n", env_name, "--dry-run", "--show-channel-urls", PACKAGE_NAME
    ).assert_ok()

    rows_on = download_table_rows(result.stdout)
    assert rows_on, f"Result should have download table rows. Got:\n{result.stdout}"
    # With channel: "build_string  size_num  size_unit  channel" = 4 tokens after "|"
    assert all(len(row.split("|")[-1].split()) == 4 for row in rows_on), (
        f"With --show-channel-urls, all rows should have 4 tokens (including channel). "
        f"Got rows:\n{rows_on}"
    )
