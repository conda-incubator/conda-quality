# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda create``."""

from __future__ import annotations

from help_command_helpers import has_help_item

EXPECTED_HELP = {
    "usage": ("usage: conda create [-h] [--clone ENV] [-n ENVIRONMENT | -p PATH] [-c CHANNEL]",),
    "description": ("Create a new conda environment from a list of specified packages.",),
    "positional arguments": ("positional arguments:", "package_spec"),
    "options": (
        "options:",
        "-h, --help",
        "--clone ENV",
        ("-f FILE, --file FILE", "-f, --file FILE"),
        "--environment-specifier",
        "--env-spec",
        "--format FORMAT",
        "--dev",
    ),
    "target environment specification": (
        "Target Environment Specification:",
        ("-n ENVIRONMENT, --name ENVIRONMENT", "-n, --name ENVIRONMENT"),
        ("-p PATH, --prefix PATH", "-p, --prefix PATH"),
    ),
    "channel customization": (
        "Channel Customization:",
        ("-c CHANNEL, --channel CHANNEL", "-c, --channel CHANNEL"),
        "--use-local",
        "-O, --override-channels",
        "--repodata-fn REPODATA_FNS",
        "--experimental {jlap,lock}",
        "--no-lock",
        "--repodata-use-zst, --no-repodata-use-zst",
        "--repodata-use-shards, --no-repodata-use-shards",
        ("--subdir SUBDIR, --platform SUBDIR", "--subdir, --platform SUBDIR"),
    ),
    "solver mode modifiers": (
        "Solver Mode Modifiers:",
        "--strict-channel-priority",
        "--no-channel-priority",
        "--no-deps",
        "--only-deps",
        "--no-pin",
        "--no-default-packages",
        "--solver {classic,libmamba,rattler}",
    ),
    "package linking and install-time options": (
        "Package Linking and Install-time Options:",
        "--copy",
        "--no-shortcuts",
        "--shortcuts-only SHORTCUTS_ONLY",
        "--clobber",
    ),
    "networking options": (
        "Networking Options:",
        "-C, --use-index-cache",
        "-k, --insecure",
        "--offline",
    ),
    "output options": (
        "Output, Prompt, and Flow Control Options:",
        "--json",
        ("--console {classic,json}", "--console CONSOLE"),
        "-v, --verbose",
        "-q, --quiet",
        "-d, --dry-run",
        "-y, --yes",
        "--download-only",
        "--show-channel-urls",
    ),
    "examples": (
        "Examples:",
        "Create from package specs:",
        "conda create -n myenv python=3.12 numpy",
        "Create from an environment spec (solved at install time):",
        "conda create -n myenv --file environment.yml",
        "Create from a lockfile (no solve, exact reproduction):",
        "conda create -n myenv --file explicit.txt",
        "Clone an existing environment:",
        "conda create -n env2 --clone env1",
    ),
    "available input formats": (
        "Available input formats:",
        "Environment specs:",
        "cep-24 (aliases: environment-yaml, env.yml): environment.yml, environment.yaml",
        "environment.yml: environment.yml, environment.yaml",
        "requirements.txt (aliases: requirements, reqs): requirements.txt, spec.txt",
        "Lockfiles:",
        "conda-lock-v1 (aliases: conda-lock): conda-lock.yml, conda-lock.yaml",
        "explicit: explicit.txt",
        "rattler-lock-v6 (aliases: pixi, pixi-lock-v6): pixi.lock",
    ),
}


def test_create_help(conda):
    """``conda create --help`` documents every option, section, and example."""
    output = conda("create", "--help").assert_ok().stdout

    missing = {}
    for section, items in EXPECTED_HELP.items():
        absent = [item for item in items if not has_help_item(item, output)]
        if absent:
            missing[section] = absent

    assert not missing, f"Help missing items by section: {missing}\n\nOutput:\n{output}"


def test_create_help_short_flag_matches_long_form(conda):
    """``conda create -h`` renders identically to ``--help``."""
    long_form = conda("create", "--help").assert_ok().stdout
    short_form = conda("create", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"


def test_create_requires_name_or_prefix(conda):
    """``conda create`` with no arguments fails asking for -n or -p."""
    conda("create").assert_error(
        code=2, contains="one of the arguments -n/--name -p/--prefix is required"
    )
