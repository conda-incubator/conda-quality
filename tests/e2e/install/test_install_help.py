# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda install --help`` output."""

from __future__ import annotations

import pytest
from shared.help_command_helpers import parse_help

# Each section maps its flags (aliases grouped together) to their fixed choices; set() means none.
EXPECTED_HELP = {
    "usage": "usage: conda install",
    "description": (
        "Install a list of packages into a specified conda environment. This command accepts "
        "a list of package specifications (e.g, bitarray=0.8) and installs a set of packages "
        "consistent with those specifications and compatible with the underlying environment. "
        "If full compatibility cannot be assured, an error is reported and the environment is "
        "not changed. Conda attempts to install the newest versions of the requested packages. "
        "To accomplish this, it may update some packages that are already installed, or install "
        "additional packages. To prevent existing packages from updating, use the "
        "--freeze-installed option. This may force conda to install older versions of the "
        "requested packages, and it does not prevent additional dependency packages from being "
        "installed. If you wish to skip dependency checking altogether, use the '--no-deps' "
        "option. This may result in an environment with incompatible packages, so this option "
        "must be used with great caution. conda can also be called with a list of explicit "
        "conda package filenames (e.g. ./lxml-3.2.0-py27_0.tar.bz2). Using conda in this mode "
        "implies the --no-deps option, and should likewise be used with great caution. Explicit "
        "filenames and package specifications cannot be mixed in a single command. When using "
        "--file, only the package list from the file is used. Any name or prefix in the file "
        "(e.g. in environment.yml) is ignored; packages are installed into the target "
        "environment (-n/-p or the current environment)."
    ),
    "sections": {
        "positional arguments:": {"package_spec": set()},
        "options:": {
            frozenset({"-h", "--help"}): set(),
            frozenset({"--dev"}): set(),
            frozenset({"--environment-specifier", "--env-spec"}): {
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
            frozenset({"--format"}): set(),
            frozenset({"--override-frozen"}): set(),
            frozenset({"--revision"}): set(),
            frozenset({"-f", "--file"}): set(),
        },
        "Target Environment Specification:": {
            frozenset({"-n", "--name"}): set(),
            frozenset({"-p", "--prefix"}): set(),
        },
        "Channel Customization:": {
            frozenset({"--experimental"}): {"jlap", "lock"},
            frozenset({"--no-lock"}): set(),
            frozenset({"--repodata-fn"}): set(),
            frozenset({"--repodata-use-shards", "--no-repodata-use-shards"}): set(),
            frozenset({"--repodata-use-zst", "--no-repodata-use-zst"}): set(),
            frozenset({"--use-local"}): set(),
            frozenset({"-O", "--override-channels"}): set(),
            frozenset({"-c", "--channel"}): set(),
        },
        "Solver Mode Modifiers:": {
            frozenset({"--exclude-newer"}): set(),
            frozenset({"--force-reinstall"}): set(),
            frozenset({"--freeze-installed", "--no-update-deps"}): set(),
            frozenset({"--no-channel-priority"}): set(),
            frozenset({"--no-deps"}): set(),
            frozenset({"--no-pin"}): set(),
            frozenset({"--only-deps"}): set(),
            frozenset({"--solver"}): {"classic", "libmamba", "rattler"},
            frozenset({"--strict-channel-priority"}): set(),
            frozenset({"--update-all", "--all"}): set(),
            frozenset({"--update-deps"}): set(),
            frozenset({"--update-specs"}): set(),
            frozenset({"-S", "--satisfied-skip-solve"}): set(),
        },
        "Package Linking and Install-time Options:": {
            frozenset({"--clobber"}): set(),
            frozenset({"--copy"}): set(),
            frozenset({"--no-shortcuts"}): set(),
            frozenset({"--shortcuts-only"}): set(),
        },
        "Networking Options:": {
            frozenset({"--offline"}): set(),
            frozenset({"-C", "--use-index-cache"}): set(),
            frozenset({"-k", "--insecure"}): set(),
        },
        "Output, Prompt, and Flow Control Options:": {
            frozenset({"--console"}): {"classic", "json"},
            frozenset({"--json"}): set(),
            frozenset({"-q", "--quiet"}): set(),
            frozenset({"-v", "--verbose"}): set(),
            frozenset({"--show-channel-urls"}): set(),
            frozenset({"--download-only"}): set(),
            frozenset({"-d", "--dry-run"}): set(),
            frozenset({"-y", "--yes"}): set(),
        },
    },
}

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(379)
def test_install_help_matches_contract(conda):
    """``conda install --help`` renders the expected structural contract."""
    output = conda("install", "--help").assert_ok().stdout
    assert parse_help(output) == EXPECTED_HELP, f"Output:\n{output}"
