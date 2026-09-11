# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

from textwrap import dedent

import pytest
from help_command_helpers import HELP_OPTION, OUTPUT_CONTROL_OPTIONS, parse_help

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

# Sections in render order; entry keys sorted (compared as dicts, so order isn't asserted).
# --system/--env embed the host's install path: presence-asserted only (see the contract test).
EXPECTED_HELP = {
    "usage": "usage: conda config",
    "usage_flags": {
        "--append",
        "--clear",
        "--console",
        "--describe",
        "--env",
        "--file",
        "--get",
        "--json",
        "--prepend",
        "--remove",
        "--remove-key",
        "--set",
        "--show",
        "--show-sources",
        "--stdin",
        "--system",
        "--validate",
        "--write-default",
        "-h",
        "-n",
        "-p",
        "-q",
        "-v",
    },
    "description": (
        "Modify configuration values in .condarc. This is modeled after the git config "
        "command. Writes to the user .condarc file (<HOME>/.condarc) by default. Use the "
        "--show-sources flag to display all identified configuration locations on your computer."
    ),
    "sections": {
        "options:": {"entries": HELP_OPTION},
        "Output, Prompt, and Flow Control Options:": {"entries": OUTPUT_CONTROL_OPTIONS},
        "Config File Location Selection:": {
            "entries": {
                "--file": "Write to the given file.",
                "-n, --name": "Name of environment.",
                "-p, --prefix": "Full path to environment location (i.e. prefix).",
            },
            "prose": [
                "Without one of these flags, the user config file at '<HOME>/.condarc' is used."
            ],
        },
        "Config Subcommands:": {
            "entries": {
                "--describe": (
                    "Describe given configuration parameters. If no arguments given, show "
                    "information for all configuration parameters."
                ),
                "--show": (
                    "Display configuration values as calculated and compiled. If no arguments "
                    "given, show information for all configuration values."
                ),
                "--show-sources": "Display all identified configuration sources.",
                "--validate": (
                    "Validate all configuration sources. Iterates over all .condarc files and "
                    "checks for parsing errors."
                ),
                "--write-default": (
                    "Write the default configuration to a file. Equivalent to `conda config "
                    "--describe > ~/.condarc`."
                ),
            },
        },
        "Config Modifiers:": {
            "entries": {
                "--append": "Add one configuration value to the end of a list key.",
                "--clear": "Clear all values from a list key.",
                "--get": "Get a configuration value.",
                "--prepend, --add": "Add one configuration value to the beginning of a list key.",
                "--remove": (
                    "Remove a configuration value from a list key. This removes all instances "
                    "of the value."
                ),
                "--remove-key": "Remove a configuration key (and all its values).",
                "--set": "Set a boolean or string key.",
                "--stdin": (
                    "Apply configuration information given in yaml format piped through stdin."
                ),
            },
            "prose": [
                "See `conda config --describe` or https://conda.io/docs/config.html for details "
                "on all the options that can go in .condarc."
            ],
        },
        "Examples:": {
            "prose": [
                "Display all configuration values as calculated and compiled:",
                "conda config --show",
                "Display all identified configuration sources:",
                "conda config --show-sources",
                "Print the descriptions of all available configuration options to your "
                "command line:",
                "conda config --describe",
                'Print the description for the "channel_priority" configuration option to your '
                "command line:",
                "conda config --describe channel_priority",
                "Add the conda-canary channel:",
                "conda config --add channels conda-canary",
                "Set the output verbosity to level 3 (highest) for the current activate "
                "environment:",
                "conda config --set verbosity 3 --env",
                "Add the 'conda-forge' channel as a backup to 'defaults':",
                "conda config --append channels conda-forge",
            ],
        },
    },
}

# =============================================================================
# Positive test cases
# =============================================================================


def test_config_help_matches_contract(conda, isolated_env_vars):
    """``conda config --help`` renders exactly the documented help."""
    output = conda("config", "--help").assert_ok().stdout
    # Pin the per-test sandbox HOME so text embedding it compares exactly.
    actual = parse_help(output.replace(isolated_env_vars["HOME"], "<HOME>"))
    # --system/--env embed the host's install path: presence only.
    location_entries = (
        actual["sections"].get("Config File Location Selection:", {}).get("entries", {})
    )
    assert {"--system", "--env"} <= location_entries.keys(), f"Output:\n{output}"
    for flag in ("--system", "--env"):
        del location_entries[flag]
    assert actual == EXPECTED_HELP, f"Output:\n{output}"


def test_config_help_short_flag_matches_long_form(conda):
    """``conda config -h`` renders identically to ``--help``."""
    long_form = conda("config", "--help").assert_ok().stdout
    short_form = conda("config", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"


def test_config_show(conda):
    """``conda config --show`` displays all configuration settings."""
    result = conda("config", "--show").assert_ok()
    config = ConfigShow.from_stdout(result)

    missing = [k for k in EXPECTED_CONFIG_KEYS if k not in config]
    assert not missing, f"Config output missing keys: {missing}. Present: {list(config.values)}"


def test_config_show_json(conda):
    """``conda config --show --json`` returns all settings."""
    result = conda("config", "--show", "--json").assert_ok()
    config = ConfigShow.from_json(result)

    missing = [k for k in EXPECTED_CONFIG_KEYS if k not in config]
    assert not missing, f"JSON output missing keys: {missing}. Present: {list(config.values)}"


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


def test_config_show_channel_priority_default(conda):
    """``conda config --show channel_priority`` returns 'flexible' by default."""
    result = conda("config", "--show", "channel_priority", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.channel_priority == "flexible", (
        f"Default channel_priority should be 'flexible'. Got: {config.channel_priority}"
    )


@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_show_channel_priority(conda, condarc, priority):
    """``conda config --show channel_priority`` displays channel priority in stdout."""
    condarc.write_text(f"channel_priority: {priority}\n")

    result = conda("config", "--show", "channel_priority").assert_ok()
    config = ConfigShow.from_stdout(result)
    assert config.channel_priority == priority, (
        f"channel_priority should be '{priority}'. Got: {config.channel_priority}"
    )


@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_show_channel_priority_json(conda, condarc, priority):
    """``conda config --show channel_priority --json`` returns the priority value."""
    condarc.write_text(f"channel_priority: {priority}\n")

    result = conda("config", "--show", "channel_priority", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.channel_priority == priority, (
        f"channel_priority should be '{priority}'. Got: {config.channel_priority}"
    )


def test_config_show_sources_empty_condarc_not_shown(conda, condarc):
    """Empty .condarc is not shown in ``conda config --show-sources``."""
    result = conda("config", "--show-sources").assert_ok()
    sources = ConfigSources.from_stdout(result)

    assert not sources.has_source(condarc), (
        f"Empty .condarc should not be shown. Sources: {sources.source_paths}"
    )


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


def test_config_show_sources_json_empty_condarc_not_shown(conda, condarc):
    """Empty .condarc is not shown in ``conda config --show-sources --json``."""
    result = conda("config", "--show-sources", "--json").assert_ok()
    sources = ConfigSources.from_json(result)

    assert not sources.has_source(condarc), (
        f"Empty .condarc should not be shown. Sources: {sources.source_paths}"
    )


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
