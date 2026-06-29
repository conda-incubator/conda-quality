# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda activate flag.

Currently, this module contains just one test to show how to use conda
test automation framework for shell-dependent commands.
"""

from __future__ import annotations

import pytest

from conda_e2e.parsers.info import CondaInfo
from conda_e2e.utils import env_exists, env_prefix, unique_env_name


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
    result = conda_shell("conda activate --help").assert_ok()
    output = f"{result.stdout}\n{result.stderr}"

    expected = (
        "ActivateHelp: usage: conda activate",
        "Activate a conda environment.",
        "env_name_or_prefix",
        "-h, --help",
        "--stack",
        "--no-stack",
        "Show this help message and exit",
    )
    missing = [e for e in expected if e not in output]
    assert not missing, f"help output missing {missing}. Command output:\n{output}"


@pytest.mark.parametrize("use_path", [False, True], ids=["name", "path"])
def test_activate_with_path_or_name(conda_shell, conda, envs_dir, use_path):
    """Activate by env name or absolute path sets the correct active env."""
    name = unique_env_name()
    env_path = env_prefix(envs_dir, name)
    activate_target = str(env_path) if use_path else name

    conda("create", "-n", name).assert_ok()
    assert env_exists(env_path)

    result = conda_shell.run_in_activated_env(
        activate_target,
        "conda info --json",
    ).assert_ok()
    info = CondaInfo.from_json(result)
    assert info.active_prefix_name == name
    assert info.active_prefix == env_path


@pytest.mark.parametrize("use_path", [False, True], ids=["name", "path"])
def test_activate_nonexistent_with_path_or_name(conda_shell, envs_dir, use_path):
    """Activate by missing env name or path fails."""
    name = unique_env_name()
    env_path = env_prefix(envs_dir, name)
    activate_target = str(env_path) if use_path else name

    assert not env_exists(env_path)

    result = conda_shell.run_in_activated_env(activate_target, "conda info --json")
    if use_path:
        result.assert_error(code=1, contains=f"Not a conda environment: {env_path}")
    else:
        result.assert_error(code=1, contains=f"Could not find conda environment: {name}")
