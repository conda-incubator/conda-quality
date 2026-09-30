# SPDX-License-Identifier: BSD-3-Clause
"""Assertions shared by ``conda info --envs`` and ``conda env list``.

``conda env list`` is a documented alias of ``conda info --envs``; both render
the same environment-listing output through ``conda_e2e.parsers.env.EnvList``.
Kept here, not under either command's own suite, because both suites now
track this shared contract and must change together; ``test_env_list_matches_info_envs_output``
enforces the alias relationship itself.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from conda_e2e.parsers.info import CONDA_ENVIRONMENTS_HEADER
from conda_e2e.utils import is_same_path

if TYPE_CHECKING:
    from pathlib import Path

    from conda_e2e.parsers.env import EnvList, EnvRecord

# Marker legend lines conda prints above the env table: "*" flags the active env,
# "+" flags a frozen one. Local to this module rather than conda_e2e.parsers,
# because the parser matches markers by substring, not by this header text.
_ACTIVE_MARKER_HEADER = "# * -> active"
_FROZEN_MARKER_HEADER = "# + -> frozen"

# Rendered by ``--size`` in both commands' plain output, e.g. "12.3 MB".
SIZE_FIGURE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|TB)\b")


def require_env_by_prefix(env_list: EnvList, env_path: Path) -> EnvRecord:
    """Return the ``env_list`` record matching ``env_path``, asserting it is present."""
    env_record = env_list.get_by_prefix(env_path)
    assert env_record is not None, f"no environment with prefix {env_path} in {env_list.prefixes}"
    return env_record


def assert_single_active_env(env_list: EnvList) -> None:
    """Assert exactly one environment in ``env_list`` is marked active."""
    active_names = [env.name for env in env_list if env.active]
    assert sum(env.active for env in env_list) == 1, (
        f"expected exactly one active environment; got {active_names}"
    )


def assert_envs_headers_present(output: str, envs_flag: str) -> None:
    """Assert the stable header and marker-legend lines are present."""
    expected_headers = (CONDA_ENVIRONMENTS_HEADER, _ACTIVE_MARKER_HEADER, _FROZEN_MARKER_HEADER)
    missing_headers = [header for header in expected_headers if header not in output]
    assert not missing_headers, (
        f"{envs_flag} output missing {missing_headers}. Command output:\n{output}"
    )


def assert_created_env_listed(created_env: EnvRecord, env_name: str, env_path: Path) -> None:
    """Assert the created env is listed with the expected name and prefix path."""
    assert created_env.name == env_name
    assert is_same_path(created_env.prefix, env_path)


def assert_created_env_json_fields(created_env: EnvRecord, env_name: str, env_path: Path) -> None:
    """Assert stable JSON fields for a newly created environment entry."""
    assert_created_env_listed(created_env, env_name, env_path)
    assert created_env.created, "expected a created timestamp for a newly created env"
    assert created_env.last_modified, "expected a last_modified timestamp for a newly created env"
    assert created_env.base is False
    assert created_env.writable
    assert not created_env.frozen
