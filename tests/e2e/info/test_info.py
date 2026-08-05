# SPDX-License-Identifier: BSD-3-Clause
"""General E2E tests for ``conda info`` output and state."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from info_asserts import (
    assert_activation_env_vars,
    assert_info_json_common_state,
    assert_info_self_consistent,
    assert_install_fields_unchanged,
    assert_plain_and_json_info_match,
    assert_plain_and_json_system_info_match,
    assert_sandboxed,
)

from conda_e2e.parsers.info import (
    CONDA_ENVIRONMENTS_HEADER,
    SYS_VERSION_PREFIX,
    CondaInfo,
    PlainCondaInfo,
    PlainCondaSystemInfo,
)
from conda_e2e.utils import IS_WINDOWS, env_prefix, is_same_path, unique_env_name

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.parametrize("help_flag", ["--help", "-h"])
def test_conda_info_help(conda, help_flag):
    """``conda info --help``/``-h`` documents usage and all available options."""
    result = conda("info", help_flag).assert_ok()
    output = result.stdout
    normalized_output = " ".join(output.split())

    expected_text = (
        "usage: conda info",
        "Display information about current conda install.",
    )

    expected_headers = (
        "options:",
        "Output, Prompt, and Flow Control Options:",
    )

    expected_flags = (
        "-h, --help",
        "-a, --all",
        "--base",
        "-e, --envs",
        "--size",
        "-s, --system",
        "--unsafe-channels",
        "--json",
        "-v, --verbose",
        "-q, --quiet",
    )

    expected = expected_text + expected_headers + expected_flags
    missing = [e for e in expected if e not in output]
    assert not missing, f"help output missing {missing}. Command output:\n{output}"
    # ``--console`` renders its argument either as a generic placeholder or as the explicit set
    # of accepted backends, depending on the conda version, so accept both spellings.
    assert re.search(r"--console (CONSOLE|\{[\w,]+\})", normalized_output), (
        f"help output missing --console option. Command output:\n{output}"
    )
    # Verify the public level mapping without coupling the test to unstable log-record text.
    assert (
        "Can be used multiple times. Once for detailed output, twice for INFO logging, "
        "thrice for DEBUG logging, four times for TRACE logging." in normalized_output
    )


# Verbosity flags are global; this representative command verifies each form is accepted and
# preserves stable stdout without asserting on implementation-specific log records.
@pytest.mark.parametrize(
    "output_flag",
    [None, "-q", "--quiet", "-v", "--verbose", "-vv", "-vvv", "-vvvv"],
)
def test_conda_info_base_reports_root_prefix(conda, install_root, output_flag):
    """``conda info --base`` accepts quiet and all documented verbosity levels."""
    args = ["info", "--base"]
    if output_flag is not None:
        args.append(output_flag)
    result = conda(*args).assert_ok()

    output_lines = [
        stripped_line for line in result.stdout.splitlines() if (stripped_line := line.strip())
    ]
    assert len(output_lines) == 1
    assert is_same_path(Path(output_lines[0]), install_root)


def test_conda_info_unsafe_channels(conda, token_channel):
    """``conda info --unsafe-channels`` exposes configured tokens in plain output."""
    masked_result = conda("info").assert_ok()
    unsafe_result = conda("info", "--unsafe-channels").assert_ok()

    assert token_channel.token not in masked_result.stdout
    assert "<TOKEN>" in masked_result.stdout
    assert f"/t/{token_channel.token}/" in unsafe_result.stdout


def test_conda_info_unsafe_channels_json(conda, token_channel):
    """``conda info --unsafe-channels --json`` exposes configured channel tokens."""
    safe_payload = conda("info", "--json").assert_ok().json()
    unsafe_payload = conda("info", "--unsafe-channels", "--json").assert_ok().json()

    masked_channels = safe_payload["channels"]
    assert masked_channels
    assert all(token_channel.token not in channel for channel in masked_channels)
    assert any("/t/<TOKEN>/" in channel for channel in masked_channels)
    assert set(unsafe_payload) == {"channels"}
    unsafe_channels = unsafe_payload["channels"]
    assert any(f"/t/{token_channel.token}/" in channel for channel in unsafe_channels)


def test_conda_info_all_combines_info_envs_and_system(conda, empty_env, info_env_vars):
    """Plain ``conda info --all`` combines summary, environment, and system reports."""
    env_name, env_path = empty_env
    result = conda("info", "--all", extra_env=info_env_vars).assert_ok()

    # Dedicated tests validate each report's fields and values; this test checks that ``--all``
    # combines the summary, environment, and system reports in that order.
    _, separator, remaining_output = result.stdout.partition(CONDA_ENVIRONMENTS_HEADER)
    assert separator, f"missing environments section in output:\n{result.stdout}"
    environments_output, separator, _ = remaining_output.partition(SYS_VERSION_PREFIX)
    assert separator, f"missing system section in output:\n{result.stdout}"

    PlainCondaInfo.from_stdout(result)
    env_line = next(
        (
            line
            for line in environments_output.splitlines()
            if (parts := line.split()) and is_same_path(Path(parts[-1]), env_path)
        ),
        None,
    )
    assert env_line is not None, f"did not find environment {env_path} in output:\n{result.stdout}"
    assert env_line.split()[0] == env_name

    system = PlainCondaSystemInfo.from_stdout(result)
    assert system.env_vars["CIO_TEST"] == info_env_vars["CIO_TEST"]


def test_conda_info_all_json(
    conda,
    install_root,
    isolated_env_vars,
    info_env_vars,
    conda_version,
    expected_info_env_vars,
):
    """``conda info --all --json`` reports the shared bare-process state correctly."""
    result = conda("info", "--all", "--json", extra_env=info_env_vars).assert_ok()
    info = CondaInfo.from_json(result)

    assert_info_json_common_state(
        info,
        install_root=install_root,
        isolated_env_vars=isolated_env_vars,
        expected_conda_version=conda_version,
        expected_env_vars=expected_info_env_vars,
    )


@pytest.mark.parametrize(
    ("short_flag", "long_flag"),
    [("-a", "--all"), ("-s", "--system")],
)
def test_conda_info_short_and_long_flags_equivalent(conda, info_env_vars, short_flag, long_flag):
    """Short and long ``conda info`` report flags render equivalent output."""
    short_result = conda("info", short_flag, extra_env=info_env_vars).assert_ok()
    long_result = conda("info", long_flag, extra_env=info_env_vars).assert_ok()

    assert short_result.stdout == long_result.stdout


def test_conda_info_system(conda, info_env_vars):
    """Plain ``conda info --system`` renders the shared JSON values faithfully."""
    json_result = conda("info", "--system", "--json", extra_env=info_env_vars).assert_ok()
    info = CondaInfo.from_json(json_result)
    plain_result = conda("info", "--system", extra_env=info_env_vars).assert_ok()
    plain = PlainCondaSystemInfo.from_stdout(plain_result)

    assert_plain_and_json_system_info_match(plain, info)
    # Plugin mappings appear only in the plain report, not in the JSON payload.
    assert plain.plugins
    assert all(provider for provider in plain.plugins.values())


@pytest.mark.skipif(IS_WINDOWS, reason="POSIX user site dirs render under ~/.local/lib/pythonX.Y")
def test_conda_info_system_site_dirs(conda, isolated_env_vars, info_env_vars):
    """``conda info --system`` parses populated POSIX user site dirs from the header section."""
    user_site_dirs = (Path(".local/lib/python3.12"), Path(".local/lib/python3.13"))
    for relative_site_dir in user_site_dirs:
        (Path(isolated_env_vars["HOME"]) / relative_site_dir).mkdir(parents=True, exist_ok=True)

    json_result = conda("info", "--system", "--json", extra_env=info_env_vars).assert_ok()
    info = CondaInfo.from_json(json_result)
    plain_result = conda("info", "--system", extra_env=info_env_vars).assert_ok()
    plain = PlainCondaSystemInfo.from_stdout(plain_result)

    expected_site_dirs = {
        Path(f"~/{relative_site_dir.as_posix()}") for relative_site_dir in user_site_dirs
    }
    # conda doesn't guarantee a stable order for multiple user site dirs.
    assert set(plain.site_dirs) == expected_site_dirs
    assert set(info.site_dirs) == expected_site_dirs
    assert_plain_and_json_system_info_match(plain, info)


def test_conda_info_system_json(
    conda,
    install_root,
    isolated_env_vars,
    info_env_vars,
    conda_version,
    expected_info_env_vars,
):
    """``conda info --system --json`` reports the conda installation and selected variables."""
    default_result = conda("info", extra_env=info_env_vars).assert_ok()
    json_result = conda("info", "--system", "--json", extra_env=info_env_vars).assert_ok()
    info = CondaInfo.from_json(json_result)

    assert not any(value in default_result.stdout for value in info_env_vars.values())
    assert_info_json_common_state(
        info,
        install_root=install_root,
        isolated_env_vars=isolated_env_vars,
        expected_conda_version=conda_version,
        expected_env_vars=expected_info_env_vars,
    )


def test_conda_info_reports_base_after_shell_hook_activation(conda_shell, isolated_env_vars):
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
def test_conda_info_root_prefix_matches_conda_install(conda, install_root):
    """``root_prefix`` identifies the installation containing conda under test."""
    info = CondaInfo.from_json(conda("info", "--json").assert_ok())
    assert is_same_path(info.root_prefix, install_root)


def test_conda_info_conda_version_matches_version_flag(conda, conda_version):
    """``conda info``'s reported version agrees with ``conda --version``.

    Shell-agnostic (neither command touches activation state), so this runs
    once against the bare binary rather than once per shell.
    """
    info = CondaInfo.from_json(conda("info", "--json").assert_ok())

    assert info.conda_version == conda_version
    assert_info_self_consistent(info)


def test_conda_info_plain_matches_json_for_bare_conda(conda):
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


def test_conda_info_reports_activated_env(conda_shell, empty_env, isolated_env_vars):
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


def test_conda_info_plain_matches_json_for_activated_env(conda_shell, empty_env):
    """``conda info`` without ``--json`` agrees with ``--json`` for an activated env.

    Confirms the plain renderer's ``active environment``/``active env
    location`` lines track activation, not just the ``base`` case covered by
    ``test_conda_info_plain_matches_json_for_bare_conda``.
    """
    env_name, _ = empty_env

    json_result = conda_shell.run_in_activated_env(env_name, "conda info --json").assert_ok()
    info = CondaInfo.from_json(json_result)

    plain_result = conda_shell.run_in_activated_env(env_name, "conda info").assert_ok()
    plain = PlainCondaInfo.from_stdout(plain_result)

    assert_plain_and_json_info_match(plain, info)
    assert_info_self_consistent(info)


def test_conda_info_active_prefix_moves_between_envs(
    conda_shell, conda, envs_dir, isolated_env_vars
):
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


def test_conda_info_reports_base_after_deactivate(conda_shell, empty_env):
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


# =============================================================================
# Negative test cases
# =============================================================================


def test_conda_info_rejects_unknown_option(conda):
    """``conda info`` rejects an unsupported option on stderr."""
    conda("info", "--invalid-flag").assert_error(
        code=2,
        contains="unrecognized arguments: --invalid-flag",
        stream="stderr",
    )
