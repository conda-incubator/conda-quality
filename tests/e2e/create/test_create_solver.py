# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Solver Configuration options."""

from __future__ import annotations

from textwrap import dedent

import pytest
from create_asserts import (
    PACKAGE_NAME,
    PRIORITY_PACKAGE,
    assert_env_created,
    assert_env_not_created,
)
from shared.helpers import list_installed_packages

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.utils import unique_env_name

# =============================================================================
# Solver selection (--solver)
# =============================================================================


@pytest.mark.parametrize("solver", ["classic", "libmamba", "rattler"])
def test_create_with_solver(conda, envs_dir, solver):
    """``conda create --solver <name>`` uses the specified solver."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--solver", solver, PACKAGE_NAME).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)


# =============================================================================
# Channel priority (--strict-channel-priority, --no-channel-priority)
# =============================================================================


def test_create_strict_channel_priority(conda, envs_dir, tmp_path):
    """``conda create --strict-channel-priority`` excludes lower-priority channels.

    Real channels can't show this reliably, since flexible priority already pulls
    from the top channel when versions don't conflict. With pkg 1.0 in a high
    channel and 2.0 in a low one, requesting 2.0 succeeds under flexible
    priority but is unsatisfiable under strict, which ignores the low channel.
    """
    env_name = unique_env_name()
    high_channel = build_local_channel(
        tmp_path / "high", [Package(PRIORITY_PACKAGE, "1.0", depends=("python",))]
    )
    low_channel = build_local_channel(
        tmp_path / "low", [Package(PRIORITY_PACKAGE, "2.0", depends=("python",))]
    )
    channels = ("-c", high_channel.as_uri(), "-c", low_channel.as_uri())
    pinned_spec = f"{PRIORITY_PACKAGE}=2.0"

    # Baseline: flexible priority (the default) finds 2.0 in the low channel
    baseline_env = unique_env_name()
    conda("create", "-n", baseline_env, *channels, pinned_spec).assert_ok()
    baseline_installed = list_installed_packages(conda, "-n", baseline_env)
    baseline_record = baseline_installed.get(PRIORITY_PACKAGE)
    assert baseline_record is not None, f"{PRIORITY_PACKAGE} should be installed in the baseline"
    assert baseline_record.version == "2.0", (
        f"Baseline (no flag) should install {PRIORITY_PACKAGE}==2.0 from the low channel. "
        f"Got: {baseline_record.version}"
    )

    # Execute: --strict-channel-priority excludes the low channel, so the pin fails
    result = conda("create", "-n", env_name, *channels, "--strict-channel-priority", pinned_spec)
    result.assert_error(code=1, contains="UnsatisfiableError")
    assert_env_not_created(envs_dir, env_name)


def test_create_no_channel_priority_mixes_channels(conda, condarc, tmp_path):
    """``conda create --no-channel-priority`` overrides a strict .condarc setting.

    Real channels can't show this reliably: conda-forge/defaults' dependency
    graphs and metadata can change over time. Two local channels make it
    deterministic: with pkg 1.0 in a high channel and 2.0 in a low one, and
    channel_priority: strict configured in .condarc, the request must be
    unpinned -- strict and flexible priority both resolve to 1.0 from the high
    channel, and only --no-channel-priority picks the newer 2.0 from the low
    one (version wins over channel order when priority is disabled). Requesting
    a pinned version instead would make the outcome independent of the flag.
    """
    env_name = unique_env_name()
    high_channel = build_local_channel(
        tmp_path / "high", [Package(PRIORITY_PACKAGE, "1.0", depends=("python",))]
    )
    low_channel = build_local_channel(
        tmp_path / "low", [Package(PRIORITY_PACKAGE, "2.0", depends=("python",))]
    )
    condarc.write_text(
        dedent(f"""\
        channels:
          - {high_channel.as_uri()}
          - {low_channel.as_uri()}
        channel_priority: strict
        """)
    )

    # Baseline: strict priority only considers the high channel, so the unpinned
    # request resolves to 1.0 even though 2.0 exists in the low channel.
    baseline_env = unique_env_name()
    conda("create", "-n", baseline_env, PRIORITY_PACKAGE).assert_ok()
    baseline_installed = list_installed_packages(conda, "-n", baseline_env)
    baseline_record = baseline_installed.get(PRIORITY_PACKAGE)
    assert baseline_record is not None, f"{PRIORITY_PACKAGE} should be installed in the baseline"
    assert baseline_record.version == "1.0", (
        f"Strict priority should resolve {PRIORITY_PACKAGE} to 1.0 from the high channel. "
        f"Got: {baseline_record.version}"
    )

    # Execute: --no-channel-priority overrides the strict config, so the newer
    # 2.0 in the low channel wins on version alone.
    conda("create", "-n", env_name, "--no-channel-priority", PRIORITY_PACKAGE).assert_ok()
    installed = list_installed_packages(conda, "-n", env_name)
    record = installed.get(PRIORITY_PACKAGE)
    assert record is not None, f"{PRIORITY_PACKAGE} should be installed"
    assert record.version == "2.0", (
        f"--no-channel-priority should install the newer {PRIORITY_PACKAGE}==2.0 from the "
        f"low channel despite channel_priority: strict. Got: {record.version}"
    )
