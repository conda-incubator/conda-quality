# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda info`` environment-listing behavior (``-e``/``--envs``)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from assert_helpers import (
    assert_created_env_json_fields,
    assert_created_env_listed,
    assert_envs_headers_present,
)

from conda_e2e.parsers.env import EnvList
from conda_e2e.utils import is_same_path

if TYPE_CHECKING:
    from conda_e2e.parsers.env import EnvRecord
    from conda_e2e.result import CommandResult


OUTPUT_MODE_FLAGS = (None, "-q", "--quiet", "-v", "--verbose")


def _run_info_with_output_flag(conda, *info_args: str, output_flag: str | None) -> CommandResult:
    """Run ``conda info`` with optional quiet/verbose flag and assert success."""
    args = ["info", *info_args]
    if output_flag is not None:
        args.append(output_flag)
    return conda(*args).assert_ok()


def _get_created_env_from_stdout(result: CommandResult, env_path: Path) -> EnvRecord:
    """Return the created environment record from plain ``conda info --envs`` output."""
    created_env = EnvList.from_stdout(result).get_by_prefix(env_path)
    assert created_env is not None
    return created_env


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
@pytest.mark.parametrize("output_flag", OUTPUT_MODE_FLAGS)
def test_conda_info_envs_lists_created_env(conda, empty_env, envs_flag, output_flag):
    """``conda info -e``/``--envs`` lists a created env in plain, quiet, and verbose modes."""
    env_name, env_path = empty_env

    result = _run_info_with_output_flag(conda, envs_flag, output_flag=output_flag)
    assert_envs_headers_present(result.stdout, envs_flag)
    created_env = _get_created_env_from_stdout(result, env_path)
    assert_created_env_listed(created_env, env_name, env_path)


@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
def test_info_envs_json_lists_created_env(conda, empty_env, envs_flag):
    """``conda info -e``/``--envs`` with ``--json`` lists a newly created env."""
    env_name, env_path = empty_env

    result = conda("info", envs_flag, "--json").assert_ok()
    env_list = EnvList.from_json(result)
    assert env_name in env_list
    created_env = env_list.get_by_prefix(env_path)
    assert created_env is not None
    assert_created_env_json_fields(created_env, env_name, env_path)


# Shell-dependent: the active marker requires observing a shell activation.
@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
def test_conda_info_envs_marks_activated_env_in_shell(conda_shell, empty_env, envs_flag):
    """``conda info -e``/``--envs`` marks an explicitly activated env as active."""
    env_name, env_path = empty_env

    result = conda_shell.run_in_activated_env(env_name, f"conda info {envs_flag}").assert_ok()
    env_list = EnvList.from_stdout(result)

    activated_env = env_list.get_by_prefix(env_path)
    assert activated_env is not None
    assert activated_env.active
    assert sum(env.active for env in env_list) == 1, (
        f"expected exactly one active environment in plain output; "
        f"got {[env.name for env in env_list if env.active]}"
    )


@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
def test_info_envs_json_marks_activated_env(conda_shell, empty_env, envs_flag):
    """``conda info -e``/``--envs`` with ``--json`` marks the activated env."""
    env_name, env_path = empty_env

    result = conda_shell.run_in_activated_env(
        env_name, f"conda info {envs_flag} --json"
    ).assert_ok()
    env_list = EnvList.from_json(result)
    activated_env = env_list.get_by_prefix(env_path)
    assert activated_env is not None
    assert activated_env.active
    assert sum(env.active for env in env_list) == 1, (
        f"expected exactly one active environment in JSON output; "
        f"got {[env.name for env in env_list if env.active]}"
    )


@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
@pytest.mark.parametrize("output_flag", OUTPUT_MODE_FLAGS)
def test_conda_info_envs_with_size_reports_env_disk_usage(conda, empty_env, envs_flag, output_flag):
    """``conda info -e``/``--envs --size`` reports env disk usage in all output modes."""
    env_name, env_path = empty_env

    result = _run_info_with_output_flag(
        conda,
        envs_flag,
        "--size",
        output_flag=output_flag,
    )
    output = result.stdout

    assert_envs_headers_present(output, f"{envs_flag} --size")
    env_line = next(
        (
            line
            for line in output.splitlines()
            if (parts := line.split()) and is_same_path(Path(parts[-1]), env_path)
        ),
        None,
    )
    assert env_line is not None, f"did not find size row for {env_path} in output:\n{output}"
    env_fields = env_line.split()
    assert env_fields[0] == env_name
    assert is_same_path(Path(env_fields[-1]), env_path)
    assert re.search(r"\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|TB)\b", env_line)


@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
def test_info_envs_json_with_size_lists_created_env(conda, empty_env, envs_flag):
    """``conda info -e/--envs --size --json`` reports env metadata including size."""
    env_name, env_path = empty_env

    result = conda("info", envs_flag, "--size", "--json").assert_ok()
    env_list = EnvList.from_json(result)
    created_env = env_list.get_by_prefix(env_path)

    assert created_env is not None
    assert_created_env_json_fields(created_env, env_name, env_path)
    assert created_env.size is not None
    assert created_env.size >= 0


def test_info_envs_json_marks_frozen_env(conda, empty_env):
    """``conda info -e --json`` reports an environment with a frozen marker."""
    _, env_path = empty_env
    frozen_marker = env_path / "conda-meta" / "frozen"
    frozen_marker.touch()
    assert frozen_marker.is_file()

    env_list = EnvList.from_json(conda("info", "-e", "--json").assert_ok())
    frozen_env = env_list.get_by_prefix(env_path)

    assert frozen_env is not None
    assert frozen_env.frozen
    assert frozen_env.writable
