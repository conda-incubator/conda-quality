# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda install --help`` output."""

from __future__ import annotations

from help_command_helpers import has_help_item, normalized, option_pairs_from_help

EXPECTED_HELP = {
    "usage": ("usage: conda install",),
    "description": ("Install a list of packages into a specified conda environment.",),
    "positional arguments": ("positional arguments:", "package_spec"),
    "options": ("options:",),
    "target environment specification": ("Target Environment Specification:",),
    "channel customization": ("Channel Customization:",),
    "solver mode modifiers": ("Solver Mode Modifiers:",),
    "package linking and install-time options": ("Package Linking and Install-time Options:",),
    "networking options": ("Networking Options:",),
    "output options": ("Output, Prompt, and Flow Control Options:",),
    "examples": (
        "Examples:",
        "conda install scipy",
        "conda install -n myenv scipy curl wheel",
        "conda install -p path/to/myenv python=3.11",
    ),
}

# Keys sorted for readability; compared as a dict, so output order isn't asserted.
EXPECTED_OPTION_DESCRIPTIONS = {
    "--clobber": (
        "Allow clobbering (i.e. overwriting) of overlapping file paths within packages and "
        "suppress related warnings."
    ),
    "--console {classic,json}": "Select the backend to use for normal output rendering.",
    "--copy": "Install all packages using copies instead of hard- or soft-linking.",
    "--dev": (
        "Use `sys.executable -m conda` in wrapper scripts instead of CONDA_EXE. This is "
        "mainly for use during tests where we test new conda sources against old Python "
        "versions."
    ),
    "--download-only": (
        "Solve an environment and ensure package caches are populated, but exit prior to "
        "unlinking and linking packages into the prefix."
    ),
    (
        "--environment-specifier, --env-spec "
        "{cep-24,environment-yaml,env.yml,conda-lock-v1,conda-lock,"
        "environment.yml,explicit,rattler-lock-v6,pixi,pixi-lock-v6,"
        "requirements.txt,requirements,reqs}"
    ): (
        "`--env-spec` is pending deprecation and will be removed in 27.3. Use the `--format` "
        "flag instead."
    ),
    "--experimental {jlap,lock}": (
        "`--experimental` is pending deprecation and will be removed in 27.3. Deprecated: "
        "jlap and lock no longer supported."
    ),
    "--force-reinstall": (
        "Ensure that any user-requested package for the current operation is uninstalled and "
        "reinstalled, even if that package already exists in the environment."
    ),
    "--format FORMAT": (
        "Override auto-detection of the input file's format. See `conda export --help` for "
        "the formats available in your installation. Aliases are interchangeable with "
        "canonical names."
    ),
    "--freeze-installed, --no-update-deps": (
        "Do not update or change already-installed dependencies."
    ),
    "--json": "Report all output as json. Suitable for using conda programmatically.",
    "--no-channel-priority": (
        "Package version takes precedence over channel priority. Overrides the value given "
        "by `conda config --show channel_priority`."
    ),
    "--no-deps": (
        "Do not install, update, remove, or change dependencies. This WILL lead to broken "
        "environments and inconsistent behavior. Use at your own risk."
    ),
    "--no-lock": "Disable locking when reading, updating index (repodata.json) cache.",
    "--no-pin": "Ignore pinned file.",
    "--no-shortcuts": "Don't install start menu shortcuts",
    "--offline": "Offline mode. Don't connect to the Internet.",
    "--only-deps": "Only install dependencies.",
    "--override-frozen": (
        "DANGEROUS. Use at your own risk. Ignore protections if the environment is frozen."
    ),
    "--repodata-fn REPODATA_FNS": (
        "Specify file name of repodata on the remote server where your channels are "
        "configured or within local backups. Conda will try whatever you specify, but will "
        "ultimately fall back to repodata.json if your specs are not satisfiable with what "
        "you specify here. This is used to employ repodata that is smaller and reduced in "
        "time scope. You may pass this flag more than once. Leftmost entries are tried "
        "first, and the fallback to repodata.json is added for you automatically. For more "
        "information, see conda config --describe repodata_fns."
    ),
    "--repodata-use-shards, --no-repodata-use-shards": (
        "Use sharded repodata if available. Enabled by default."
    ),
    "--repodata-use-zst, --no-repodata-use-zst": (
        "Check for/do not check for repodata.json.zst. Enabled by default."
    ),
    "--revision REVISION": "Revert to the specified REVISION.",
    "--shortcuts-only SHORTCUTS_ONLY": (
        "Install shortcuts only for this package name. Can be used several times."
    ),
    "--show-channel-urls": (
        "Show channel urls. Overrides the value given by `conda config --show show_channel_urls`."
    ),
    "--solver {classic,libmamba,rattler}": "Choose which solver backend to use.",
    "--strict-channel-priority": (
        "Packages in lower priority channels are not considered if a package with the same "
        "name appears in a higher priority channel."
    ),
    "--update-all, --all": "Update all installed packages in the environment.",
    "--update-deps": "Update dependencies that have available updates.",
    "--update-specs": "Update based on provided specifications.",
    "--use-local": "Use locally built packages. Identical to '-c local'.",
    "-C, --use-index-cache": (
        "Use cache of channel index files, even if it has expired. This is useful if you "
        "don't want conda to check whether a new version of the repodata file exists, which "
        "will save bandwidth."
    ),
    "-O, --override-channels": "Do not search default or .condarc channels. Requires --channel.",
    "-S, --satisfied-skip-solve": (
        "Exit early and do not run the solver if the requested specs are satisfied. Also "
        "skips aggressive updates as configured by the 'aggressive_update_packages' config "
        "setting. Use 'conda config --describe aggressive_update_packages' to view your "
        "setting. --satisfied-skip-solve is similar to the default behavior of 'pip "
        "install'."
    ),
    "-c, --channel CHANNEL": (
        "Additional channel to search for packages. These are URLs searched in the order "
        "they are given (including local directories using the 'file://' syntax or simply "
        "a path like '/home/conda/mychan' or '../mychan'). Then, the defaults or "
        "channels from .condarc are searched (unless --override-channels is given). You can "
        "use 'defaults' to get the default packages for conda. You can also use any name "
        "and the .condarc channel_alias value will be prepended. The default channel_alias "
        "is https://conda.anaconda.org/."
    ),
    "-d, --dry-run": "Only display what would have been done.",
    "-f, --file FILE": (
        "Read environment or package specs from a file. The format is detected from the "
        "filename or contents. Which formats are supported depends on the installed plugins "
        "(see the epilog for the list available here). Custom filenames require --format. "
        "May be repeated (e.g. --file=file1 --file=file2)."
    ),
    "-h, --help": "Show this help message and exit.",
    "-k, --insecure": (
        'Allow conda to perform "insecure" SSL connections and transfers. Equivalent to '
        "setting 'ssl_verify' to 'false'."
    ),
    "-n, --name ENVIRONMENT": "Name of environment.",
    "-p, --prefix PATH": "Full path to environment location (i.e. prefix).",
    "-q, --quiet": "Do not display progress bar.",
    "-v, --verbose": (
        "Can be used multiple times. Once for detailed output, twice for INFO logging, "
        "thrice for DEBUG logging, four times for TRACE logging."
    ),
    "-y, --yes": (
        "Sets any confirmation values to 'yes' automatically. Users will not be asked to "
        "confirm any adding, deleting, backups, etc."
    ),
}


# =============================================================================
# Positive test cases
# =============================================================================


def test_install_help(conda):
    """``conda install --help`` documents usage, sections, and examples."""
    output = conda("install", "--help").assert_ok().stdout
    collapsed = normalized(output)
    missing = {}
    for section, items in EXPECTED_HELP.items():
        section_missing = [item for item in items if not has_help_item(item, collapsed)]
        if section_missing:
            missing[section] = section_missing
    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"


def test_install_help_option_descriptions_pair_correctly(conda):
    """Each option is paired with its own description."""
    output = conda("install", "--help").assert_ok().stdout
    assert option_pairs_from_help(output) == EXPECTED_OPTION_DESCRIPTIONS, f"Output:\n{output}"


def test_install_help_short_flag_matches_long_form(conda):
    """``conda install -h`` renders identically to ``--help``."""
    long_form = conda("install", "--help").assert_ok().stdout
    short_form = conda("install", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"
