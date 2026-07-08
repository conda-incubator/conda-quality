# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda activate flag.

Currently, this module contains just one test to show how to use conda
test automation framework for shell-dependent commands.
"""

from __future__ import annotations

import pytest

from conda_e2e.parsers.info import CondaInfo
from conda_e2e.shells import Shell
from conda_e2e.utils import env_exists, env_prefix, unique_env_name


def _stack_flag(shell: Shell) -> str:
    """Return the stack-activation flag for this shell (PowerShell uses -Stack)."""
    return "-Stack" if shell in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL) else "--stack"


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


@pytest.mark.parametrize(
    ("use_path", "expected_fragment"),
    [
        (False, "Could not find conda environment:"),
        (True, "Not a conda environment:"),
    ],
    ids=["name", "path"],
)
def test_activate_nonexistent_with_path_or_name(conda_shell, envs_dir, use_path, expected_fragment):
    """Activate by missing env name or path fails."""
    name = unique_env_name()
    env_path = env_prefix(envs_dir, name)
    activate_target = str(env_path) if use_path else name

    assert not env_exists(env_path)

    result = conda_shell.run_in_activated_env(activate_target, "conda info --json")
    result.assert_error(code=1, contains=f"{expected_fragment} {activate_target}")


def test_activate_stack(conda_shell, conda, envs_dir):
    """``conda activate --stack`` stacks env on top of current env."""
    base_name = unique_env_name()
    stack_name = unique_env_name()
    base_path = env_prefix(envs_dir, base_name)
    stack_path = env_prefix(envs_dir, stack_name)

    conda("create", "-n", base_name).assert_ok()
    conda("create", "-n", stack_name).assert_ok()

    stack_flag = _stack_flag(conda_shell.shell)
    result = conda_shell.run_in_activated_env(
        base_name,
        f"conda activate {stack_flag} {stack_name}",
        "conda info --json",
    ).assert_ok()

    conda_info = CondaInfo.from_json(result)
    assert conda_info.active_prefix_name == stack_name
    assert conda_info.active_prefix == stack_path

    # Verify conda recorded a stacked activation
    is_stacked = any(
        k.startswith("CONDA_STACKED_") and str(v).lower() == "true"
        for k, v in conda_info.env_vars.items()
    )
    assert is_stacked, "CONDA_STACKED_* should be set to true after stacking"

    # Verify the base env is still present on PATH (the actual stacking effect)
    path_value = conda_info.env_vars.get("PATH", "")
    assert str(base_path) in path_value, (
        f"base env should still be present on PATH after stacking. PATH: {path_value}"
    )


def test_activate_stack_nonexistent_fails(conda_shell, conda):
    """Stacking a nonexistent env fails with appropriate error."""
    base_name = unique_env_name()
    missing_name = unique_env_name()

    conda("create", "-n", base_name).assert_ok()

    stack_flag = _stack_flag(conda_shell.shell)
    result = conda_shell.run_in_activated_env(
        base_name,
        f"conda activate {stack_flag} {missing_name}",
        "conda info --json",
    )
    # CMD maps inner activation failures to exit code 2; all other shells use 1
    expected_code = 2 if conda_shell.shell is Shell.CMD else 1
    result.assert_error(
        code=expected_code,
        contains=f"Could not find conda environment: {missing_name}",
    )
