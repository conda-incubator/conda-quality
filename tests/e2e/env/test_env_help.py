# SPDX-License-Identifier: BSD-3-Clause
"""Check ``conda env`` help structure, help shown without a subcommand, and invalid subcommands."""

import pytest
from shared.help_command_helpers import parse_help

# Each section maps its flags (aliases grouped together) to their fixed choices; set() means none.
EXPECTED_HELP = {
    "usage": "usage: conda env",
    "description": "",
    "sections": {
        "positional arguments:": {
            "command": {"config", "create", "export", "list", "remove", "update"},
        },
        "options:": {frozenset({"-h", "--help"}): set()},
    },
}


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(225)
def test_env_help_matches_contract(conda):
    """``conda env --help`` renders the expected structural contract."""
    output = conda("env", "--help").assert_ok().stdout
    assert parse_help(output) == EXPECTED_HELP, f"Output:\n{output}"


@pytest.mark.covers(274)
def test_env_without_subcommand_prints_help(conda):
    """``conda env`` with no subcommand prints its help, matching ``--help`` exactly."""
    bare = conda("env").assert_ok().stdout
    help_output = conda("env", "--help").assert_ok().stdout
    assert bare == help_output, "bare `conda env` should render the same help as --help"


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.covers(273)
def test_env_rejects_unknown_subcommand(conda):
    """``conda env <unknown>`` reports the invalid choice on stderr."""
    conda("env", "not-a-subcommand").assert_error(
        code=2, contains="argument command: invalid choice"
    )
