# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

from textwrap import dedent

import pytest
from shared.help_command_helpers import parse_help

from conda_e2e.parsers.config import ConfigShow, ConfigSources

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

# Each section maps its flags (aliases grouped together) to their fixed choices; set() means none.
EXPECTED_HELP = {
    "usage": "usage: conda config",
    "description": (
        "Modify configuration values in .condarc. This is modeled after the git config "
        "command. Writes to the user .condarc file (<HOME>/.condarc) by default. Use the "
        "--show-sources flag to display all identified configuration locations on your computer."
    ),
    "sections": {
        "options:": {frozenset({"-h", "--help"}): set()},
        "Output, Prompt, and Flow Control Options:": {
            frozenset({"--console"}): {"classic", "json"},
            frozenset({"--json"}): set(),
            frozenset({"-q", "--quiet"}): set(),
            frozenset({"-v", "--verbose"}): set(),
        },
        "Config File Location Selection:": {
            frozenset({"--system"}): set(),
            frozenset({"--env"}): set(),
            frozenset({"--file"}): set(),
            frozenset({"-n", "--name"}): set(),
            frozenset({"-p", "--prefix"}): set(),
        },
        "Config Subcommands:": {
            frozenset({"--describe"}): set(),
            frozenset({"--show"}): set(),
            frozenset({"--show-sources"}): set(),
            frozenset({"--validate"}): set(),
            frozenset({"--write-default"}): set(),
        },
        "Config Modifiers:": {
            frozenset({"--append"}): set(),
            frozenset({"--clear"}): set(),
            frozenset({"--get"}): set(),
            frozenset({"--prepend", "--add"}): set(),
            frozenset({"--remove"}): set(),
            frozenset({"--remove-key"}): set(),
            frozenset({"--set"}): set(),
            frozenset({"--stdin"}): set(),
        },
    },
}

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(52)
def test_config_help_matches_contract(conda, isolated_env_vars):
    """``conda config --help`` renders the expected structural contract."""
    output = conda("config", "--help").assert_ok().stdout
    # Config help includes the temporary HOME path; use <HOME> and "/"
    # instead of Windows backslashes.
    normalized_output = output.replace(isolated_env_vars["HOME"], "<HOME>")
    normalized_output = normalized_output.replace("<HOME>\\", "<HOME>/")
    actual = parse_help(normalized_output)
    assert actual == EXPECTED_HELP, f"Output:\n{output}"


@pytest.mark.covers(53)
def test_config_show(conda):
    """``conda config --show`` displays all configuration settings."""
    result = conda("config", "--show").assert_ok()
    config = ConfigShow.from_stdout(result)

    missing = [k for k in EXPECTED_CONFIG_KEYS if k not in config]
    assert not missing, f"Config output missing keys: {missing}. Present: {list(config.values)}"


@pytest.mark.covers(54)
def test_config_show_json(conda):
    """``conda config --show --json`` returns all settings."""
    result = conda("config", "--show", "--json").assert_ok()
    config = ConfigShow.from_json(result)

    missing = [k for k in EXPECTED_CONFIG_KEYS if k not in config]
    assert not missing, f"JSON output missing keys: {missing}. Present: {list(config.values)}"


@pytest.mark.covers(55)
def test_config_show_channels(conda, condarc):
    """``conda config --show channels`` displays the channels list in stdout."""
    condarc.write_text(
        dedent("""\
        channels:
          - defaults
          - conda-forge
        """)
    )

    result = conda("config", "--show", "channels").assert_ok()
    config = ConfigShow.from_stdout(result)
    assert config.channels == ["defaults", "conda-forge"], (
        f"channels should match .condarc. Got: {config.channels}"
    )


@pytest.mark.covers(56)
def test_config_show_channels_json(conda, condarc):
    """``conda config --show channels --json`` returns the channels list."""
    condarc.write_text(
        dedent("""\
        channels:
          - defaults
          - conda-forge
        """)
    )

    result = conda("config", "--show", "channels", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.channels == ["defaults", "conda-forge"], (
        f"channels should match .condarc. Got: {config.channels}"
    )


@pytest.mark.covers(58)
def test_config_show_channel_priority_default(conda):
    """``conda config --show channel_priority`` returns 'flexible' by default."""
    result = conda("config", "--show", "channel_priority", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.channel_priority == "flexible", (
        f"Default channel_priority should be 'flexible'. Got: {config.channel_priority}"
    )


@pytest.mark.covers(57)
@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_show_channel_priority(conda, condarc, priority):
    """``conda config --show channel_priority`` displays channel priority in stdout."""
    condarc.write_text(f"channel_priority: {priority}\n")

    result = conda("config", "--show", "channel_priority").assert_ok()
    config = ConfigShow.from_stdout(result)
    assert config.channel_priority == priority, (
        f"channel_priority should be '{priority}'. Got: {config.channel_priority}"
    )


@pytest.mark.covers(58)
@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_show_channel_priority_json(conda, condarc, priority):
    """``conda config --show channel_priority --json`` returns the priority value."""
    condarc.write_text(f"channel_priority: {priority}\n")

    result = conda("config", "--show", "channel_priority", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.channel_priority == priority, (
        f"channel_priority should be '{priority}'. Got: {config.channel_priority}"
    )


@pytest.mark.covers(59)
def test_config_show_sources_empty_condarc_not_shown(conda, condarc):
    """Empty .condarc is not shown in ``conda config --show-sources``."""
    result = conda("config", "--show-sources").assert_ok()
    sources = ConfigSources.from_stdout(result)

    assert not sources.has_source(condarc), (
        f"Empty .condarc should not be shown. Sources: {sources.source_paths}"
    )


@pytest.mark.covers(59)
def test_config_show_sources(conda, condarc):
    """``conda config --show-sources`` lists the .condarc source and its values."""
    condarc.write_text(
        dedent("""\
        channels:
          - defaults
        """)
    )

    result = conda("config", "--show-sources").assert_ok()
    sources = ConfigSources.from_stdout(result)

    assert sources.has_source(condarc), (
        f"Output should list .condarc at {condarc.resolve()}. Sources: {sources.source_paths}"
    )
    assert sources.channels(condarc) == ["defaults"], (
        f"channels should match .condarc. Got: {sources.channels(condarc)}"
    )


@pytest.mark.covers(60)
def test_config_show_sources_json_empty_condarc_not_shown(conda, condarc):
    """Empty .condarc is not shown in ``conda config --show-sources --json``."""
    result = conda("config", "--show-sources", "--json").assert_ok()
    sources = ConfigSources.from_json(result)

    assert not sources.has_source(condarc), (
        f"Empty .condarc should not be shown. Sources: {sources.source_paths}"
    )


@pytest.mark.covers(60)
def test_config_show_sources_json(conda, condarc):
    """``conda config --show-sources --json`` returns source info with correct paths."""
    condarc.write_text(
        dedent("""\
        channels:
          - defaults
          - conda-forge
        """)
    )

    result = conda("config", "--show-sources", "--json").assert_ok()
    sources = ConfigSources.from_json(result)

    assert sources.has_source(condarc), (
        f"JSON should include .condarc at {condarc.resolve()}. Sources: {sources.source_paths}"
    )
    assert sources.channels(condarc) == ["defaults", "conda-forge"], (
        f"channels should match .condarc. Got: {sources.channels(condarc)}"
    )


# =============================================================================
# Edge cases
# =============================================================================


@pytest.mark.covers(140)
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


@pytest.mark.covers(646)
def test_config_invalid_flag(conda):
    """``conda config --invalid-flag`` fails with unrecognized argument error."""
    result = conda("config", "--invalid-flag")
    result.assert_error(
        code=2,
        contains="unrecognized arguments: --invalid-flag",
    )
