# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda env list`` (an alias of ``conda info --envs``)."""

from __future__ import annotations

import pytest
from shared.helpers import freeze_env

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.smoke
@pytest.mark.parametrize(
    "flags",
    [(), ("--json",), ("--size",), ("--size", "--json")],
    ids=["plain", "json", "size", "size-json"],
)
def test_env_list_matches_info_envs(conda, make_env, flags):
    """``conda env list`` matches ``conda info --envs``, its documented alias."""
    make_env()
    _, frozen_path = make_env()
    freeze_env(frozen_path)

    env_list_output = conda("env", "list", *flags).assert_ok().stdout
    info_envs_output = conda("info", "--envs", *flags).assert_ok().stdout
    assert env_list_output == info_envs_output


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("env_list_cmd", "info_envs_cmd"),
    [
        ("conda env list", "conda info --envs"),
        ("conda env list --json", "conda info --envs --json"),
    ],
    ids=["plain", "json"],
)
def test_env_list_matches_info_envs_when_activated(
    conda_shell, make_env, env_list_cmd, info_envs_cmd
):
    """The alias holds with an activated env, so the active marker is compared too."""
    env_name, env_path = make_env()
    freeze_env(env_path)

    env_list_result = conda_shell.run_in_activated_env(env_name, env_list_cmd)
    info_envs_result = conda_shell.run_in_activated_env(env_name, info_envs_cmd)
    assert env_list_result.assert_ok().stdout == info_envs_result.assert_ok().stdout


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
