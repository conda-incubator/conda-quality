# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda create``."""

from __future__ import annotations

import pytest
from shared.help_command_helpers import flags, parse_help

EXPECTED_HELP = {
    "usage": "usage: conda create",
    "description": (
        "Create a new conda environment from a list of specified packages. Environments can be "
        "created from package specs on the command line, from an input file whose format is "
        "detected from its name or contents, or as a clone of an existing environment. See the "
        "epilog for the input formats available in your installation. To use the newly-created "
        "environment, use 'conda activate envname'. This command requires either the -n NAME or "
        "-p PREFIX option unless --dry-run or --download-only is specified."
    ),
    "sections": {
        "positional arguments:": {"package_spec": set()},
        "options:": flags(
            "-h, --help",
            "--clone",
            "-f, --file",
            (
                "--environment-specifier, --env-spec",
                {
                    "cep-24",
                    "environment-yaml",
                    "env.yml",
                    "conda-lock-v1",
                    "conda-lock",
                    "environment.yml",
                    "explicit",
                    "rattler-lock-v6",
                    "pixi",
                    "pixi-lock-v6",
                    "requirements.txt",
                    "requirements",
                    "reqs",
                },
            ),
            "--format",
            "--dev",
        ),
        "Target Environment Specification:": flags("-n, --name", "-p, --prefix"),
        "Channel Customization:": flags(
            "-c, --channel",
            "--use-local",
            "-O, --override-channels",
            "--repodata-fn",
            ("--experimental", {"jlap", "lock"}),
            "--no-lock",
            "--repodata-use-zst, --no-repodata-use-zst",
            "--repodata-use-shards, --no-repodata-use-shards",
            "--subdir, --platform",
        ),
        "Solver Mode Modifiers:": flags(
            "--exclude-newer",
            "--strict-channel-priority",
            "--no-channel-priority",
            "--no-deps",
            "--only-deps",
            "--no-pin",
            "--no-default-packages",
            ("--solver", {"classic", "libmamba", "rattler"}),
        ),
        "Package Linking and Install-time Options:": flags(
            "--copy", "--no-shortcuts", "--shortcuts-only", "--clobber"
        ),
        "Networking Options:": flags("-C, --use-index-cache", "-k, --insecure", "--offline"),
        "Output, Prompt, and Flow Control Options:": flags(
            "--json",
            ("--console", {"classic", "json"}),
            "-v, --verbose",
            "-q, --quiet",
            "-d, --dry-run",
            "-y, --yes",
            "--download-only",
            "--show-channel-urls",
        ),
    },
}


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(150)
def test_create_help_matches_contract(conda):
    """``conda create --help`` renders the expected structural contract."""
    output = conda("create", "--help").assert_ok().stdout
    assert parse_help(output) == EXPECTED_HELP, f"Output:\n{output}"
