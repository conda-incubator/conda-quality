# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda config command."""

from __future__ import annotations

from textwrap import dedent

import pytest
import yaml
from shared.help_command_helpers import flags, parse_help
from shared.solver_constants import SOLVER_UNSATISFIABLE_ERRORS

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.parsers.config import ConfigShow, ConfigSources
from conda_e2e.parsers.search import SearchResult

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

# The self-signed channel is served on loopback, so host proxy settings must not
# intercept requests, and the expected verification failure needs no retries.
LOOPBACK_SEARCH_ENV = {
    "NO_PROXY": "127.0.0.1,localhost",
    "no_proxy": "127.0.0.1,localhost",
    "CONDA_REMOTE_MAX_RETRIES": "0",
}

EXPECTED_HELP = {
    "usage": "usage: conda config",
    "description": (
        "Modify configuration values in .condarc. This is modeled after the git config "
        "command. Writes to the user .condarc file (<HOME>/.condarc) by default. Use the "
        "--show-sources flag to display all identified configuration locations on your computer."
    ),
    "sections": {
        "options:": flags("-h, --help"),
        "Output, Prompt, and Flow Control Options:": flags(
            ("--console", {"classic", "json"}),
            "--json",
            "-q, --quiet",
            "-v, --verbose",
        ),
        "Config File Location Selection:": flags(
            "--system",
            "--env",
            "--file",
            "-n, --name",
            "-p, --prefix",
        ),
        "Config Subcommands:": flags(
            "--describe",
            "--show",
            "--show-sources",
            "--validate",
            "--write-default",
        ),
        "Config Modifiers:": flags(
            "--append",
            "--clear",
            "--get",
            "--prepend, --add",
            "--remove",
            "--remove-key",
            "--set",
            "--stdin",
        ),
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


@pytest.mark.covers(67)
def test_config_get_channels(conda, condarc):
    """``conda config --get channels`` prints the --add commands for configured channels.

    Only keys present in .condarc are reported, and the list is rendered lowest priority
    first, so replaying the printed commands recreates the same file order.
    """
    condarc.write_text(
        dedent("""\
        channels:
          - conda-forge
          - bioconda
        """)
    )

    result = conda("config", "--get", "channels").assert_ok()
    assert result.stdout.splitlines() == [
        "--add channels 'bioconda'   # lowest priority",
        "--add channels 'conda-forge'   # highest priority",
    ], f"Unexpected --get channels output: {result.stdout!r}"
    assert result.stderr == "", f"Expected no stderr, got: {result.stderr!r}"


@pytest.mark.covers(68)
def test_config_get_channel_priority(conda, condarc):
    """``conda config --get channel_priority`` prints the configured --set command.

    ``strict`` differs from the ``flexible`` default, so a command that reported effective
    defaults instead of the file value would print the wrong command.
    """
    condarc.write_text("channel_priority: strict\n")

    result = conda("config", "--get", "channel_priority").assert_ok()
    assert result.stdout.splitlines() == ["--set channel_priority strict"], (
        f"Unexpected --get channel_priority output: {result.stdout!r}"
    )
    assert result.stderr == "", f"Expected no stderr, got: {result.stderr!r}"


@pytest.mark.covers(69)
def test_config_get_channel_alias(conda, condarc):
    """``conda config --get channel_alias`` prints the configured --set command.

    The alias is a deliberately fake URL that is only rendered: --get never contacts it,
    so no command may reuse this value for network access.
    """
    alias = "https://example.test/conda"
    condarc.write_text(f"channel_alias: {alias}\n")

    result = conda("config", "--get", "channel_alias").assert_ok()
    assert result.stdout.splitlines() == [f"--set channel_alias {alias}"], (
        f"Unexpected --get channel_alias output: {result.stdout!r}"
    )
    assert result.stderr == "", f"Expected no stderr, got: {result.stderr!r}"


@pytest.mark.covers(93, 94, 95)
@pytest.mark.parametrize("priority", ["strict", "flexible", "disabled"])
def test_config_set_channel_priority(conda, condarc, priority):
    """``conda config --set channel_priority <p>`` writes only that key to .condarc."""
    conda("config", "--set", "channel_priority", priority).assert_ok()

    written_config = yaml.safe_load(condarc.read_text())
    assert written_config == {"channel_priority": priority}, (
        f"Unexpected .condarc after --set: {written_config}"
    )


@pytest.mark.covers(99, 100)
@pytest.mark.parametrize(
    ("solver", "baseline_solver"),
    [("classic", "libmamba"), ("libmamba", "classic"), ("rattler", "libmamba")],
)
def test_config_set_solver(conda, condarc, tmp_path, solver, baseline_solver):
    """``conda config --set solver <s>`` writes the solver and later solves use it.

    The local channel has ``a`` requiring ``b >=2.0`` but only ``b 1.0``, so every
    solver fails, each with its own error type. A different baseline solver is
    configured first, so the target's error proves the setting changed solver
    selection rather than matching conda's default.
    """
    channel = build_local_channel(
        tmp_path / "channel", [Package("a", "1.0", depends=("b >=2.0",)), Package("b", "1.0")]
    )

    def assert_unsolvable_create_uses(expected_solver: str) -> None:
        conda(
            "create",
            "--dry-run",
            "-n",
            "unsolvable",
            "a",
            "-c",
            channel.as_uri(),
            "--override-channels",
        ).assert_error(code=1, contains=SOLVER_UNSATISFIABLE_ERRORS[expected_solver])

    conda("config", "--set", "solver", baseline_solver).assert_ok()
    assert_unsolvable_create_uses(baseline_solver)

    conda("config", "--set", "solver", solver).assert_ok()
    written_config = yaml.safe_load(condarc.read_text())
    assert written_config == {"solver": solver}, (
        f"Unexpected .condarc after --set: {written_config}"
    )
    assert_unsolvable_create_uses(solver)


@pytest.mark.covers(96)
@pytest.mark.smoke
def test_config_set_ssl_verify_false_disables_certificate_verification(
    conda, condarc, self_signed_channel
):
    """``conda config --set ssl_verify false`` accepts an untrusted certificate.

    The channel serves a throwaway self-signed certificate, so the same channel
    fails with conda's SSL error on the default setting and yields the channel's
    package records once the boolean is written.
    """
    package = self_signed_channel.package
    search = (
        "search",
        "-c",
        self_signed_channel.url,
        "--override-channels",
        package.name,
        "--json",
    )

    failure = conda(*search, extra_env=LOOPBACK_SEARCH_ENV).assert_error(code=1)
    payload = failure.json()
    assert payload["exception_name"] == "CondaSSLError", (
        f"Expected the untrusted certificate to fail verification. "
        f"Got: {payload['exception_name']!r}"
    )

    conda("config", "--set", "ssl_verify", "false").assert_ok()
    written_config = yaml.safe_load(condarc.read_text())
    assert written_config == {"ssl_verify": False}, (
        f"Unexpected .condarc after --set: {written_config}"
    )

    result = conda(*search, extra_env=LOOPBACK_SEARCH_ENV).assert_ok()
    search_result = SearchResult.from_json(result)
    assert set(search_result.packages) == {package.name}, (
        f"Expected the channel's package after disabling verification. "
        f"Got: {set(search_result.packages)}"
    )
    records = search_result.get(package.name)
    assert len(records) == 1, f"Expected the channel's single {package.name} record. Got: {records}"
    assert records[0].version == package.version, (
        f"Expected {package.name} version {package.version}. Got: {records[0].version}"
    )
    record_channel = f"{self_signed_channel.url}/noarch"
    assert records[0].channel == record_channel, (
        f"Expected the record's channel to be {record_channel!r}. Got: {records[0].channel!r}"
    )


@pytest.mark.covers(114)
def test_config_add_channels_to_empty_condarc(conda, condarc):
    """``conda config --add channels conda-forge`` on an empty .condarc writes only conda-forge."""
    conda("config", "--add", "channels", "conda-forge").assert_ok()

    written_config = yaml.safe_load(condarc.read_text())
    assert written_config == {"channels": ["conda-forge"]}, (
        f"Unexpected .condarc after --add: {written_config}"
    )


@pytest.mark.covers(114, 115)
@pytest.mark.parametrize("flag", ["--add", "--prepend"])
def test_config_add_channels_prepends_conda_forge(conda, condarc, flag):
    """``conda config --add/--prepend channels conda-forge`` prepends it to .condarc channels.

    The file starts with ``defaults``, so appending instead of prepending produces
    the opposite order and fails the exact comparison.
    """
    condarc.write_text(
        dedent("""\
        channels:
          - defaults
        """)
    )

    conda("config", flag, "channels", "conda-forge").assert_ok()

    written_config = yaml.safe_load(condarc.read_text())
    assert written_config == {"channels": ["conda-forge", "defaults"]}, (
        f"Unexpected .condarc after {flag}: {written_config}"
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


@pytest.mark.covers(61)
def test_config_validate_accepts_valid_condarc(conda, condarc):
    """``conda config --validate`` is silent when every configuration source is valid.

    The same file makes ``--get channel_priority`` print its configured value, so this
    silence also distinguishes validation from the value-printing commands.
    """
    condarc.write_text(
        dedent("""\
        channels:
          - conda-forge
        channel_priority: strict
        """)
    )

    result = conda("config", "--validate").assert_ok()
    assert result.stdout == "", f"Expected no stdout, got: {result.stdout!r}"
    assert result.stderr == "", f"Expected no stderr, got: {result.stderr!r}"


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


@pytest.mark.covers(62)
def test_config_validate_reports_unparseable_condarc(conda, condarc):
    """``conda config --validate`` warns about an unreadable .condarc but still exits 0.

    conda drops a source it cannot parse, so the YAML error is logged with the file and
    position instead of failing the command.
    """
    condarc.write_text(
        dedent("""\
        channel_priority: strict
        &(*#*&Gjia
        """)
    )

    result = conda("config", "--validate").assert_ok()
    assert result.stdout == "", f"Expected no stdout, got: {result.stdout!r}"
    expected_warning = [
        f"Ignoring configuration file ({condarc}) due to error:",
        "Unable to load configuration file.",
        f"  path: {condarc}",
        "  reason: invalid yaml at line 2, column 0",
    ]
    assert result.stderr.splitlines()[:4] == expected_warning, (
        f"Unexpected validation warning: {result.stderr!r}"
    )


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.covers(62)
def test_config_validate_rejects_invalid_channel_priority(conda, condarc):
    """``conda config --validate`` fails and names the invalid value and valid choices."""
    condarc.write_text("channel_priority: invalid\n")

    result = conda("config", "--validate")
    result.assert_error(code=1)
    assert result.stdout == "", f"Expected no stdout, got: {result.stdout!r}"
    expected_error = [
        (
            "CustomValidationError: Parameter channel_priority = 'invalid' declared in "
            f"{condarc} is invalid."
        ),
        "'invalid' is not a valid ChannelPriority",
        "Valid choices for channel_priority: 'strict', 'flexible', 'disabled'",
    ]
    assert result.stderr.strip("\n").splitlines() == expected_error, (
        f"Unexpected validation error: {result.stderr!r}"
    )


@pytest.mark.covers(646)
def test_config_invalid_flag(conda):
    """``conda config --invalid-flag`` fails with unrecognized argument error."""
    result = conda("config", "--invalid-flag")
    result.assert_error(
        code=2,
        contains="unrecognized arguments: --invalid-flag",
    )
