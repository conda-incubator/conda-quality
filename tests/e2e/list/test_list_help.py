# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda list``."""

from __future__ import annotations

import re

from help_command_helpers import has_help_item, normalized, option_pairs_from_help

LIST_FIELDS = (
    "arch",
    "build",
    "build_number",
    "channel",
    "channel_name",
    "constrains",
    "depends",
    "dist_str",
    "features",
    "fn",
    "license",
    "license_family",
    "md5",
    "name",
    "noarch",
    "package_type",
    "requested_spec",
    "requested_specs",
    "sha256",
    "size",
    "subdir",
    "timestamp",
    "track_features",
    "url",
    "version",
)

EXPECTED_HELP = {
    "usage": ("usage: conda list", "[--console", "[regex]"),
    "description": ("List installed packages in a conda environment.",),
    "positional arguments": ("positional arguments:", "regex"),
    "options": ("options:",),
    "target environment specification": ("Target Environment Specification:",),
    "output options": ("Output, Prompt, and Flow Control Options:",),
    "examples": (
        "Examples:",
        "List all packages in the current environment:",
        "conda list",
        "List all packages in reverse order:",
        "conda list --reverse",
        "List all packages installed into the environment 'myenv':",
        "conda list -n myenv",
        'List all packages that begin with the letters "py", using regex:',
        "conda list ^py",
        "List name and version only:",
        "conda list --fields name,version",
        "Save packages for future use:",
        "conda list --export > package-list.txt",
        "Reinstall packages from an export file:",
        "conda create -n myenv --file package-list.txt",
    ),
}


# Keys sorted for readability; compared as a dict, so output order isn't asserted.
EXPECTED_OPTION_DESCRIPTIONS = {
    "--auth": (
        "In explicit mode, leave authentication details in package URLs. They are removed by "
        "default otherwise."
    ),
    "--console {classic,json}": "Select the backend to use for normal output rendering.",
    "--explicit": (
        "List explicitly all installed conda packages with URL (output may be used by conda "
        "create --file)."
    ),
    "--fields LIST_FIELDS": (
        "Comma-separated list of fields to print. Valid values: "
        "arch,build,build_number,channel,channel_name,constrain "
        "s,depends,dist_str,features,fn,license,license_family, "
        "md5,name,noarch,package_type,requested_spec,requested_ "
        "specs,sha256,size,subdir,timestamp,track_features,url, version."
    ),
    "--json": "Report all output as json. Suitable for using conda programmatically.",
    "--md5": "Add MD5 hashsum when using --explicit.",
    "--no-pip": "Do not include pip-only installed packages.",
    "--reverse": "List installed packages in reverse order.",
    "--sha256": "Add SHA256 hashsum when using --explicit.",
    "--show-channel-urls": (
        "Show channel urls. Overrides the value given by `conda config --show show_channel_urls`."
    ),
    "--size": "Show package and environment sizes.",
    "-c, --canonical": "Output canonical names of packages only.",
    "-e, --export": (
        "Output explicit, machine-readable requirement strings instead of human-readable "
        "lists of packages. This output may be used by conda create --file."
    ),
    "-f, --full-name": (
        "Only search for full names, i.e., ^<regex>$. --full- name NAME is identical to "
        "regex '^NAME$'."
    ),
    "-h, --help": "Show this help message and exit.",
    "-n, --name ENVIRONMENT": "Name of environment.",
    "-p, --prefix PATH": "Full path to environment location (i.e. prefix).",
    "-q, --quiet": "Do not display progress bar.",
    "-r, --revisions": "List the revision history.",
    "-v, --verbose": (
        "Can be used multiple times. Once for detailed output, twice for INFO logging, "
        "thrice for DEBUG logging, four times for TRACE logging."
    ),
}


def list_fields_from_help(output: str) -> tuple[str, ...]:
    """Return canonical field names from the ``--fields`` valid-values block."""
    match = re.search(
        r"^  --fields LIST_FIELDS.*?(?=^  --)", output, flags=re.MULTILINE | re.DOTALL
    )
    if match is None:
        return ()
    values = match.group().partition("Valid values:")[2]
    return tuple(re.sub(r"\s+", "", values).removesuffix(".").split(","))


# =============================================================================
# Positive test cases
# =============================================================================


def test_list_help_documents_sections_and_examples(conda):
    """``conda list --help`` documents usage, sections, and examples."""
    output = conda("list", "--help").assert_ok().stdout
    collapsed = normalized(output)
    missing = {}
    for section, items in EXPECTED_HELP.items():
        section_missing = [item for item in items if not has_help_item(item, collapsed)]
        if section_missing:
            missing[section] = section_missing
    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"

    assert list_fields_from_help(output) == LIST_FIELDS, (
        f"Unexpected valid --fields values: {list_fields_from_help(output)}\nOutput:\n{output}"
    )
    assert re.search(r"--full-(?:\n\s*)?name NAME is identical to regex '\^NAME\$'\.", output), (
        f"Missing --full-name continuation contract:\n{output}"
    )


def test_list_help_option_descriptions_pair_correctly(conda):
    """Each option is paired with its own description."""
    output = conda("list", "--help").assert_ok().stdout
    assert option_pairs_from_help(output) == EXPECTED_OPTION_DESCRIPTIONS, f"Output:\n{output}"


def test_list_help_short_flag_matches_long_form(conda):
    """``conda list -h`` renders identically to ``--help``."""
    long_form = conda("list", "--help").assert_ok().stdout
    short_form = conda("list", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"
