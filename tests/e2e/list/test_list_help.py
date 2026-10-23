# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda list``."""

import pytest
from shared.help_command_helpers import parse_help

# Each section maps its flags (aliases grouped together) to their fixed choices; set() means none.
EXPECTED_HELP = {
    "usage": "usage: conda list",
    "description": "List installed packages in a conda environment.",
    "sections": {
        "positional arguments:": {"regex": set()},
        "options:": {
            frozenset({"-h", "--help"}): set(),
            frozenset({"--show-channel-urls"}): set(),
            frozenset({"--auth"}): set(),
            frozenset({"--explicit"}): set(),
            frozenset({"--fields"}): set(),
            frozenset({"--md5"}): set(),
            frozenset({"--no-pip"}): set(),
            frozenset({"--reverse"}): set(),
            frozenset({"--sha256"}): set(),
            frozenset({"--size"}): set(),
            frozenset({"-c", "--canonical"}): set(),
            frozenset({"-e", "--export"}): set(),
            frozenset({"-f", "--full-name"}): set(),
            frozenset({"-r", "--revisions"}): set(),
        },
        "Target Environment Specification:": {
            frozenset({"-n", "--name"}): set(),
            frozenset({"-p", "--prefix"}): set(),
        },
        "Output, Prompt, and Flow Control Options:": {
            frozenset({"--console"}): {"classic", "json"},
            frozenset({"--json"}): set(),
            frozenset({"-q", "--quiet"}): set(),
            frozenset({"-v", "--verbose"}): set(),
        },
    },
}


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(438)
def test_list_help_matches_contract(conda):
    """``conda list --help`` renders the expected structural contract."""
    output = conda("list", "--help").assert_ok().stdout
    assert parse_help(output) == EXPECTED_HELP, f"Output:\n{output}"
