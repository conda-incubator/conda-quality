# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda activate flag.

Currently, this module contains just one test to show how to use conda
test automation framework for shell-dependent commands.
"""

from __future__ import annotations

from conda_e2e.parsers.info import CondaInfo
from conda_e2e.utils import unique_env_name


def test_activate_makes_env_current(conda_shell, conda):
    """``conda activate`` is shell-specific, so it uses the ``conda_shell`` fixture.

    Pattern: create the env, then activate it through the shell and confirm conda
    reports it as active. This test runs once per shell available on the OS.
    """
    name = unique_env_name()
    conda("create", "-n", name).assert_ok()

    result = conda_shell.run_in_activated_env(name, "conda info --json").assert_ok()
    # Verify that `conda info` run in an activated env shows the correct prefix name.
    assert CondaInfo.from_json(result).active_prefix_name == name


def test_activate_help_list(conda_shell):
    """``conda activate --help`` via hooked shell documents core options."""
    result = conda_shell("conda activate --help")
    output = f"{result.stdout}\n{result.stderr}"

    result.assert_ok()

    expected = (
        "ActivateHelp: usage: conda activate",
        "-h, --help",
        "--stack",
        "--no-stack",
        "Show this help message and exit",
    )
    missing = [e for e in expected if e not in output]
    assert not missing, f"help output missing {missing}. Command output:\n{output}"
