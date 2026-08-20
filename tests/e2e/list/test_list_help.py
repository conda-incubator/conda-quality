# SPDX-License-Identifier: BSD-3-Clause
"""Help coverage for ``conda list``."""

from __future__ import annotations

import re

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
    "options": (
        "options:",
        "-h, --help",
        "--show-channel-urls",
        "--fields LIST_FIELDS",
        "--reverse",
        "-c, --canonical",
        "-f, --full-name",
        "--explicit",
        "--md5",
        "--sha256",
        "-e, --export",
        "-r, --revisions",
        "--size",
        "--no-pip",
        "--auth",
    ),
    "target environment specification": (
        "Target Environment Specification:",
        ("-n ENVIRONMENT, --name ENVIRONMENT", "-n, --name ENVIRONMENT"),
        ("-p PATH, --prefix PATH", "-p, --prefix PATH"),
    ),
    "output options": (
        "Output, Prompt, and Flow Control Options:",
        "--json",
        "--console",
        "-v, --verbose",
        "-q, --quiet",
    ),
    "option descriptions": (
        "List only packages matching this regular expression.",
        "Show this help message and exit.",
        "Show channel urls. Overrides the value given by `conda config --show show_channel_urls`.",
        "Comma-separated list of fields to print. Valid values:",
        "List installed packages in reverse order.",
        "Output canonical names of packages only.",
        "Only search for full names, i.e., ^<regex>$.",
        "List explicitly all installed conda packages with URL "
        "(output may be used by conda create --file).",
        "Add MD5 hashsum when using --explicit.",
        "Add SHA256 hashsum when using --explicit.",
        "Output explicit, machine-readable requirement strings instead of "
        "human-readable lists of packages.",
        "This output may be used by conda create --file.",
        "List the revision history.",
        "Show package and environment sizes.",
        "Do not include pip-only installed packages.",
        "In explicit mode, leave authentication details in package URLs.",
        "They are removed by default otherwise.",
        "Name of environment.",
        "Full path to environment location (i.e. prefix).",
        "Report all output as json. Suitable for using conda programmatically.",
        "Select the backend to use for normal output rendering.",
        "Can be used multiple times. Once for detailed output, twice for INFO logging, "
        "thrice for DEBUG "
        "logging, four times for TRACE logging.",
        "Do not display progress bar.",
    ),
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


def has_expected_help_item(item: str | tuple[str, ...], output: str) -> bool:
    """Return whether a help item or one of its portable renderings appears in output."""
    options = item if isinstance(item, tuple) else (item,)
    return any(normalized(option) in output for option in options)


def normalized(text: str) -> str:
    """Collapse wrapping and repeated whitespace for stable help comparisons."""
    return " ".join(text.split())


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


def test_list_help_documents_complete_public_surface(conda):
    """``conda list --help`` documents every option, section, and example."""
    output = conda("list", "--help").assert_ok().stdout
    collapsed = normalized(output)
    missing = {}
    for section, items in EXPECTED_HELP.items():
        section_missing = [item for item in items if not has_expected_help_item(item, collapsed)]
        if section_missing:
            missing[section] = section_missing
    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"

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
