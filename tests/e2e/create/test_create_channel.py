# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Channel Customization options."""

from __future__ import annotations

from create_helpers import (
    PACKAGE_NAME,
    assert_env_created,
    assert_env_not_created,
    assert_package_from_channel,
)

from conda_e2e.utils import unique_env_name

# =============================================================================
# Channel selection (-c, --channel)
# =============================================================================


def test_create_with_channel(conda, envs_dir):
    """``conda create -c conda-forge`` installs from specified channel."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "-c", "conda-forge", PACKAGE_NAME).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)
    assert_package_from_channel(conda, env_name, PACKAGE_NAME, "conda-forge")


def test_create_with_multiple_channels(conda, envs_dir):
    """``conda create -c A -c B`` searches channels in priority order.

    With conda-forge as the first channel, the package should come from there.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "-c", "conda-forge", "-c", "defaults", PACKAGE_NAME).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)
    assert_package_from_channel(conda, env_name, PACKAGE_NAME, "conda-forge")


def test_create_override_channels_excludes_defaults(conda, envs_dir):
    """``conda create -c conda-forge --override-channels <pkg>`` excludes defaults.

    Uses neo4j, a package in defaults but not conda-forge. With --override-channels,
    defaults is excluded, so the create must fail. This proves exclusion.
    """
    env_name = unique_env_name()
    package_name = "neo4j"

    # defaults is excluded, and since neo4j isn't on conda-forge, create must fail
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

    # Without --override-channels, falls back to defaults
    conda("create", "-n", env_name, "-c", "conda-forge", package_name).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=package_name)
    assert_package_from_channel(conda, env_name, package_name, "pkgs/main")


# =============================================================================
# Error handling
# =============================================================================


def test_create_override_channels_requires_channel(conda):
    """``conda create --override-channels`` without -c fails."""
    conda("create", "-n", unique_env_name(), "--override-channels", PACKAGE_NAME).assert_error(
        code=2, contains="override-channels"
    )
