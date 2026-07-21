# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda info``/``conda info --json`` reported output and state."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from assert_helpers import (
    assert_activation_env_vars,
    assert_created_env_json_fields,
    assert_info_self_consistent,
    assert_install_fields_unchanged,
    assert_plain_and_json_info_match,
    assert_sandboxed,
    assert_unsafe_channels_are_channel_roots,
)

from conda_e2e.parsers.env import EnvList
from conda_e2e.parsers.info import CondaInfo, PlainCondaInfo
from conda_e2e.utils import env_prefix, is_same_path, unique_env_name

# =============================================================================
# Positive test cases
# =============================================================================


def test_info_reports_base_after_shell_hook_activation(conda_shell, isolated_env_vars):
    """Sourcing a shell's conda hook auto-activates ``base``, reflected in ``conda info``.

    Every supported shell's hook does this activation itself (see each
    ``Shell.wrap_with_hook``), so this is genuinely shell-dependent behaviour,
    not just a shell-agnostic ``conda info`` check running once per shell.
    """
    result = conda_shell("conda info --json").assert_ok()
    info = CondaInfo.from_json(result)

    assert info.active_prefix_name == "base"
    assert info.active_prefix == info.root_prefix
    assert info.default_prefix == info.root_prefix
    # Baseline shell level can vary by shell/config, but must be reflected in env_vars.
    assert info.conda_shlvl >= 1

    assert_activation_env_vars(
        info,
        default_env="base",
        prefix=info.root_prefix,
        shlvl=info.conda_shlvl,
    )

    assert_sandboxed(info, isolated_env_vars)
    assert_info_self_consistent(info)


# Shell-agnostic: the installation root does not depend on activation or shell state.
def test_info_root_prefix_matches_conda_install(conda, install_root):
    """``root_prefix`` identifies the installation containing conda under test."""
    info = CondaInfo.from_json(conda("info", "--json").assert_ok())
    assert is_same_path(info.root_prefix, install_root)


def test_info_conda_version_matches_version_flag(conda):
    """``conda info``'s reported version agrees with ``conda --version``.

    Shell-agnostic (neither command touches activation state), so this runs
    once against the bare binary rather than once per shell.
    """
    info = CondaInfo.from_json(conda("info", "--json").assert_ok())

    version_result = conda("--version").assert_ok()
    expected_version = version_result.stdout.strip().removeprefix("conda ").strip()
    assert info.conda_version == expected_version
    assert_info_self_consistent(info)


def test_info_plain_matches_json_for_bare_conda(conda):
    """``conda info`` without ``--json`` reports the same values as ``--json``.

    The JSON path already proves these values correct (sandboxing, host
    invariants); this only checks the plain-text renderer agrees with them.
    Uses the bare ``conda`` binary (not ``conda_shell``): this cross-check is
    shell-agnostic, so there's nothing to gain from running it once per shell.
    """
    json_result = conda("info", "--json").assert_ok()
    info = CondaInfo.from_json(json_result)

    plain_result = conda("info").assert_ok()
    plain = PlainCondaInfo.from_stdout(plain_result)

    assert_plain_and_json_info_match(plain, info)
    assert_info_self_consistent(info)


def test_info_reports_activated_env(conda_shell, empty_env, isolated_env_vars):
    """After activating a freshly created env, ``conda info`` reflects it.

    Every value asserted (name, prefix path, shell level, prompt, env vars) is
    derived from the env this test creates or the baseline captured before
    activation, not hardcoded, so the test holds regardless of where the
    sandbox or conda install lives.
    """
    baseline_result = conda_shell("conda info --json").assert_ok()
    baseline_info = CondaInfo.from_json(baseline_result)

    env_name, env_path = empty_env

    result = conda_shell.run_in_activated_env(env_name, "conda info --json").assert_ok()
    info = CondaInfo.from_json(result)

    assert info.active_prefix_name == env_name
    assert is_same_path(info.active_prefix, env_path)
    assert is_same_path(info.default_prefix, env_path)

    # Activating one level deeper bumps the shell level by exactly one.
    assert info.conda_shlvl == baseline_info.conda_shlvl + 1

    assert_install_fields_unchanged(baseline_info, info)
    assert_sandboxed(info, isolated_env_vars)
    assert_info_self_consistent(info)

    # The new env is now discoverable among conda's known envs, alongside root_prefix.
    assert any(is_same_path(env_path, path) for path in info.envs)

    # conda mirrors the active env into these vars for subprocesses/tools to read.
    assert_activation_env_vars(
        info,
        default_env=env_name,
        prefix=env_path,
        shlvl=info.conda_shlvl,
        prompt_modifier=f"({env_name}) ",
    )


def test_info_plain_matches_json_for_activated_env(conda_shell, empty_env):
    """``conda info`` without ``--json`` agrees with ``--json`` for an activated env.

    Confirms the plain renderer's ``active environment``/``active env
    location`` lines track activation, not just the ``base`` case covered by
    ``test_info_plain_matches_json_for_bare_conda``.
    """
    env_name, _ = empty_env

    json_result = conda_shell.run_in_activated_env(env_name, "conda info --json").assert_ok()
    info = CondaInfo.from_json(json_result)

    plain_result = conda_shell.run_in_activated_env(env_name, "conda info").assert_ok()
    plain = PlainCondaInfo.from_stdout(plain_result)

    assert_plain_and_json_info_match(plain, info)
    assert_info_self_consistent(info)


def test_info_unsafe_channels_json_exposes_configured_token(conda, token_channel):
    """``conda info --unsafe-channels --json`` exposes configured channel tokens."""
    token = "e2e-token"

    masked_channels = conda("info", "--json").assert_ok().json()["channels"]
    unsafe_payload = conda("info", "--unsafe-channels", "--json").assert_ok().json()

    assert masked_channels
    assert all(token not in channel for channel in masked_channels)
    assert any("/t/<TOKEN>/conda-forge/" in channel for channel in masked_channels)
    assert set(unsafe_payload) == {"channels"}
    unsafe_channels = unsafe_payload["channels"]
    assert token_channel in unsafe_channels
    assert_unsafe_channels_are_channel_roots(unsafe_channels)


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
    assert sum(env.active for env in env_list) == 1


def test_info_active_prefix_moves_between_envs(conda_shell, conda, envs_dir, isolated_env_vars):
    """Activating a second env updates the active prefix and bumps the shell level again.

    Unlike ``--stack``, a plain ``conda activate`` replaces the current env
    rather than layering on top of it, so the first env's prefix must drop out
    of ``PATH`` once the second is active.
    """
    baseline_result = conda_shell("conda info --json").assert_ok()
    baseline_info = CondaInfo.from_json(baseline_result)

    first_name = unique_env_name()
    second_name = unique_env_name()
    first_path = env_prefix(envs_dir, first_name)
    second_path = env_prefix(envs_dir, second_name)

    conda("create", "-n", first_name).assert_ok()
    conda("create", "-n", second_name).assert_ok()

    result = conda_shell.run_in_activated_env(
        first_name,
        f"conda activate {second_name}",
        "conda info --json",
    ).assert_ok()
    info = CondaInfo.from_json(result)

    assert info.active_prefix_name == second_name
    assert is_same_path(info.active_prefix, second_path)
    assert is_same_path(info.default_prefix, second_path)

    # Two activations deep from the baseline shell level.
    assert info.conda_shlvl == baseline_info.conda_shlvl + 2
    assert_install_fields_unchanged(baseline_info, info)

    assert_activation_env_vars(
        info,
        default_env=second_name,
        prefix=second_path,
        shlvl=info.conda_shlvl,
        prompt_modifier=f"({second_name}) ",
    )

    # A non-stacked activate replaces the first env on PATH rather than layering it.
    path_entries = tuple(
        Path(path_entry).resolve()
        for path_entry in info.env_vars.get("PATH", "").split(os.pathsep)
        if path_entry
    )
    resolved_first_path = first_path.resolve()
    resolved_second_path = second_path.resolve()
    assert any(path_entry.is_relative_to(resolved_second_path) for path_entry in path_entries)
    assert not any(path_entry.is_relative_to(resolved_first_path) for path_entry in path_entries)

    assert_sandboxed(info, isolated_env_vars)
    assert_info_self_consistent(info)


# =============================================================================
# Edge cases
# =============================================================================


def test_info_reports_base_after_deactivate(conda_shell, empty_env):
    """Deactivating a created env drops the shell level back to the pre-activation baseline.

    Baseline is captured from this same shell before any activation, so the
    assertion holds regardless of what shell level a hooked shell starts at.
    """
    baseline_result = conda_shell("conda info --json").assert_ok()
    baseline_info = CondaInfo.from_json(baseline_result)

    env_name, env_path = empty_env

    result = conda_shell.run_in_activated_env(
        env_name,
        "conda deactivate",
        "conda info --json",
    ).assert_ok()
    info = CondaInfo.from_json(result)

    assert info.active_prefix_name == baseline_info.active_prefix_name
    assert info.active_prefix == baseline_info.active_prefix
    assert info.conda_shlvl == baseline_info.conda_shlvl
    assert_install_fields_unchanged(baseline_info, info)

    assert_activation_env_vars(
        info,
        default_env=baseline_info.env_vars.get("CONDA_DEFAULT_ENV"),
        prefix=baseline_info.env_vars.get("CONDA_PREFIX"),
        shlvl=info.conda_shlvl,
    )
    assert_info_self_consistent(info)

    # The deactivated env's prefix is gone from PATH once more.
    assert str(env_path) not in info.env_vars.get("PATH", "")
