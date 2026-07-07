# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

import pytest

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
    """``conda config --show channels`` displays the channels list."""
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
    """``conda config --show channel_priority`` displays channel priority setting."""
    condarc.write_text(f"channel_priority: {priority}\n")
    data = conda("config", "--show", "channel_priority", "--json").assert_ok().json()
    assert data["channel_priority"] == priority, (
        f"channel_priority should be '{priority}'. Got: {data['channel_priority']}"
    )


def test_config_show_sources(conda):
    """``conda config --show-sources`` displays configuration file sources."""
    result = conda("config", "--show-sources").assert_ok()
    output = result.stdout

    # Primary assertion: sources are displayed with "==>" header
    assert "==>" in output, f"Output should contain source headers (==>). Got:\n{output}"

    # Secondary assertion: output should reference .condarc paths
    has_condarc_path = ".condarc" in output or "condarc" in output.lower()
    assert has_condarc_path, f"Output should contain .condarc paths. Got:\n{output}"


def test_config_show_sources_json(conda):
    """``conda config --show-sources --json`` returns valid JSON with source info."""
    result = conda("config", "--show-sources", "--json").assert_ok()

    data = result.json()
    assert isinstance(data, dict), "JSON output should be a dictionary"

    # Verify data is not empty and contains source information
    assert len(data) > 0, "JSON output should not be empty"

    # Each source should map to a dict of config values
    for source, config in data.items():
        assert isinstance(config, dict), (
            f"Source '{source}' should map to a dict of config values, got {type(config)}"
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
