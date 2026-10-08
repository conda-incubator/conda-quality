# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Networking options."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from create_asserts import (
    PACKAGE_NAME,
    assert_env_created,
    assert_env_not_created,
    assert_package_importable,
)

from conda_e2e.utils import unique_env_name

if TYPE_CHECKING:
    from pathlib import Path

# Channels under test: the defaults repodata. Other channels (e.g. the Anaconda
# cloud channel a plugin injects) have their own cache entries.
_DEFAULTS_REPODATA_URL_PREFIX = "https://repo.anaconda.com/pkgs/"

# Treat cached repodata as always expired, so any run without -C must contact the
# server. A documented config knob, instead of reaching into the cache's state files.
_REPODATA_ALWAYS_STALE = {"CONDA_LOCAL_REPODATA_TTL": "0"}


def _repodata_state_mtimes(cache_dir: Path) -> dict[str, int]:
    """Snapshot defaults repodata state-file mtimes, which change on server contact."""
    return {
        info_file.name: info_file.stat().st_mtime_ns
        for info_file in cache_dir.glob("cache/*.info.json")
        if json.loads(info_file.read_text())
        .get("url", "")
        .startswith(_DEFAULTS_REPODATA_URL_PREFIX)
    }


# =============================================================================
# Positive test cases
# =============================================================================


def test_create_offline_uses_cached_packages(conda, envs_dir, cache_dir):
    """``--offline`` creates an env from cached packages without revalidating repodata.

    With ``CONDA_LOCAL_REPODATA_TTL=0``, an unflagged create would contact the
    channel and update its cached state; offline mode must leave it unchanged.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()
    assert_env_not_created(envs_dir, env_name)
    before = _repodata_state_mtimes(cache_dir)
    assert before, "priming should have populated the defaults repodata cache"

    conda(
        "create",
        "-n",
        env_name,
        "--offline",
        PACKAGE_NAME,
        extra_env=_REPODATA_ALWAYS_STALE,
    ).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)
    assert_package_importable(conda, PACKAGE_NAME, "-n", env_name)
    assert _repodata_state_mtimes(cache_dir) == before, (
        "--offline should not revalidate cached repodata against the server"
    )


def test_create_use_index_cache_uses_expired_repodata(conda, cache_dir):
    """``conda create -C`` solves from expired cached repodata without server contact.

    ``CONDA_LOCAL_REPODATA_TTL=0`` makes conda treat cached repodata as expired, so
    the unflagged baseline must revalidate; ``-C`` uses the cache regardless.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()
    before = _repodata_state_mtimes(cache_dir)
    assert before, "priming should have populated the defaults repodata cache"

    conda(
        "create",
        "-n",
        env_name,
        "--download-only",
        "-C",
        PACKAGE_NAME,
        extra_env=_REPODATA_ALWAYS_STALE,
    ).assert_ok()

    assert _repodata_state_mtimes(cache_dir) == before, (
        "-C should reuse expired repodata without contacting the server"
    )


def test_create_without_use_index_cache_revalidates_expired_repodata(conda, cache_dir):
    """Without ``-C``, expired cached repodata is revalidated against the server."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()
    before = _repodata_state_mtimes(cache_dir)
    assert before, "priming should have populated the defaults repodata cache"

    conda(
        "create",
        "-n",
        env_name,
        "--download-only",
        PACKAGE_NAME,
        extra_env=_REPODATA_ALWAYS_STALE,
    ).assert_ok()

    after = _repodata_state_mtimes(cache_dir)
    revalidated = {
        name for name, refresh_mtime in after.items() if before.get(name) != refresh_mtime
    }
    assert revalidated, (
        "without -C, conda should revalidate expired repodata with the server; "
        f"none of {len(after)} defaults repodata state files changed"
    )


# =============================================================================
# Negative test cases
# =============================================================================


def test_create_offline_fails_when_package_not_cached(conda, envs_dir):
    """``conda create --offline`` cannot solve with an empty repodata cache.

    With no cached channel metadata, offline mode cannot solve the requested
    package; the command fails before creating an environment.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--offline", PACKAGE_NAME).assert_error(
        code=1, contains="PackagesNotFoundInChannelsError"
    )

    assert_env_not_created(envs_dir, env_name)
