# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

import json

# Key configuration options that should be present in conda config output
EXPECTED_CONFIG_KEYS = (
    "channels",
    "channel_priority",
    "auto_update_conda",
    "always_yes",
    "changeps1",
    "ssl_verify",
)


# =============================================================================
# Positive test cases
# =============================================================================


def test_config_help(conda):
    """``conda config --help`` documents available options."""
    result = conda("config", "--help").assert_ok()
    output = f"{result.stdout}\n{result.stderr}"

    expected = (
        "usage:",
        "conda config",
        "Modify configuration values in .condarc",
        "-h, --help",
        "--show",
        "--show-sources",
        "--json",
        "--set KEY VALUE",
        "--get",
        "--append KEY VALUE",
        "--remove KEY VALUE",
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

    # Verify output is valid JSON
    data = json.loads(result.stdout)
    assert isinstance(data, dict), "JSON output should be a dictionary"

    # Verify key configuration options are present
    missing = [k for k in EXPECTED_CONFIG_KEYS if k not in data]
    assert not missing, f"JSON output missing keys: {missing}. Keys present: {list(data.keys())}"


def test_config_show_channels(conda):
    """``conda config --show channels`` displays the channels list."""
    result = conda("config", "--show", "channels").assert_ok()
    output = result.stdout

    # Verify output contains channels key
    assert "channels:" in output, f"Output should contain 'channels:'. Got:\n{output}"


def test_config_show_channel_priority(conda):
    """``conda config --show channel_priority`` displays channel priority setting."""
    result = conda("config", "--show", "channel_priority").assert_ok()
    output = result.stdout

    # Verify output contains channel_priority key
    assert "channel_priority:" in output, (
        f"Output should contain 'channel_priority:'. Got:\n{output}"
    )

    # Verify value is one of the valid options
    valid_values = ("strict", "flexible", "disabled")
    has_valid_value = any(v in output.lower() for v in valid_values)
    assert has_valid_value, (
        f"channel_priority should be one of {valid_values}. Got:\n{output}"
    )


def test_config_show_sources(conda):
    """``conda config --show-sources`` displays configuration file sources."""
    result = conda("config", "--show-sources").assert_ok()
    output = result.stdout

    # Verify output indicates config sources (files or defaults)
    # Output should contain file paths or indicate where config comes from
    assert output.strip(), "show-sources should produce output"


def test_config_show_sources_json(conda):
    """``conda config --show-sources --json`` returns valid JSON with source info."""
    result = conda("config", "--show-sources", "--json").assert_ok()

    # Verify output is valid JSON
    data = json.loads(result.stdout)
    assert isinstance(data, dict), "JSON output should be a dictionary"


# =============================================================================
# Edge cases
# =============================================================================


def test_config_show_invalid_key(conda):
    """``conda config --show invalid_key`` handles unknown keys gracefully."""
    result = conda("config", "--show", "nonexistent_key_12345")
    # conda may return error or empty output for invalid keys
    output = f"{result.stdout}\n{result.stderr}"
    # Either it errors or returns empty/warning - both are acceptable
    assert result.returncode != 0 or "nonexistent_key_12345" not in output or not output.strip(), (
        f"Should either error or not show the invalid key. Got:\n{output}"
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
