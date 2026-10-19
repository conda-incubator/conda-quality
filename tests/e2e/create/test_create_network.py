# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Networking options."""

from __future__ import annotations

import pytest
from create_asserts import (
    PACKAGE_NAME,
    assert_env_created,
    assert_env_not_created,
    assert_package_importable,
)

from conda_e2e.utils import unique_env_name

# Treat cached repodata as always expired for online runs without -C.
_REPODATA_ALWAYS_STALE = {"CONDA_LOCAL_REPODATA_TTL": "0"}

# Make any attempted HTTPS request fail immediately instead of relying on cache-file changes.
_NETWORK_BLOCKED = {
    "HTTPS_PROXY": "http://127.0.0.1:1",
    "NO_PROXY": "",
    "https_proxy": "http://127.0.0.1:1",
    "no_proxy": "",
    "CONDA_REMOTE_MAX_RETRIES": "0",
    "CONDA_NUMBER_CHANNEL_NOTICES": "0",
}


# =============================================================================
# Offline mode (--offline)
# =============================================================================


@pytest.mark.covers(170)
def test_create_offline_uses_cached_packages(conda, envs_dir):
    """``--offline`` creates an env from cached packages without network access.

    The proxy blocks network access, while ``--download-only`` primes the package
    and repodata caches needed for the offline create.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()
    assert_env_not_created(envs_dir, env_name)

    conda(
        "create",
        "-n",
        env_name,
        "--offline",
        PACKAGE_NAME,
        extra_env={**_REPODATA_ALWAYS_STALE, **_NETWORK_BLOCKED},
    ).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)
    assert_package_importable(conda, PACKAGE_NAME, "-n", env_name)


@pytest.mark.covers(170)
def test_create_offline_fails_without_cached_repodata(conda, envs_dir):
    """``conda create --offline`` cannot solve with an empty repodata cache.

    With no cached channel metadata, offline mode cannot solve the requested
    package; the command fails before creating an environment.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--offline", PACKAGE_NAME).assert_error(
        code=1, contains="PackagesNotFoundInChannelsError"
    )

    assert_env_not_created(envs_dir, env_name)


@pytest.mark.covers(170)
def test_create_offline_refuses_to_download_uncached_packages(conda, envs_dir):
    """``conda create --offline`` fails rather than downloading a package.

    ``--dry-run`` caches repodata but downloads no packages, so the offline solve
    succeeds and only the package download is refused.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--dry-run", PACKAGE_NAME).assert_ok()

    conda("create", "-n", env_name, "--offline", PACKAGE_NAME).assert_error(
        code=1, contains="OfflineError"
    )

    assert_env_not_created(envs_dir, env_name)


# =============================================================================
# Index cache (-C, --use-index-cache)
# =============================================================================


@pytest.mark.covers(169)
@pytest.mark.smoke
def test_create_use_index_cache_uses_expired_repodata(conda, envs_dir):
    """``conda create -C`` creates from expired cached repodata without network access.

    ``CONDA_LOCAL_REPODATA_TTL=0`` expires the cached repodata. With network access
    blocked, success proves ``-C`` used the cache.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()

    conda(
        "create",
        "-n",
        env_name,
        "-C",
        PACKAGE_NAME,
        extra_env={**_REPODATA_ALWAYS_STALE, **_NETWORK_BLOCKED},
    ).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)
    assert_package_importable(conda, PACKAGE_NAME, "-n", env_name)


def test_create_without_use_index_cache_revalidates_expired_repodata(conda, envs_dir):
    """Without ``-C``, stale repodata requires a server request before solving."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()

    conda(
        "create",
        "-n",
        env_name,
        PACKAGE_NAME,
        extra_env={**_REPODATA_ALWAYS_STALE, **_NETWORK_BLOCKED},
    ).assert_error(code=1, contains="ProxyError")

    assert_env_not_created(envs_dir, env_name)
