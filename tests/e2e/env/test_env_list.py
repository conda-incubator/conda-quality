# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda env list`` (an alias of ``conda info --envs``)."""

from __future__ import annotations

import json

import pytest
from shared.helpers import drop_base_last_activated, freeze_env

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(226, 227, 271, 657)
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
    _assert_same_output(env_list_output, info_envs_output, is_json="--json" in flags)


@pytest.mark.covers(226, 227)
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
    """The alias holds with an activated env, so the active marker is compared too.

    Both commands share one activation: every ``conda activate`` refreshes the
    env's ``last_activated`` timestamp, so separate activations would differ.
    """
    env_name, env_path = make_env()
    freeze_env(env_path)

    env_list_output, info_envs_output = conda_shell.stdout_per_command_in_activated_env(
        env_name, env_list_cmd, info_envs_cmd
    )
    _assert_same_output(env_list_output, info_envs_output, is_json="--json" in env_list_cmd)


def _assert_same_output(first: str, second: str, *, is_json: bool) -> None:
    """Assert two env list outputs match, ignoring the base env's ``last_activated`` in JSON."""
    if not is_json:
        assert first == second
        return
    first_json, second_json = json.loads(first), json.loads(second)
    for payload in (first_json, second_json):
        drop_base_last_activated(payload)
    assert first_json == second_json


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.covers(658)
@pytest.mark.smoke
def test_env_list_rejects_unsupported_option(conda):
    """``conda env list`` reports unsupported options on stderr."""
    conda("env", "list", "--not-a-real-option").assert_error(
        code=2,
        contains="unrecognized arguments: --not-a-real-option",
    )
