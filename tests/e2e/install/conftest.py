# SPDX-License-Identifier: BSD-3-Clause
"""Local fixtures for conda install tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from conda_e2e.utils import env_prefix, unique_env_name

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def empty_env(conda, envs_dir: Path) -> tuple[str, Path]:
    """Create an empty conda environment and return its (name, path)."""
    env_name = unique_env_name()
    conda("create", "-n", env_name).assert_ok()
    return env_name, env_prefix(envs_dir, env_name)
