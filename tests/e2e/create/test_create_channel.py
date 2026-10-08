# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Channel Customization options."""

from __future__ import annotations

from create_asserts import (
    LOCAL_PACKAGE,
    LOW_ONLY_PACKAGE,
    PACKAGE_NAME,
    PRIORITY_PACKAGE,
    assert_env_created,
    assert_env_not_created,
    assert_package_from_channel,
)
from shared.helpers import list_installed_packages

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.utils import unique_env_name

# =============================================================================
# Channel selection (-c, --channel)
# =============================================================================


def test_create_with_channel(conda, envs_dir):
    """``conda create -c conda-forge`` installs from specified channel."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "-c", "conda-forge", PACKAGE_NAME).assert_ok()

    assert_env_created(conda, envs_dir, env_name)
    assert_package_from_channel(conda, env_name, PACKAGE_NAME, "conda-forge")


def test_create_with_multiple_channels(conda, tmp_path):
    """``conda create -c A -c B`` searches channels in priority order."""
    env_name = unique_env_name()
    high_channel = build_local_channel(
        tmp_path / "high", [Package(PRIORITY_PACKAGE, "1.0", depends=("python",))]
    )
    low_channel = build_local_channel(
        tmp_path / "low",
        [
            Package(PRIORITY_PACKAGE, "2.0", depends=("python",)),
            Package(LOW_ONLY_PACKAGE, "1.0", depends=("python",)),
        ],
    )

    conda(
        "create",
        "-n",
        env_name,
        "-c",
        high_channel.as_uri(),
        "-c",
        low_channel.as_uri(),
        PRIORITY_PACKAGE,
        LOW_ONLY_PACKAGE,
    ).assert_ok()

    installed = list_installed_packages(conda, "-n", env_name)
    priority_record = installed.get(PRIORITY_PACKAGE)
    assert priority_record is not None, f"{PRIORITY_PACKAGE} should be installed"
    assert priority_record.version == "1.0", (
        f"The higher-priority channel's version should win. "
        f"Got {PRIORITY_PACKAGE}=={priority_record.version}"
    )
    assert LOW_ONLY_PACKAGE in installed, (
        f"{LOW_ONLY_PACKAGE} (only in the lower-priority channel) should still be installed. "
        f"Got: {installed.names}"
    )


def test_create_override_channels_excludes_defaults(conda, envs_dir):
    """``conda create -c conda-forge --override-channels <pkg>`` excludes defaults.

    Uses neo4j, a package in defaults but not conda-forge. With --override-channels,
    defaults is excluded, so the create must fail. This proves exclusion.
    """
    env_name = unique_env_name()
    package_name = "neo4j"

    conda(
        "create",
        "-n",
        env_name,
        "-c",
        "conda-forge",
        "--override-channels",
        package_name,
    ).assert_error(code=1, contains="PackagesNotFoundInChannelsError")

    assert_env_not_created(envs_dir, env_name)


def test_create_channel_fallback_to_defaults(conda, envs_dir):
    """``conda create -c conda-forge <pkg>`` falls back to defaults when absent.

    Without --override-channels, conda searches defaults after conda-forge.
    neo4j isn't in conda-forge but is in defaults, so it succeeds.
    """
    env_name = unique_env_name()
    package_name = "neo4j"

    conda("create", "-n", env_name, "-c", "conda-forge", package_name).assert_ok()

    assert_env_created(conda, envs_dir, env_name)
    assert_package_from_channel(conda, env_name, package_name, "pkgs/main")


# =============================================================================
# Local channel (--use-local)
# =============================================================================


def test_create_use_local_installs_locally_built_package(conda, envs_dir, tmp_path):
    """``conda create --use-local`` resolves a package from the local bld channel.

    ``CONDA_BLD_PATH`` adds this sandboxed bld directory to the "local" multichannel;
    the default base ``conda-bld`` may also remain in that multichannel. The fabricated
    package is built only in this sandbox directory, so successful resolution proves
    ``--use-local`` searched the added local channel.
    """
    env_name = unique_env_name()
    bld_dir = build_local_channel(
        tmp_path / "bld", [Package(LOCAL_PACKAGE, "1.0", depends=("python",))]
    )

    conda(
        "create",
        "-n",
        env_name,
        "--use-local",
        LOCAL_PACKAGE,
        extra_env={"CONDA_BLD_PATH": str(bld_dir)},
    ).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=LOCAL_PACKAGE)


# =============================================================================
# Error handling
# =============================================================================


def test_create_override_channels_requires_channel(conda, envs_dir):
    """``conda create --override-channels`` without -c fails."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--override-channels", PACKAGE_NAME).assert_error(
        code=2,
        contains="At least one -c / --channel flag must be supplied when using --override-channels",
    )

    assert_env_not_created(envs_dir, env_name)


def test_create_without_use_local_cannot_resolve_built_package(conda, envs_dir, tmp_path):
    """Without ``--use-local``, a package that only exists in conda-bld is unresolvable.

    Same controlled setup and package as the --use-local test, minus the flag: the
    bld channel is configured via ``CONDA_BLD_PATH`` but only ``--use-local`` adds
    it to the searched channels, so the failure is attributable to the missing flag.
    """
    env_name = unique_env_name()
    bld_dir = build_local_channel(
        tmp_path / "bld", [Package(LOCAL_PACKAGE, "1.0", depends=("python",))]
    )

    conda(
        "create",
        "-n",
        env_name,
        LOCAL_PACKAGE,
        extra_env={"CONDA_BLD_PATH": str(bld_dir)},
    ).assert_error(code=1, contains="PackagesNotFoundInChannelsError")

    assert_env_not_created(envs_dir, env_name)
