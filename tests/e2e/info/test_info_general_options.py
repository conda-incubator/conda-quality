# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda info`` general options and documented usage."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from assert_helpers import (
    assert_created_env_listed,
    assert_envs_headers_present,
    assert_unsafe_channels_are_root_urls,
)

from conda_e2e.parsers.env import PlainEnvList
from conda_e2e.utils import is_same_path

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


OUTPUT_MODE_FLAGS = (None, "-q", "--quiet", "-v", "--verbose")


def _run_info_with_output_flag(conda, *info_args: str, output_flag: str | None) -> CommandResult:
    """Run ``conda info`` with optional quiet/verbose flag and assert success."""
    args = ["info", *info_args]
    if output_flag is not None:
        args.append(output_flag)
    return conda(*args).assert_ok()


@pytest.mark.parametrize("help_flag", ["--help", "-h"])
def test_conda_info_help(conda, help_flag):
    """``conda info --help``/``-h`` documents usage and all available options."""
    result = conda("info", help_flag).assert_ok()
    output = result.stdout

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
        "-s, --system",
        "--unsafe-channels",
        "--json",
        "-v, --verbose",
        "-q, --quiet",
    )

    expected = expected_text + expected_headers + expected_flags
    missing = [e for e in expected if e not in output]
    assert not missing, f"help output missing {missing}. Command output:\n{output}"


@pytest.mark.parametrize("output_flag", OUTPUT_MODE_FLAGS)
def test_conda_info_base_reports_root_prefix(conda, conda_exe, output_flag):
    """``conda info --base`` reports the root prefix in plain, quiet, and verbose modes."""
    result = _run_info_with_output_flag(conda, "--base", output_flag=output_flag)
    install_root = Path(conda_exe).resolve().parent.parent

    output_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(output_lines) == 1
    assert is_same_path(Path(output_lines[0]), install_root)


@pytest.mark.parametrize("output_flag", OUTPUT_MODE_FLAGS)
def test_conda_info_unsafe_channels_plain_output(conda, output_flag):
    """``conda info --unsafe-channels`` keeps root URLs in plain, quiet, and verbose modes."""
    result = _run_info_with_output_flag(conda, "--unsafe-channels", output_flag=output_flag)
    channels = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert_unsafe_channels_are_root_urls(channels)


@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
@pytest.mark.parametrize("output_flag", OUTPUT_MODE_FLAGS)
def test_conda_info_envs_lists_created_env(conda, empty_env, envs_flag, output_flag):
    """``conda info -e``/``--envs`` lists a created env in plain, quiet, and verbose modes."""
    env_name, env_path = empty_env

    result = _run_info_with_output_flag(conda, envs_flag, output_flag=output_flag)
    assert_envs_headers_present(result.stdout, envs_flag)
    assert_created_env_listed(result, env_name, env_path)


# Shell-dependent: the active marker requires observing a shell activation.
@pytest.mark.parametrize("envs_flag", ["-e", "--envs"])
def test_conda_info_envs_marks_activated_env_in_shell(conda_shell, empty_env, envs_flag):
    """``conda info -e``/``--envs`` marks an explicitly activated env as active."""
    env_name, env_path = empty_env

    result = conda_shell.run_in_activated_env(env_name, f"conda info {envs_flag}").assert_ok()
    env_list = PlainEnvList.from_stdout(result)

    active_env = env_list.active_env
    assert active_env is not None
    assert active_env.name == env_name
    assert active_env.active
    assert is_same_path(active_env.prefix, env_path)


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
    assert_created_env_listed(result, env_name, env_path)

    env_line = next(
        (
            line
            for line in output.splitlines()
            if line.split() and is_same_path(Path(line.split()[-1]), env_path)
        ),
        None,
    )
    assert env_line is not None, f"did not find size row for {env_path} in output:\n{output}"
    assert re.search(r"\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|TB)\b", env_line)


# =============================================================================
# Negative test cases
# =============================================================================


def test_conda_info_size_requires_envs_flag_negative(conda):
    """Negative case: ``conda info --size`` errors without ``-e``/``--envs``."""
    conda("info", "--size").assert_error(contains="--size can only be used with --envs")
