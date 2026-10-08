# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda info`` environment-listing behavior (``-e``/``--envs``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from info_asserts import (
    SIZE_FIGURE_RE,
    assert_created_env_json_fields,
    assert_created_env_listed,
    assert_envs_headers_present,
    assert_single_active_env,
    require_env_by_prefix,
)
from shared.helpers import freeze_env

from conda_e2e.parsers.env import EnvList

if TYPE_CHECKING:
    from conda_e2e.parsers.env import EnvRecord


def _assert_frozen_env_independent_of_active(active_env: EnvRecord, frozen_env: EnvRecord) -> None:
    """Assert a frozen env's marker doesn't bleed into an unrelated active env, or vice versa."""
    assert active_env.active
    assert not active_env.frozen
    assert frozen_env.frozen
    assert not frozen_env.active


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(347, 226)
@pytest.mark.smoke
def test_conda_info_envs_lists_created_env(conda, make_env):
    """``conda info --envs`` lists a created environment in plain output."""
    env_name, env_path = make_env()

    result = conda("info", "--envs").assert_ok()
    assert_envs_headers_present(result.stdout, "--envs")
    created_env = require_env_by_prefix(EnvList.from_stdout(result), env_path)
    assert_created_env_listed(created_env, env_name, env_path)


@pytest.mark.covers(656, 227)
@pytest.mark.smoke
def test_conda_info_envs_lists_created_env_json(conda, make_env):
    """``conda info --envs --json`` lists a newly created environment."""
    env_name, env_path = make_env()

    result = conda("info", "--envs", "--json").assert_ok()
    env_list = EnvList.from_json(result)
    created_env = require_env_by_prefix(env_list, env_path)
    assert_created_env_json_fields(created_env, env_name, env_path)
    assert created_env.size is None, "size should only be reported with --size"


@pytest.mark.covers(347, 226)
@pytest.mark.smoke
def test_conda_info_envs_includes_base_with_install_path(conda, install_root):
    """``conda info --envs`` reports base at its install path, inactive by default."""
    env_list = EnvList.from_stdout(conda("info", "--envs").assert_ok())
    base_env = require_env_by_prefix(env_list, install_root)
    assert base_env.name == "base"
    # The harness invokes conda without a shell hook sourced, so no env is active.
    assert not base_env.active


@pytest.mark.covers(347, 226)
@pytest.mark.smoke
def test_conda_info_envs_marks_base_active_when_base_activated(conda_shell, install_root):
    """``conda info --envs`` marks ``base`` active once activated, and only that one."""
    result = conda_shell.run_in_activated_env("base", "conda info --envs").assert_ok()
    env_list = EnvList.from_stdout(result)
    base_env = require_env_by_prefix(env_list, install_root)
    assert base_env.active
    assert_single_active_env(env_list)


@pytest.mark.covers(656, 227)
def test_conda_info_envs_marks_base_active_when_base_activated_json(conda_shell, install_root):
    """``conda info --envs --json`` marks ``base`` correctly and active as the sole active env."""
    result = conda_shell.run_in_activated_env("base", "conda info --envs --json").assert_ok()
    env_list = EnvList.from_json(result)
    base_env = require_env_by_prefix(env_list, install_root)
    assert base_env.name == "base"
    assert base_env.active
    assert base_env.base
    assert_single_active_env(env_list)


@pytest.mark.covers(346, 347, 226)
def test_conda_info_envs_short_and_long_flags_equivalent(conda):
    """``conda info -e`` and ``--envs`` render the same environment list."""
    short_result = conda("info", "-e").assert_ok()
    long_result = conda("info", "--envs").assert_ok()

    assert short_result.stdout == long_result.stdout


# Shell-dependent: the active marker requires observing a shell activation.
@pytest.mark.covers(347, 226)
def test_conda_info_envs_marks_activated_env(conda_shell, make_env):
    """``conda info --envs`` marks an explicitly activated environment as active."""
    env_name, env_path = make_env()

    result = conda_shell.run_in_activated_env(env_name, "conda info --envs").assert_ok()
    env_list = EnvList.from_stdout(result)

    activated_env = require_env_by_prefix(env_list, env_path)
    assert activated_env.active
    assert_single_active_env(env_list)


@pytest.mark.covers(656, 227)
def test_conda_info_envs_marks_activated_env_json(conda_shell, make_env):
    """``conda info --envs --json`` marks the activated environment."""
    env_name, env_path = make_env()

    result = conda_shell.run_in_activated_env(env_name, "conda info --envs --json").assert_ok()
    env_list = EnvList.from_json(result)
    activated_env = require_env_by_prefix(env_list, env_path)
    assert activated_env.active
    assert_single_active_env(env_list)


@pytest.mark.covers(656, 227)
def test_conda_info_envs_marks_frozen_env_json(conda, make_env):
    """``conda info --envs --json`` reports an environment with a frozen marker."""
    _, env_path = make_env()
    freeze_env(env_path)

    env_list = EnvList.from_json(conda("info", "--envs", "--json").assert_ok())
    frozen_env = require_env_by_prefix(env_list, env_path)
    assert frozen_env.frozen
    assert frozen_env.writable


@pytest.mark.covers(347, 226)
def test_conda_info_envs_marks_frozen_env_separately_from_active(conda_shell, make_env):
    """``conda info --envs`` marks a frozen env independently of an unrelated active env."""
    active_name, active_path = make_env()
    _, frozen_path = make_env()
    freeze_env(frozen_path)

    result = conda_shell.run_in_activated_env(active_name, "conda info --envs").assert_ok()
    env_list = EnvList.from_stdout(result)
    active_env = require_env_by_prefix(env_list, active_path)
    frozen_env = require_env_by_prefix(env_list, frozen_path)
    _assert_frozen_env_independent_of_active(active_env, frozen_env)


@pytest.mark.covers(656, 227)
def test_conda_info_envs_marks_frozen_env_separately_from_active_json(conda_shell, make_env):
    """``conda info --envs --json`` marks a frozen env independently of an unrelated active env."""
    active_name, active_path = make_env()
    _, frozen_path = make_env()
    freeze_env(frozen_path)

    result = conda_shell.run_in_activated_env(active_name, "conda info --envs --json").assert_ok()
    env_list = EnvList.from_json(result)
    active_env = require_env_by_prefix(env_list, active_path)
    frozen_env = require_env_by_prefix(env_list, frozen_path)
    _assert_frozen_env_independent_of_active(active_env, frozen_env)


@pytest.mark.smoke
@pytest.mark.covers(347, 226)
def test_conda_info_envs_marks_active_and_frozen_on_same_env(conda_shell, make_env):
    """``conda info --envs`` marks an already-frozen env active too, showing both markers."""
    env_name, env_path = make_env()
    freeze_env(env_path)

    result = conda_shell.run_in_activated_env(env_name, "conda info --envs").assert_ok()
    env_list = EnvList.from_stdout(result)
    env_record = require_env_by_prefix(env_list, env_path)

    assert env_record.active
    assert env_record.frozen
    assert_single_active_env(env_list)


@pytest.mark.covers(656, 227)
def test_conda_info_envs_marks_active_and_frozen_on_same_env_json(conda_shell, make_env):
    """``conda info --envs --json`` marks an already-frozen env active too, showing both markers."""
    env_name, env_path = make_env()
    freeze_env(env_path)

    result = conda_shell.run_in_activated_env(env_name, "conda info --envs --json").assert_ok()
    env_list = EnvList.from_json(result)
    env_record = require_env_by_prefix(env_list, env_path)

    assert env_record.active
    assert env_record.frozen
    assert_single_active_env(env_list)


@pytest.mark.covers(353, 271)
def test_conda_info_envs_with_size(conda, make_env):
    """``conda info --envs --size`` renders a size figure on every line, including a created env."""
    env_name, env_path = make_env()

    result = conda("info", "--envs", "--size").assert_ok()
    output = result.stdout
    assert_envs_headers_present(output, "--envs --size")
    data_lines = [
        line
        for line in output.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]
    assert data_lines, f"expected at least one environment data line in output:\n{output}"
    unsized_lines = [line for line in data_lines if not SIZE_FIGURE_RE.search(line)]
    assert not unsized_lines, (
        f"lines missing a size figure: {unsized_lines}\nfull output:\n{output}"
    )

    # Anchor to the created env so the check is not satisfied by base alone.
    created_env = require_env_by_prefix(EnvList.from_stdout(result), env_path)
    assert created_env.name == env_name


@pytest.mark.covers(354, 657)
def test_conda_info_envs_with_size_json(conda, make_env):
    """``conda info --envs --size --json`` reports a non-negative size for every env.

    Also checks the created env's full JSON fields, which ``--size`` leaves intact.
    """
    env_name, env_path = make_env()

    env_list = EnvList.from_json(conda("info", "--envs", "--size", "--json").assert_ok())
    assert env_list, "expected at least one reported environment"
    unsized_envs = [env.name for env in env_list if env.size is None or env.size < 0]
    assert not unsized_envs, f"environments missing a valid size: {unsized_envs}"

    # Anchor to the created env so the check is not satisfied by base alone.
    created_env = require_env_by_prefix(env_list, env_path)
    assert_created_env_json_fields(created_env, env_name, env_path)
