# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda install --help`` output."""

from __future__ import annotations


def test_install_help(conda):
    """``conda install --help`` documents usage, sections, and available options."""
    result = conda("install", "--help").assert_ok()
    output = result.stdout

    expected = (
        "usage:",
        "conda install",
        "Install a list of packages into a specified conda environment.",
        "positional arguments:",
        "package_spec",
        "options:",
        "-h, --help",
        "--name",
        "--prefix",
        "--channel",
        "--revision",
        "--no-deps",
        "--only-deps",
        "--freeze-installed",
        "--update-deps",
        "--update-all",
        "--force-reinstall",
        "--solver",
        "--dry-run",
        "--json",
        "--offline",
        "-k, --insecure",
        "--yes",
        "--file",
        "--copy",
        "--clobber",
        "--override-channels",
        "--strict-channel-priority",
        "--no-channel-priority",
        "--download-only",
        "Target Environment Specification:",
        "Channel Customization:",
        "Solver Mode Modifiers:",
        "Package Linking and Install-time Options:",
        "Networking Options:",
        "Output, Prompt, and Flow Control Options:",
    )
    missing = [e for e in expected if e not in output]
    assert not missing, f"help output missing {missing}. Command output:\n{output}"
