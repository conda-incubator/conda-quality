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

from conda_e2e.utils import unique_env_name

# =============================================================================
# Output format tests
# =============================================================================


def test_install_json_output(conda, empty_env):
    """``conda install --json`` produces valid JSON with expected structure."""
    env_name, env_path = empty_env

    result = conda("install", "-n", env_name, "--json", PACKAGE_NAME).assert_ok()

    data = result.json()
    assert "success" in data, f"JSON output should contain 'success' key. Got: {data.keys()}"
    assert data["success"] is True, f"JSON 'success' should be True. Got: {data}"
    assert "actions" in data, f"JSON output should contain 'actions' key. Got: {data.keys()}"

    actions = data["actions"]
    link_packages = [pkg["name"] for pkg in actions.get("LINK", [])]
    assert PACKAGE_NAME in link_packages, (
        f"actions.LINK should contain {PACKAGE_NAME}. Got: {link_packages}"
    )

    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


@pytest.mark.parametrize("flag", ["-q", "--quiet"])
def test_install_quiet_suppresses_progress_output(conda, empty_env, flag):
    """``conda install -q`` / ``--quiet`` suppresses progress bar output."""
    env_name, env_path = empty_env

    # Baseline: verify banner appears without quiet flag
    baseline_env = unique_env_name()
    conda("create", "-n", baseline_env).assert_ok()
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


def test_install_verbose_adds_detail(conda, empty_env):
    """``conda install -v`` produces more detailed output than default."""
    env_name, env_path = empty_env

    # Prepopulate cache so both installs have the same cache state
    conda("install", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()

    baseline_env = unique_env_name()
    conda("create", "-n", baseline_env).assert_ok()
    baseline = conda("install", "-n", baseline_env, PACKAGE_NAME).assert_ok()

    verbose = conda("install", "-n", env_name, "-v", PACKAGE_NAME).assert_ok()

    # -v adds channel gathering/reviewing messages not present in default output
    verbose_indicators = ["Gathering channels", "Reviewing channels"]

    assert any(ind in verbose.stdout for ind in verbose_indicators), (
        f"Verbose mode (-v) should show channel messages. Got:\n{verbose.stdout[:500]}"
    )
    assert not any(ind in baseline.stdout for ind in verbose_indicators), (
        f"Baseline should not show channel messages. Got:\n{baseline.stdout[:500]}"
    )

    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_very_verbose_produces_info_logging(conda, empty_env):
    """``conda install -vv`` produces INFO-level logging output on stderr."""
    env_name, env_path = empty_env

    result = conda("install", "-n", env_name, "-vv", PACKAGE_NAME).assert_ok()

    assert "INFO" in result.stderr, (
        f"Very verbose mode (-vv) should produce INFO logging on stderr. "
        f"Got stderr:\n{result.stderr}"
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
    assert all(len(row.split("|")[-1].split()) == 3 for row in rows_off), (
        f"With show_channel_urls: false, all rows should have 3 tokens after '|'. "
        f"Got rows:\n{rows_off}"
    )

    result = conda(
        "install", "-n", env_name, "--dry-run", "--show-channel-urls", PACKAGE_NAME
    ).assert_ok()

    rows_on = download_table_rows(result.stdout)
    assert rows_on, f"Result should have download table rows. Got:\n{result.stdout}"
    assert all(len(row.split("|")[-1].split()) == 4 for row in rows_on), (
        f"With --show-channel-urls, all rows should have 4 tokens (including channel). "
        f"Got rows:\n{rows_on}"
    )
