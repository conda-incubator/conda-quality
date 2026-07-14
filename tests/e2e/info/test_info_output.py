# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda info``/``conda info --json`` reported output and state."""

from __future__ import annotations

from assert_helpers import (
    assert_activation_env_vars,
    assert_host_invariants,
    assert_plain_and_json_info_match,
    assert_sandboxed,
)

from conda_e2e.parsers.info import CondaInfo, PlainCondaInfo
from conda_e2e.utils import env_prefix, unique_env_name

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
    assert info.env_vars.get("CONDA_SHLVL") == str(info.conda_shlvl)

    assert_activation_env_vars(
        info,
        default_env="base",
        prefix=info.root_prefix,
        shlvl=info.conda_shlvl,
    )

    assert_sandboxed(info, isolated_env_vars)
    assert_host_invariants(info, info.root_prefix, info.conda_version)


def test_info_conda_version_matches_version_flag(conda):
    """``conda info``'s reported version agrees with ``conda --version``.

    Shell-agnostic (neither command touches activation state), so this runs
    once against the bare binary rather than once per shell.
    """
    info = CondaInfo.from_json(conda("info", "--json").assert_ok())

    version_result = conda("--version").assert_ok()
    expected_version = version_result.stdout.strip().removeprefix("conda ").strip()
    assert info.conda_version == expected_version


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
    plain = PlainCondaInfo.from_stdout(plain_result.stdout)

    assert_plain_and_json_info_match(plain, info)


def test_info_reports_activated_env(conda_shell, conda, envs_dir, isolated_env_vars):
    """After activating a freshly created env, ``conda info`` reflects it.

    Every value asserted (name, prefix path, shell level, prompt, env vars) is
    derived from the env this test creates or the baseline captured before
    activation, not hardcoded, so the test holds regardless of where the
    sandbox or conda install lives.
    """
    baseline_result = conda_shell("conda info --json").assert_ok()
    baseline_info = CondaInfo.from_json(baseline_result)

    env_name = unique_env_name()
    env_path = env_prefix(envs_dir, env_name)

    conda("create", "-n", env_name).assert_ok()

    result = conda_shell.run_in_activated_env(env_name, "conda info --json").assert_ok()
    info = CondaInfo.from_json(result)

    assert info.active_prefix_name == env_name
    assert info.active_prefix == env_path
    assert info.default_prefix == env_path

    # Activating one level deeper bumps the shell level by exactly one.
    assert info.conda_shlvl == baseline_info.conda_shlvl + 1

    # root_prefix, sandbox dirs, config, and host metadata are unaffected by activation.
    assert info.root_prefix == baseline_info.root_prefix
    assert info.pkgs_dirs == baseline_info.pkgs_dirs
    assert info.envs_dirs == baseline_info.envs_dirs
    assert info.config_files == baseline_info.config_files
    assert info.rc_path == baseline_info.rc_path
    assert info.channels == baseline_info.channels
    assert info.virtual_pkgs == baseline_info.virtual_pkgs
    assert info.solver_name == baseline_info.solver_name
    assert info.av_data_dir == baseline_info.av_data_dir
    assert info.uid == baseline_info.uid
    assert info.gid == baseline_info.gid
    assert_sandboxed(info, isolated_env_vars)
    assert_host_invariants(info, info.root_prefix, info.conda_version)

    # The new env is now discoverable among conda's known envs, alongside root_prefix.
    assert env_path in info.envs

    # conda mirrors the active env into these vars for subprocesses/tools to read.
    assert_activation_env_vars(
        info,
        default_env=env_name,
        prefix=env_path,
        shlvl=info.conda_shlvl,
        prompt_modifier=f"({env_name}) ",
    )


def test_info_plain_matches_json_for_activated_env(conda_shell, conda):
    """``conda info`` without ``--json`` agrees with ``--json`` for an activated env.

    Confirms the plain renderer's ``active environment``/``active env
    location`` lines track activation, not just the ``base`` case covered by
    ``test_info_plain_matches_json_for_bare_conda``.
    """
    env_name = unique_env_name()
    conda("create", "-n", env_name).assert_ok()

    json_result = conda_shell.run_in_activated_env(env_name, "conda info --json").assert_ok()
    info = CondaInfo.from_json(json_result)

    plain_result = conda_shell.run_in_activated_env(env_name, "conda info").assert_ok()
    plain = PlainCondaInfo.from_stdout(plain_result.stdout)

    assert_plain_and_json_info_match(plain, info)


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
    assert info.active_prefix == second_path
    assert info.default_prefix == second_path

    # Two activations deep from the baseline shell level.
    assert info.conda_shlvl == baseline_info.conda_shlvl + 2

    assert_activation_env_vars(
        info,
        default_env=second_name,
        prefix=second_path,
        shlvl=info.conda_shlvl,
        prompt_modifier=f"({second_name}) ",
    )

    # A non-stacked activate replaces the first env on PATH rather than layering it.
    path_value = info.env_vars.get("PATH", "")
    assert str(second_path) in path_value
    assert str(first_path) not in path_value

    assert_sandboxed(info, isolated_env_vars)
    assert_host_invariants(info, baseline_info.root_prefix, baseline_info.conda_version)


# =============================================================================
# Edge cases
# =============================================================================


def test_info_reports_base_after_deactivate(conda_shell, conda, envs_dir):
    """Deactivating a created env drops the shell level back to the pre-activation baseline.

    Baseline is captured from this same shell before any activation, so the
    assertion holds regardless of what shell level a hooked shell starts at.
    """
    baseline_result = conda_shell("conda info --json").assert_ok()
    baseline_info = CondaInfo.from_json(baseline_result)

    env_name = unique_env_name()
    conda("create", "-n", env_name).assert_ok()

    result = conda_shell.run_in_activated_env(
        env_name,
        "conda deactivate",
        "conda info --json",
    ).assert_ok()
    info = CondaInfo.from_json(result)

    assert info.active_prefix_name == baseline_info.active_prefix_name
    assert info.active_prefix == baseline_info.active_prefix
    assert info.conda_shlvl == baseline_info.conda_shlvl

    assert_activation_env_vars(
        info,
        default_env=baseline_info.env_vars.get("CONDA_DEFAULT_ENV"),
        prefix=baseline_info.env_vars.get("CONDA_PREFIX"),
        shlvl=info.conda_shlvl,
    )

    # The deactivated env's prefix is gone from PATH once more.
    env_path = env_prefix(envs_dir, env_name)
    assert str(env_path) not in info.env_vars.get("PATH", "")
