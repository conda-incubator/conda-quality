# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda env list`` (an alias of ``conda info --envs``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
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
from conda_e2e.parsers.info import CondaInfo

if TYPE_CHECKING:
    from pathlib import Path

    from conda_e2e.parsers.env import EnvRecord


def _root_prefix(conda) -> Path:
    """Return the base env prefix from an independent ``conda info --json`` call."""
    return CondaInfo.from_json(conda("info", "--json").assert_ok()).root_prefix


def _assert_frozen_env_independent_of_active(active_env: EnvRecord, frozen_env: EnvRecord) -> None:
    """Assert a frozen env's marker doesn't bleed into an unrelated active env, or vice versa."""
    assert active_env.active
    assert not active_env.frozen
    assert frozen_env.frozen
    assert not frozen_env.active


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.smoke
def test_env_list_matches_info_envs_output(conda, make_env):
    """``conda env list`` renders identically to ``conda info --envs``, its documented alias.

    Anchored to a created env's row, so two matching header-only or broken
    renderings cannot pass this equivalence check.
    """
    _, env_path = make_env()

    env_list_result = conda("env", "list").assert_ok()
    info_envs_output = conda("info", "--envs").assert_ok().stdout
    assert_envs_headers_present(env_list_result.stdout, "env list")
    require_env_by_prefix(EnvList.from_stdout(env_list_result), env_path)
    assert env_list_result.stdout == info_envs_output


@pytest.mark.smoke
def test_env_list_includes_base_with_install_path(conda):
    """``conda env list`` reports base at its install path, inactive by default.

    The inactive baseline is what the later "marks base active" test contrasts against.
    """
    root_prefix = _root_prefix(conda)

    env_list = EnvList.from_stdout(conda("env", "list").assert_ok())
    base_env = require_env_by_prefix(env_list, root_prefix)
    assert base_env.name == "base"
    # The harness invokes conda without a shell hook sourced, so no env is active.
    assert not base_env.active


@pytest.mark.smoke
def test_env_list_marks_base_active_when_base_activated(conda, conda_shell):
    """``conda env list`` marks ``base`` active once activated, and only that one."""
    root_prefix = _root_prefix(conda)

    result = conda_shell.run_in_activated_env("base", "conda env list").assert_ok()
    env_list = EnvList.from_stdout(result)
    base_env = require_env_by_prefix(env_list, root_prefix)
    assert base_env.active
    assert_single_active_env(env_list)


def test_env_list_marks_base_active_when_base_activated_json(conda, conda_shell):
    """``conda env list --json`` marks base active, not frozen, and the sole active env.

    Also asserts ``base: true``, the field JSON exposes that plain output cannot.
    """
    root_prefix = _root_prefix(conda)

    result = conda_shell.run_in_activated_env("base", "conda env list --json").assert_ok()
    env_list = EnvList.from_json(result)
    base_env = require_env_by_prefix(env_list, root_prefix)
    assert base_env.name == "base"
    assert base_env.active
    assert base_env.base
    assert not base_env.frozen
    assert_single_active_env(env_list)


@pytest.mark.smoke
def test_env_list_lists_created_env(conda, make_env):
    """``conda env list`` lists a created environment's name and prefix."""
    env_name, env_path = make_env()

    env_list = EnvList.from_stdout(conda("env", "list").assert_ok())
    created_env = require_env_by_prefix(env_list, env_path)
    assert_created_env_listed(created_env, env_name, env_path)


def test_env_list_lists_created_env_json(conda, make_env):
    """``conda env list --json`` reports a created env's identity and marker fields.

    Anchored to its on-disk ``conda-meta`` dir; ``size`` is absent without ``--size``.
    """
    env_name, env_path = make_env()
    # Anchor the report to on-disk reality: the listed env must physically
    # exist as a real conda env (one disk check per suite is enough, since
    # every test shares the same make_env() setup path).
    assert (env_path / "conda-meta").is_dir(), f"expected conda-meta dir under {env_path}"

    env_list = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    created_env = require_env_by_prefix(env_list, env_path)
    assert_created_env_json_fields(created_env, env_name, env_path)
    assert created_env.size is None, "size should only be reported with --size"


@pytest.mark.smoke
def test_env_list_marks_activated_env(conda_shell, make_env):
    """``conda env list`` marks an explicitly activated env active, and only that one."""
    env_name, env_path = make_env()

    result = conda_shell.run_in_activated_env(env_name, "conda env list").assert_ok()
    env_list = EnvList.from_stdout(result)
    activated_env = require_env_by_prefix(env_list, env_path)
    assert activated_env.active
    assert_single_active_env(env_list)


def test_env_list_marks_activated_env_json(conda_shell, make_env):
    """``conda env list --json`` marks an explicitly activated env active, and only that one."""
    env_name, env_path = make_env()

    result = conda_shell.run_in_activated_env(env_name, "conda env list --json").assert_ok()
    env_list = EnvList.from_json(result)
    activated_env = require_env_by_prefix(env_list, env_path)
    assert activated_env.active
    assert_single_active_env(env_list)


@pytest.mark.smoke
def test_env_list_marks_frozen_env_separately_from_active(conda_shell, make_env):
    """``conda env list`` marks a frozen env's marker independently of an unrelated active env."""
    active_name, active_path = make_env()
    _, frozen_path = make_env()
    freeze_env(frozen_path)

    result = conda_shell.run_in_activated_env(active_name, "conda env list").assert_ok()
    env_list = EnvList.from_stdout(result)
    active_env = require_env_by_prefix(env_list, active_path)
    frozen_env = require_env_by_prefix(env_list, frozen_path)
    _assert_frozen_env_independent_of_active(active_env, frozen_env)


def test_env_list_marks_frozen_env_separately_from_active_json(conda_shell, make_env):
    """``conda env list --json`` marks a frozen env independently of an unrelated active env."""
    active_name, active_path = make_env()
    _, frozen_path = make_env()
    freeze_env(frozen_path)

    result = conda_shell.run_in_activated_env(active_name, "conda env list --json").assert_ok()
    env_list = EnvList.from_json(result)
    active_env = require_env_by_prefix(env_list, active_path)
    frozen_env = require_env_by_prefix(env_list, frozen_path)
    _assert_frozen_env_independent_of_active(active_env, frozen_env)


@pytest.mark.smoke
def test_env_list_marks_active_and_frozen_on_same_env(conda_shell, make_env):
    """``conda env list`` marks an already-frozen env active too, showing both markers."""
    env_name, env_path = make_env()
    freeze_env(env_path)

    result = conda_shell.run_in_activated_env(env_name, "conda env list").assert_ok()
    env_list = EnvList.from_stdout(result)
    env_record = require_env_by_prefix(env_list, env_path)

    assert env_record.active
    assert env_record.frozen
    assert_single_active_env(env_list)


def test_env_list_marks_active_and_frozen_on_same_env_json(conda_shell, make_env):
    """``conda env list --json`` marks an already-frozen env active too, showing both markers."""
    env_name, env_path = make_env()
    freeze_env(env_path)

    result = conda_shell.run_in_activated_env(env_name, "conda env list --json").assert_ok()
    env_list = EnvList.from_json(result)
    env_record = require_env_by_prefix(env_list, env_path)

    assert env_record.active
    assert env_record.frozen
    assert_single_active_env(env_list)


@pytest.mark.smoke
def test_env_list_with_size_reports_size_for_every_env(conda, make_env):
    """``conda env list --size`` renders a size figure on every line, including a created env."""
    env_name, env_path = make_env()

    result = conda("env", "list", "--size").assert_ok()
    output = result.stdout
    assert_envs_headers_present(output, "env list --size")
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


def test_env_list_with_size_reports_size_for_every_env_json(conda, make_env):
    """``conda env list --size --json`` reports a non-negative size for every env.

    Also checks the created env's full JSON fields, which ``--size`` leaves intact.
    """
    env_name, env_path = make_env()

    env_list = EnvList.from_json(conda("env", "list", "--size", "--json").assert_ok())
    assert env_list, "expected at least one reported environment"
    unsized_envs = [env.name for env in env_list if env.size is None or env.size < 0]
    assert not unsized_envs, f"environments missing a valid size: {unsized_envs}"

    # Anchor to the created env so the check is not satisfied by base alone.
    created_env = require_env_by_prefix(env_list, env_path)
    assert_created_env_json_fields(created_env, env_name, env_path)


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.smoke
def test_env_list_rejects_unsupported_option(conda):
    """``conda env list`` reports unsupported options on stderr."""
    conda("env", "list", "--not-a-real-option").assert_error(
        code=2,
        contains="unrecognized arguments: --not-a-real-option",
    )
