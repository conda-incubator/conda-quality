# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

from textwrap import dedent

import pytest
from help_command_helpers import has_help_item, normalized, option_pairs_from_help

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

EXPECTED_HELP = {
    "usage": ("usage: conda config",),
    "description": ("Modify configuration values in .condarc.",),
    "options": ("options:",),
    "output options": ("Output, Prompt, and Flow Control Options:",),
    "config file location selection": ("Config File Location Selection:",),
    "config subcommands": ("Config Subcommands:",),
    "config modifiers": ("Config Modifiers:",),
    "examples": ("Examples:",),
}

# Keys sorted for readability; compared as a dict, so output order isn't asserted.
# --system/--env excluded: host-dependent descriptions (see pairing test).
EXPECTED_OPTION_DESCRIPTIONS = {
    "--append KEY VALUE": "Add one configuration value to the end of a list key.",
    "--console {classic,json}": "Select the backend to use for normal output rendering.",
    "--describe [DESCRIBE ...]": (
        "Describe given configuration parameters. If no arguments given, show information "
        "for all configuration parameters."
    ),
    "--file FILE": "Write to the given file.",
    "--get [KEY ...]": "Get a configuration value.",
    "--json": "Report all output as json. Suitable for using conda programmatically.",
    "--prepend, --add KEY VALUE": "Add one configuration value to the beginning of a list key.",
    "--remove KEY VALUE": (
        "Remove a configuration value from a list key. This removes all instances of the value."
    ),
    "--remove-key KEY": "Remove a configuration key (and all its values).",
    "--set KEY VALUE": "Set a boolean or string key.",
    "--show [SHOW ...]": (
        "Display configuration values as calculated and compiled. If no arguments given, "
        "show information for all configuration values."
    ),
    "--show-sources": "Display all identified configuration sources.",
    "--stdin": "Apply configuration information given in yaml format piped through stdin.",
    "--validate": (
        "Validate all configuration sources. Iterates over all .condarc files and checks for "
        "parsing errors."
    ),
    "--write-default": (
        "Write the default configuration to a file. Equivalent to `conda config --describe > "
        "~/.condarc`."
    ),
    "-h, --help": "Show this help message and exit.",
    "-n, --name ENVIRONMENT": "Name of environment.",
    "-p, --prefix PATH": "Full path to environment location (i.e. prefix).",
    "-q, --quiet": "Do not display progress bar.",
    "-v, --verbose": (
        "Can be used multiple times. Once for detailed output, twice for INFO logging, "
        "thrice for DEBUG logging, four times for TRACE logging."
    ),
}


# =============================================================================
# Positive test cases
# =============================================================================


def test_config_help(conda):
    """``conda config --help`` documents usage, description, and sections."""
    output = conda("config", "--help").assert_ok().stdout
    collapsed = normalized(output)
    missing = {}
    for section, items in EXPECTED_HELP.items():
        section_missing = [item for item in items if not has_help_item(item, collapsed)]
        if section_missing:
            missing[section] = section_missing
    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"


def test_config_help_option_descriptions_pair_correctly(conda):
    """Each option is paired with its own description."""
    output = conda("config", "--help").assert_ok().stdout
    actual = option_pairs_from_help(output)
    # --system/--env descriptions embed the conda under test's install path and the
    # sandbox HOME, which differ per host, so only their presence is asserted.
    assert {"--system", "--env"} <= actual.keys(), f"Output:\n{output}"
    actual = {key: value for key, value in actual.items() if key not in ("--system", "--env")}
    assert actual == EXPECTED_OPTION_DESCRIPTIONS, f"Output:\n{output}"


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
