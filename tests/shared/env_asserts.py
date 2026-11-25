# SPDX-License-Identifier: BSD-3-Clause
"""Assertions for environment creation and registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conda_e2e.parsers.env import EnvList
from conda_e2e.utils import env_exists

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def assert_registered_env_created(conda: Callable, prefix: Path) -> None:
    """Assert an environment exists on disk and in the environment listing."""
    assert env_exists(prefix), f"Environment should exist at {prefix}"
    listed = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert listed.get_by_prefix(prefix) is not None, (
        f"{prefix} not in conda env list. Prefixes: {listed.prefixes}"
    )
