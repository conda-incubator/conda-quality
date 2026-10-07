# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda install --help`` output."""

from __future__ import annotations

import pytest
from help_command_helpers import (
    HELP_OPTION,
    OUTPUT_CONTROL_OPTIONS,
    SHOW_CHANNEL_URLS_OPTION,
    TARGET_ENVIRONMENT_OPTIONS,
    parse_help,
)

# Sections in render order; entry keys sorted (compared as dicts, so order isn't asserted).
EXPECTED_HELP = {
    "usage": "usage: conda install",
    "usage_flags": {
        "--clobber",
        "--console",
        "--copy",
        "--dev",
        "--download-only",
        "--environment-specifier",
        "--exclude-newer",
        "--experimental",
        "--force-reinstall",
        "--format",
        "--freeze-installed",
        "--json",
        "--no-channel-priority",
        "--no-deps",
        "--no-lock",
        "--no-pin",
        "--no-repodata-use-shards",
        "--no-repodata-use-zst",
        "--no-shortcuts",
        "--offline",
        "--only-deps",
        "--override-frozen",
        "--repodata-fn",
        "--repodata-use-shards",
        "--repodata-use-zst",
        "--revision",
        "--shortcuts-only",
        "--show-channel-urls",
        "--solver",
        "--strict-channel-priority",
        "--update-all",
        "--update-deps",
        "--update-specs",
        "--use-local",
        "-C",
        "-O",
        "-S",
        "-c",
        "-d",
        "-f",
        "-h",
        "-k",
        "-n",
        "-p",
        "-q",
        "-v",
        "-y",
    },
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
        "positional arguments:": {
            "entries": {
                "package_spec": "List of packages to install or update in the conda environment.",
            },
        },
        "options:": {
            "entries": {
                **HELP_OPTION,
                "--dev": (
                    "`--dev` is pending deprecation and will be removed in 27.9. Set "
                    "`PYTHONPATH` to the conda source root instead."
                ),
                "--environment-specifier, --env-spec": (
                    "`--env-spec` is pending deprecation and will be removed in 27.3. Use the "
                    "`--format` flag instead."
                ),
                "--format": (
                    "Override auto-detection of the input file's format. See `conda export "
                    "--help` for the formats available in your installation. Aliases are "
                    "interchangeable with canonical names."
                ),
                "--override-frozen": (
                    "DANGEROUS. Use at your own risk. Ignore protections if the environment is "
                    "frozen."
                ),
                "--revision": "Revert to the specified REVISION.",
                "-f, --file": (
                    "Read environment or package specs from a file. The format is detected from "
                    "the filename or contents. Which formats are supported depends on the "
                    "installed plugins (see the epilog for the list available here). Custom "
                    "filenames require --format. May be repeated (e.g. --file=file1 "
                    "--file=file2)."
                ),
            },
        },
        "Target Environment Specification:": {"entries": TARGET_ENVIRONMENT_OPTIONS},
        "Channel Customization:": {
            "entries": {
                "--experimental": (
                    "`--experimental` is pending deprecation and will be removed in 27.3. "
                    "Deprecated: jlap and lock no longer supported."
                ),
                "--no-lock": (
                    "Disable locking when reading, updating index (repodata.json) cache."
                ),
                "--repodata-fn": (
                    "Specify file name of repodata on the remote server where your channels are "
                    "configured or within local backups. Conda will try whatever you specify, "
                    "but will ultimately fall back to repodata.json if your specs are not "
                    "satisfiable with what you specify here. This is used to employ repodata "
                    "that is smaller and reduced in time scope. You may pass this flag more "
                    "than once. Leftmost entries are tried first, and the fallback to "
                    "repodata.json is added for you automatically. For more information, see "
                    "conda config --describe repodata_fns."
                ),
                "--repodata-use-shards, --no-repodata-use-shards": (
                    "Use sharded repodata if available. Enabled by default."
                ),
                "--repodata-use-zst, --no-repodata-use-zst": (
                    "Check for/do not check for repodata.json.zst. Enabled by default."
                ),
                "--use-local": "Use locally built packages. Identical to '-c local'.",
                "-O, --override-channels": (
                    "Do not search default or .condarc channels. Requires --channel."
                ),
                "-c, --channel": (
                    "Additional channel to search for packages. These are URLs searched in the "
                    "order they are given (including local directories using the 'file://' "
                    "syntax or simply a path like '/home/conda/mychan' or '../mychan'). Then, "
                    "the defaults or channels from .condarc are searched (unless "
                    "--override-channels is given). You can use 'defaults' to get the default "
                    "packages for conda. You can also use any name and the .condarc "
                    "channel_alias value will be prepended. The default channel_alias is "
                    "https://conda.anaconda.org/."
                ),
            },
        },
        "Solver Mode Modifiers:": {
            "entries": {
                "--exclude-newer": (
                    "Exclude packages published more recently than the given duration (e.g. 7d, "
                    "3d12h, 1w) or date (e.g. 2026-04-01, 2026-04-01T12:00:00Z). Date-only "
                    "values use the start of the next UTC day. Supply 0 for no delay, using "
                    "the current time as the cutoff. Channel and per-package overrides can be "
                    "set via channel_settings and exclude_newer_package in .condarc."
                ),
                "--force-reinstall": (
                    "Ensure that any user-requested package for the current operation is "
                    "uninstalled and reinstalled, even if that package already exists in the "
                    "environment."
                ),
                "--freeze-installed, --no-update-deps": (
                    "Do not update or change already-installed dependencies."
                ),
                "--no-channel-priority": (
                    "Package version takes precedence over channel priority. Overrides the "
                    "value given by `conda config --show channel_priority`."
                ),
                "--no-deps": (
                    "Do not install, update, remove, or change dependencies. This WILL lead to "
                    "broken environments and inconsistent behavior. Use at your own risk."
                ),
                "--no-pin": "Ignore pinned file.",
                "--only-deps": "Only install dependencies.",
                "--solver": "Choose which solver backend to use.",
                "--strict-channel-priority": (
                    "Packages in lower priority channels are not considered if a package with "
                    "the same name appears in a higher priority channel."
                ),
                "--update-all, --all": "Update all installed packages in the environment.",
                "--update-deps": "Update dependencies that have available updates.",
                "--update-specs": "Update based on provided specifications.",
                "-S, --satisfied-skip-solve": (
                    "Exit early and do not run the solver if the requested specs are "
                    "satisfied. Also skips aggressive updates as configured by the "
                    "'aggressive_update_packages' config setting. Use 'conda config --describe "
                    "aggressive_update_packages' to view your setting. "
                    "--satisfied-skip-solve is similar to the default behavior of 'pip install'."
                ),
            },
        },
        "Package Linking and Install-time Options:": {
            "entries": {
                "--clobber": (
                    "Allow clobbering (i.e. overwriting) of overlapping file paths within "
                    "packages and suppress related warnings."
                ),
                "--copy": "Install all packages using copies instead of hard- or soft-linking.",
                "--no-shortcuts": "Don't install start menu shortcuts",
                "--shortcuts-only": (
                    "Install shortcuts only for this package name. Can be used several times."
                ),
            },
        },
        "Networking Options:": {
            "entries": {
                "--offline": "Offline mode. Don't connect to the Internet.",
                "-C, --use-index-cache": (
                    "Use cache of channel index files, even if it has expired. This is useful "
                    "if you don't want conda to check whether a new version of the repodata "
                    "file exists, which will save bandwidth."
                ),
                "-k, --insecure": (
                    'Allow conda to perform "insecure" SSL connections and transfers. '
                    "Equivalent to setting 'ssl_verify' to 'false'."
                ),
            },
        },
        "Output, Prompt, and Flow Control Options:": {
            "entries": {
                **OUTPUT_CONTROL_OPTIONS,
                **SHOW_CHANNEL_URLS_OPTION,
                "--download-only": (
                    "Solve an environment and ensure package caches are populated, but exit "
                    "prior to unlinking and linking packages into the prefix."
                ),
                "-d, --dry-run": "Only display what would have been done.",
                "-y, --yes": (
                    "Sets any confirmation values to 'yes' automatically. Users will not be "
                    "asked to confirm any adding, deleting, backups, etc."
                ),
            },
        },
        "Examples:": {
            "prose": [
                "Install the package 'scipy' into the currently-active environment:",
                "conda install scipy",
                "Install a list of packages into an environment, myenv:",
                "conda install -n myenv scipy curl wheel",
                "Install a specific version of 'python' into an environment, myenv:",
                "conda install -p path/to/myenv python=3.11",
            ],
        },
    },
}

# =============================================================================
# Positive test cases
# =============================================================================


def test_install_help_matches_contract(conda, conda_base_python):
    """``conda install --help`` renders exactly the documented help."""
    if conda_base_python < (3, 11):
        pytest.skip(
            "conda/conda#16653: Python < 3.11 appends `(default: Null)` to the repodata flags"
        )
    output = conda("install", "--help").assert_ok().stdout
    assert parse_help(output) == EXPECTED_HELP, f"Output:\n{output}"


def test_install_help_short_flag_matches_long_form(conda):
    """``conda install -h`` renders identically to ``--help``."""
    long_form = conda("install", "--help").assert_ok().stdout
    short_form = conda("install", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"
