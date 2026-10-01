# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda info`` environment-listing behavior (``-e``/``--envs``)."""

from __future__ import annotations

from pathlib import Path

from shared.env_list_asserts import (
    SIZE_FIGURE_RE,
    assert_created_env_json_fields,
    assert_created_env_listed,
    assert_envs_headers_present,
    assert_single_active_env,
    require_env_by_prefix,
)
from shared.env_state import freeze_env

from conda_e2e.parsers.env import EnvList
from conda_e2e.utils import is_same_path

# =============================================================================
# Positive test cases
# =============================================================================


def test_conda_info_envs_lists_created_env(conda, make_env):
    """``conda info --envs`` lists a created environment in plain output."""
    env_name, env_path = make_env()

    result = conda("info", "--envs").assert_ok()
    assert_envs_headers_present(result.stdout, "--envs")
    created_env = require_env_by_prefix(EnvList.from_stdout(result), env_path)
    assert_created_env_listed(created_env, env_name, env_path)


def test_conda_info_envs_lists_created_env_json(conda, make_env):
    """``conda info --envs --json`` lists a newly created environment.

    Anchored to its on-disk ``conda-meta`` dir; ``size`` is absent without ``--size``.
    """
    env_name, env_path = make_env()
    assert (env_path / "conda-meta").is_dir(), f"expected conda-meta dir under {env_path}"

    result = conda("info", "--envs", "--json").assert_ok()
    env_list = EnvList.from_json(result)
    created_env = require_env_by_prefix(env_list, env_path)
    assert_created_env_json_fields(created_env, env_name, env_path)
    assert created_env.size is None, "size should only be reported with --size"


def test_conda_info_envs_short_and_long_flags_equivalent(conda):
    """``conda info -e`` and ``--envs`` render the same environment list."""
    short_result = conda("info", "-e").assert_ok()
    long_result = conda("info", "--envs").assert_ok()

    assert short_result.stdout == long_result.stdout


# Shell-dependent: the active marker requires observing a shell activation.
def test_conda_info_envs_marks_activated_env(conda_shell, make_env):
    """``conda info --envs`` marks an explicitly activated environment as active."""
    env_name, env_path = make_env()

    result = conda_shell.run_in_activated_env(env_name, "conda info --envs").assert_ok()
    env_list = EnvList.from_stdout(result)

    activated_env = require_env_by_prefix(env_list, env_path)
    assert activated_env.active
    assert_single_active_env(env_list)


def test_conda_info_envs_marks_activated_env_json(conda_shell, make_env):
    """``conda info --envs --json`` marks the activated environment."""
    env_name, env_path = make_env()

    result = conda_shell.run_in_activated_env(env_name, "conda info --envs --json").assert_ok()
    env_list = EnvList.from_json(result)
    activated_env = require_env_by_prefix(env_list, env_path)
    assert activated_env.active
    assert_single_active_env(env_list)


def test_conda_info_envs_with_size(conda, make_env):
    """``conda info --envs --size`` reports environment disk usage."""
    env_name, env_path = make_env()

    result = conda("info", "--envs", "--size").assert_ok()
    output = result.stdout

    assert_envs_headers_present(output, "--envs --size")
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
    assert SIZE_FIGURE_RE.search(env_line)


def test_conda_info_envs_with_size_json(conda, make_env):
    """``conda info --envs --size --json`` reports environment metadata including size."""
    env_name, env_path = make_env()

    result = conda("info", "--envs", "--size", "--json").assert_ok()
    env_list = EnvList.from_json(result)
    created_env = require_env_by_prefix(env_list, env_path)
    assert_created_env_json_fields(created_env, env_name, env_path)
    assert created_env.size is not None
    assert created_env.size >= 0


def test_conda_info_envs_marks_frozen_env_json(conda, make_env):
    """``conda info --envs --json`` reports an environment with a frozen marker."""
    _, env_path = make_env()
    freeze_env(env_path)

    env_list = EnvList.from_json(conda("info", "--envs", "--json").assert_ok())
    frozen_env = require_env_by_prefix(env_list, env_path)
    assert frozen_env.frozen
    assert frozen_env.writable
