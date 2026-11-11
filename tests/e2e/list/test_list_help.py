# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda list``."""

import pytest
from shared.help_command_helpers import flags, parse_help

EXPECTED_HELP = {
    "usage": "usage: conda list",
    "description": "List installed packages in a conda environment.",
    "sections": {
        "positional arguments:": {"regex": set()},
        "options:": flags(
            "-h, --help",
            "--show-channel-urls",
            "--auth",
            "--explicit",
            "--fields",
            "--md5",
            "--no-pip",
            "--reverse",
            "--sha256",
            "--size",
            "-c, --canonical",
            "-e, --export",
            "-f, --full-name",
            "-r, --revisions",
        ),
        "Target Environment Specification:": flags(
            "-n, --name",
            "-p, --prefix",
        ),
        "Output, Prompt, and Flow Control Options:": flags(
            ("--console", {"classic", "json"}),
            "--json",
            "-q, --quiet",
            "-v, --verbose",
        ),
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
