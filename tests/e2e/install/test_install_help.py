# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda install --help`` output."""

from __future__ import annotations

EXPECTED_HELP = {
    "usage": ("usage: conda install",),
    "description": (
        "Install a list of packages into a specified conda environment.",
        "This command accepts a list of package specifications",
        "Conda attempts to install the newest versions",
        "To prevent existing packages from updating",
        "use the --freeze-installed option",
        "If you wish to skip dependency checking altogether",
        "conda can also be called with a list of explicit conda package filenames",
        "Using conda in this mode implies the",
        "--no-deps",
        "option, and should likewise be used with great caution",
        "filenames and package specifications cannot be mixed",
        "When using --file, only the package list from the file is used",
    ),
    "positional arguments": (
        "positional arguments:",
        "package_spec",
    ),
    "options": (
        "options:",
        "-h, --help",
        "--revision",
        "--override-frozen",
        "--file",
        "--environment-specifier",
        "--env-spec",
        "--format",
        "--dev",
    ),
    "target environment specification": (
        "Target Environment Specification:",
        "--name",
        "--prefix",
    ),
    "channel customization": (
        "Channel Customization:",
        "--channel",
        "--use-local",
        "-O, --override-channels",
        "--repodata-fn",
        "--experimental",
        "--no-lock",
        "--repodata-use-zst",
        "--no-repodata-use-zst",
        "--repodata-use-shards",
        "--no-repodata-use-shards",
    ),
    "solver mode modifiers": (
        "Solver Mode Modifiers:",
        "--strict-channel-priority",
        "--no-channel-priority",
        "--no-deps",
        "--only-deps",
        "--no-pin",
        "--solver",
        "classic,libmamba,rattler",
        "--force-reinstall",
        "--freeze-installed",
        "--no-update-deps",
        "--update-deps",
        "-S, --satisfied-skip-solve",
        "--update-all",
        "--all",
        "--update-specs",
    ),
    "package linking and install-time options": (
        "Package Linking and Install-time Options:",
        "--copy",
        "--no-shortcuts",
        "--shortcuts-only",
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
        "--console",
        "-v, --verbose",
        "-q, --quiet",
        "-d, --dry-run",
        "-y, --yes",
        "--download-only",
        "--show-channel-urls",
    ),
    "examples": (
        "Examples:",
        "conda install scipy",
        "conda install -n myenv scipy curl wheel",
        "conda install -p path/to/myenv python=3.11",
    ),
}


# =============================================================================
# Positive test cases
# =============================================================================


def test_install_help(conda):
    """``conda install --help`` documents all flags, sections, and examples."""
    output = conda("install", "--help").assert_ok().stdout

    missing = {}
    for section, items in EXPECTED_HELP.items():
        absent = [item for item in items if item not in output]
        if absent:
            missing[section] = absent

    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"
