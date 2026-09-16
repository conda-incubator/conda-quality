# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Solver Configuration options."""

from __future__ import annotations

from textwrap import dedent

import pytest
from helpers import PACKAGE_NAME, assert_env_created

from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import unique_env_name

# =============================================================================
# Solver selection (--solver)
# =============================================================================


@pytest.mark.parametrize("solver", ["classic", "libmamba", "rattler"])
def test_create_with_solver(conda, envs_dir, solver):
    """``conda create --solver <name>`` uses the specified solver."""
    env_name = unique_env_name()

    result = conda("create", "-n", env_name, "--solver", solver, PACKAGE_NAME)

    # Some solvers may not be available; check for availability error
    if result.returncode != 0:
        if "solver" in result.stderr.lower() and "not available" in result.stderr.lower():
            pytest.skip(f"Solver '{solver}' not available in this conda installation")
        result.assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)


# =============================================================================
# Channel priority (--strict-channel-priority, --no-channel-priority)
# =============================================================================


def test_create_strict_channel_priority(conda, envs_dir, condarc):
    """``conda create --strict-channel-priority`` only pulls from the top channel.

    With strict priority, all packages (including dependencies) must come from
    the highest-priority channel that has them.
    """
    env_name = unique_env_name()
    condarc.write_text(
        dedent("""\
        channels:
          - conda-forge
          - defaults
        """)
    )

    conda("create", "-n", env_name, "--strict-channel-priority", PACKAGE_NAME).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)

    # Verify every installed package came from conda-forge only
    installed = PackageList.from_json(conda("list", "-n", env_name, "--json").assert_ok())
    channels = {pkg.channel for pkg in installed}
    assert channels == {"conda-forge"}, (
        f"--strict-channel-priority should pull every package from conda-forge only. "
        f"Got channels: {channels}"
    )


def test_create_no_channel_priority_mixes_channels(conda, envs_dir, condarc):
    """``conda create --no-channel-priority`` overrides a strict .condarc setting.

    Even with channel_priority: strict in config, the flag allows the solver
    to pull packages from any configured channel.
    """
    env_name = unique_env_name()
    channel_name = "pkgs/main"
    condarc.write_text(
        dedent("""\
        channels:
          - conda-forge
          - defaults
        channel_priority: strict
        """)
    )

    conda("create", "-n", env_name, "--no-channel-priority", PACKAGE_NAME).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)

    # Verify at least one dependency came from defaults, proving the strict
    # channel_priority config was overridden
    installed = PackageList.from_json(conda("list", "-n", env_name, "--json").assert_ok())
    channels = {pkg.channel for pkg in installed}
    assert channel_name in channels, (
        f"--no-channel-priority should allow deps from defaults ({channel_name}) despite "
        f"channel_priority: strict. Got channels: {channels}"
    )
