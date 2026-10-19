# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

from textwrap import dedent

import pytest

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


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(52)
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


@pytest.mark.covers(93, 94, 95)
@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_set_channel_priority(conda, condarc, priority):
    """``conda config --set channel_priority <p>`` writes the value to .condarc."""
    conda("config", "--set", "channel_priority", priority).assert_ok()

    result = conda("config", "--show", "channel_priority", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.channel_priority == priority, (
        f"channel_priority should be '{priority}' after --set. Got: {config.channel_priority}"
    )

    # Check the source file too: the effective value may already match the
    # default, and a missing source fails the lookup below with a KeyError.
    sources = ConfigSources.from_stdout(conda("config", "--show-sources").assert_ok())
    assert sources.channel_priority(condarc) == priority, (
        f".condarc should hold channel_priority '{priority}' after --set. "
        f"Got: {sources.channel_priority(condarc)}"
    )


@pytest.mark.covers(99, 100)
@pytest.mark.parametrize("solver", ["classic", "libmamba", "rattler"])
def test_config_set_solver(conda, condarc, solver):
    """``conda config --set solver <solver>`` writes the value to .condarc."""
    conda("config", "--set", "solver", solver).assert_ok()

    result = conda("config", "--show", "solver", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.solver == solver, f"solver should be '{solver}' after --set. Got: {config.solver}"

    # Check the source file too: the effective value may already match the
    # default, and a missing source fails the lookup below with a KeyError.
    sources = ConfigSources.from_stdout(conda("config", "--show-sources").assert_ok())
    assert sources.solver(condarc) == solver, (
        f".condarc should hold solver '{solver}' after --set. Got: {sources.solver(condarc)}"
    )


@pytest.mark.covers(114)
def test_config_add_channels_prepends_conda_forge(conda, condarc):
    """``conda config --add channels conda-forge`` prepends it to .condarc channels.

    The file starts with ``defaults``, so appending instead of prepending produces
    the opposite order and fails the exact-list assertion.
    """
    condarc.write_text(
        dedent("""\
        channels:
          - defaults
        """)
    )

    conda("config", "--add", "channels", "conda-forge").assert_ok()

    result = conda("config", "--show", "channels", "--json").assert_ok()
    config = ConfigShow.from_json(result)
    assert config.channels == ["conda-forge", "defaults"], (
        f"--add must prepend; got: {config.channels}"
    )

    # Verify the persisted source contains the merged channel list.
    sources = ConfigSources.from_stdout(conda("config", "--show-sources").assert_ok())
    assert sources.channels(condarc) == ["conda-forge", "defaults"], (
        f".condarc should hold the merged list after --add. Got: {sources.channels(condarc)}"
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
