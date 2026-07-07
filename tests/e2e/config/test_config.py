# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

import pytest

from conda_e2e.parsers.config import ConfigSources

# Key configuration options that should be present in conda config output
EXPECTED_CONFIG_KEYS = (
    "channels",
    "channel_priority",
    "auto_update_conda",
    "always_yes",
    "changeps1",
    "ssl_verify",
)

# Invalid key for negative test cases
INVALID_CONFIG_KEY = "nonexistent_key_12345"


# =============================================================================
# Positive test cases
# =============================================================================


def test_config_help(conda):
    """``conda config --help`` documents available options."""
    result = conda("config", "--help").assert_ok()
    output = f"{result.stdout}\n{result.stderr}"

    # Only assert on stable flags/subcommands, not descriptive text which may change
    expected = (
        "usage:",
        "conda config",
        "-h, --help",
        "--show",
        "--show-sources",
        "--json",
        "--set",
        "--get",
        "--append",
        "--remove",
    )
    missing = [e for e in expected if e not in output]
    assert not missing, f"Help output missing: {missing}. Output:\n{output}"


def test_config_show(conda):
    """``conda config --show`` displays all configuration settings."""
    result = conda("config", "--show").assert_ok()
    output = result.stdout

    # Verify key configuration options are present (YAML format uses "key:")
    missing = [k for k in EXPECTED_CONFIG_KEYS if f"{k}:" not in output]
    assert not missing, f"Config output missing keys: {missing}. Output:\n{output}"


def test_config_show_json(conda):
    """``conda config --show --json`` returns valid JSON with all settings."""
    result = conda("config", "--show", "--json").assert_ok()

    data = result.json()
    assert isinstance(data, dict), "JSON output should be a dictionary"

    # Verify key configuration options are present
    missing = [k for k in EXPECTED_CONFIG_KEYS if k not in data]
    assert not missing, f"JSON output missing keys: {missing}. Keys present: {list(data.keys())}"


def test_config_show_channels(conda, condarc):
    """``conda config --show channels`` displays the channels list in stdout."""
    condarc.write_text("channels:\n  - defaults\n  - conda-forge\n")

    result = conda("config", "--show", "channels").assert_ok()
    output = result.stdout

    assert "channels:" in output, f"Output should contain 'channels:'. Got:\n{output}"
    assert "- defaults" in output, f"Output should contain '- defaults'. Got:\n{output}"
    assert "- conda-forge" in output, f"Output should contain '- conda-forge'. Got:\n{output}"


def test_config_show_channels_json(conda, condarc):
    """``conda config --show channels --json`` returns the channels list."""
    condarc.write_text("channels:\n  - defaults\n  - conda-forge\n")

    result = conda("config", "--show", "channels", "--json").assert_ok()
    data = result.json()

    assert "channels" in data, f"JSON output should contain 'channels' key. Got: {data}"
    assert isinstance(data["channels"], list), "channels should be a list"
    assert data["channels"] == ["defaults", "conda-forge"], (
        f"channels should match .condarc. Got: {data['channels']}"
    )


def test_config_show_channel_priority_default(conda):
    """``conda config --show channel_priority`` returns 'flexible' by default."""
    data = conda("config", "--show", "channel_priority", "--json").assert_ok().json()
    assert data["channel_priority"] == "flexible", (
        f"Default channel_priority should be 'flexible'. Got: {data['channel_priority']}"
    )


@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_show_channel_priority(conda, condarc, priority):
    """``conda config --show channel_priority`` displays channel priority in stdout."""
    condarc.write_text(f"channel_priority: {priority}\n")

    result = conda("config", "--show", "channel_priority").assert_ok()
    output = result.stdout

    assert "channel_priority:" in output, (
        f"Output should contain 'channel_priority:'. Got:\n{output}"
    )
    assert priority in output, f"Output should contain '{priority}'. Got:\n{output}"


@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_show_channel_priority_json(conda, condarc, priority):
    """``conda config --show channel_priority --json`` returns the priority value."""
    condarc.write_text(f"channel_priority: {priority}\n")
    data = conda("config", "--show", "channel_priority", "--json").assert_ok().json()
    assert data["channel_priority"] == priority, (
        f"channel_priority should be '{priority}'. Got: {data['channel_priority']}"
    )


def test_config_show_sources_empty_condarc_not_shown(conda, condarc):
    """Empty .condarc is not shown in ``conda config --show-sources``."""
    condarc.write_text("")

    result = conda("config", "--show-sources").assert_ok()
    sources = ConfigSources.from_stdout(result)

    assert not sources.has_source(condarc), (
        f"Empty .condarc should not be shown. Sources: {sources.source_paths}"
    )


def test_config_show_sources(conda, condarc):
    """``conda config --show-sources`` displays configuration file sources."""
    condarc.write_text("channels:\n  - defaults\n")

    result = conda("config", "--show-sources").assert_ok()
    sources = ConfigSources.from_stdout(result)

    assert sources.has_source(condarc), (
        f"Output should list .condarc at {condarc.resolve()}. Sources: {sources.source_paths}"
    )


def test_config_show_sources_json_empty_condarc_not_shown(conda, condarc):
    """Empty .condarc is not shown in ``conda config --show-sources --json``."""
    condarc.write_text("")

    result = conda("config", "--show-sources", "--json").assert_ok()
    sources = ConfigSources.from_json(result)

    assert not sources.has_source(condarc), (
        f"Empty .condarc should not be shown. Sources: {sources.source_paths}"
    )


def test_config_show_sources_json(conda, condarc):
    """``conda config --show-sources --json`` returns source info with correct paths."""
    condarc.write_text("channels:\n  - defaults\n  - conda-forge\n")

    result = conda("config", "--show-sources", "--json").assert_ok()
    sources = ConfigSources.from_json(result)

    assert sources.has_source(condarc), (
        f"JSON should include .condarc at {condarc.resolve()}. Sources: {sources.source_paths}"
    )

    config = sources.get_config(condarc)
    assert config is not None, f"Should have config for {condarc}"
    assert config.get("channels") == ["defaults", "conda-forge"], (
        f"channels should match .condarc. Got: {config.get('channels')}"
    )


# =============================================================================
# Edge cases
# =============================================================================


def test_config_show_invalid_key(conda):
    """``conda config --show invalid_key`` fails with invalid parameter error."""
    result = conda("config", "--show", INVALID_CONFIG_KEY)
    result.assert_error(
        code=2,
        contains="Invalid configuration parameters",
    )


# =============================================================================
# Negative test cases
# =============================================================================


def test_config_invalid_flag(conda):
    """``conda config --invalid-flag`` fails with unrecognized argument error."""
    result = conda("config", "--invalid-flag")
    result.assert_error(
        code=2,
        contains="unrecognized arguments: --invalid-flag",
    )
