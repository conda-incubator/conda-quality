# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda install --help`` output."""

from __future__ import annotations

import pytest
from shared.help_command_helpers import flags, parse_help

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
        "options:": flags(
            "-h, --help",
            "--dev",
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
            "--override-frozen",
            "--revision",
            "-f, --file",
        ),
        "Target Environment Specification:": flags(
            "-n, --name",
            "-p, --prefix",
        ),
        "Channel Customization:": flags(
            ("--experimental", {"jlap", "lock"}),
            "--no-lock",
            "--repodata-fn",
            "--repodata-use-shards, --no-repodata-use-shards",
            "--repodata-use-zst, --no-repodata-use-zst",
            "--use-local",
            "-O, --override-channels",
            "-c, --channel",
        ),
        "Solver Mode Modifiers:": flags(
            "--exclude-newer",
            "--force-reinstall",
            "--freeze-installed, --no-update-deps",
            "--no-channel-priority",
            "--no-deps",
            "--no-pin",
            "--only-deps",
            ("--solver", {"classic", "libmamba", "pycosat", "rattler"}),
            "--strict-channel-priority",
            "--update-all, --all",
            "--update-deps",
            "--update-specs",
            "-S, --satisfied-skip-solve",
        ),
        "Package Linking and Install-time Options:": flags(
            "--clobber",
            "--copy",
            "--no-shortcuts",
            "--shortcuts-only",
        ),
        "Networking Options:": flags(
            "--offline",
            "-C, --use-index-cache",
            "-k, --insecure",
        ),
        "Output, Prompt, and Flow Control Options:": flags(
            ("--console", {"classic", "json"}),
            "--json",
            "-q, --quiet",
            "-v, --verbose",
            "--show-channel-urls",
            "--download-only",
            "-d, --dry-run",
            "-y, --yes",
        ),
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
