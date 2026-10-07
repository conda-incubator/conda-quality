# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda list``."""

from __future__ import annotations

import re

from help_command_helpers import (
    HELP_OPTION,
    OUTPUT_CONTROL_OPTIONS,
    SHOW_CHANNEL_URLS_OPTION,
    TARGET_ENVIRONMENT_OPTIONS,
    parse_help,
)

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

# Sections in render order; entry keys sorted (compared as dicts, so order isn't asserted).
EXPECTED_HELP = {
    "usage": "usage: conda list",
    "usage_flags": {
        "--auth",
        "--console",
        "--explicit",
        "--fields",
        "--json",
        "--md5",
        "--no-pip",
        "--reverse",
        "--sha256",
        "--show-channel-urls",
        "--size",
        "-c",
        "-e",
        "-f",
        "-h",
        "-n",
        "-p",
        "-q",
        "-r",
        "-v",
    },
    "description": "List installed packages in a conda environment.",
    "sections": {
        "positional arguments:": {
            "entries": {
                "regex": "List only packages matching this regular expression.",
            },
        },
        "options:": {
            "entries": {
                **HELP_OPTION,
                **SHOW_CHANNEL_URLS_OPTION,
                "--auth": (
                    "In explicit mode, leave authentication details in package URLs. They are "
                    "removed by default otherwise."
                ),
                "--explicit": (
                    "List explicitly all installed conda packages with URL (output may be used "
                    "by conda create --file)."
                ),
                "--fields": (
                    "Comma-separated list of fields to print. Valid values: "
                    "arch,build,build_number,channel,channel_name,constrain "
                    "s,depends,dist_str,features,fn,license,license_family, "
                    "md5,name,noarch,package_type,requested_spec,requested_ "
                    "specs,sha256,size,subdir,timestamp,track_features,url, version."
                ),
                "--md5": "Add MD5 hashsum when using --explicit.",
                "--no-pip": "Do not include pip-only installed packages.",
                "--reverse": "List installed packages in reverse order.",
                "--sha256": "Add SHA256 hashsum when using --explicit.",
                "--size": "Show package and environment sizes.",
                "-c, --canonical": "Output canonical names of packages only.",
                "-e, --export": (
                    "Output explicit, machine-readable requirement strings instead of "
                    "human-readable lists of packages. This output may be used by conda create "
                    "--file."
                ),
                "-f, --full-name": (
                    "Only search for full names, i.e., ^<regex>$. --full- name NAME is "
                    "identical to regex '^NAME$'."
                ),
                "-r, --revisions": "List the revision history.",
            },
        },
        "Target Environment Specification:": {"entries": TARGET_ENVIRONMENT_OPTIONS},
        "Output, Prompt, and Flow Control Options:": {"entries": OUTPUT_CONTROL_OPTIONS},
        "Examples:": {
            "prose": [
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
            ],
        },
    },
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


def test_list_help_matches_contract(conda):
    """``conda list --help`` renders exactly the documented help."""
    output = conda("list", "--help").assert_ok().stdout
    assert parse_help(output) == EXPECTED_HELP, f"Output:\n{output}"

    assert list_fields_from_help(output) == LIST_FIELDS, (
        f"Unexpected valid --fields values: {list_fields_from_help(output)}\nOutput:\n{output}"
    )
    assert re.search(r"--full-(?:\n\s*)?name NAME is identical to regex '\^NAME\$'\.", output), (
        f"Missing --full-name continuation contract:\n{output}"
    )


def test_list_help_short_flag_matches_long_form(conda):
    """``conda list -h`` renders identically to ``--help``."""
    long_form = conda("list", "--help").assert_ok().stdout
    short_form = conda("list", "-h").assert_ok().stdout
    assert short_form == long_form, "-h should match --help output byte-for-byte"
