# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda env``.

Verifies ``conda env --help``/``-h`` against the full expected structure, and
that bare ``conda env`` prints the same help instead of an error.
"""

from help_command_helpers import HELP_OPTION, parse_help

# Sections in render order; entry keys sorted (compared as dicts, so order isn't asserted).
EXPECTED_HELP = {
    "usage": "usage: conda env",
    "usage_flags": {"-h"},
    "description": "",
    "sections": {
        "positional arguments:": {
            "entries": {
                "command": "",
                "config": "Configure a conda environment.",
                "create": "Create an environment based on an environment definition file.",
                "export": "Export a conda environment to a file.",
                "list": "An alias for `conda info --envs`. Lists all conda environments.",
                "remove": "Remove an environment.",
                "update": "Update the current environment based on environment file.",
            },
        },
        "options:": {"entries": HELP_OPTION},
    },
}


def test_env_help_matches_contract(conda):
    """``conda env --help`` renders exactly the documented help."""
    output = conda("env", "--help").assert_ok().stdout
    assert parse_help(output) == EXPECTED_HELP, f"Output:\n{output}"


def test_env_help_short_flag_matches_long_form(conda):
    """``conda env -h`` renders identically to ``--help``."""
    long_form = conda("env", "--help").assert_ok().stdout
    short_form = conda("env", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"


def test_env_without_subcommand_prints_help(conda):
    """Bare ``conda env`` exits zero and prints the full subcommand help."""
    output = conda("env").assert_ok().stdout
    assert output.startswith(EXPECTED_HELP["usage"])
    for subcommand in EXPECTED_HELP["sections"]["positional arguments:"]["entries"]:
        assert subcommand in output, f"Missing {subcommand!r} in bare `conda env` output"


def test_env_rejects_unknown_subcommand(conda):
    """``conda env nosuchcommand`` exits non-zero and points at the valid subcommands."""
    result = conda("env", "nosuchcommand")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert "config" in result.stderr
