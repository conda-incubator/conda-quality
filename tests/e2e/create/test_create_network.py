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


def _repodata_cache_mtimes(cache_dir: Path) -> dict[str, int]:
    """Snapshot the defaults repodata cache entries: each payload plus its state file.

    Only entries for the defaults channels are included. The cache directory also
    holds unrelated entries (a url-less state file conda rewrites on its own
    schedule) that would make a whole-directory snapshot flaky. A 304 Not Modified
    rewrites the state file, so a changed mtime means conda contacted the server.
    """
    mtimes: dict[str, int] = {}
    for info_file in cache_dir.glob("cache/*.info.json"):
        if (
            not json.loads(info_file.read_text())
            .get("url", "")
            .startswith(_DEFAULTS_REPODATA_URL_PREFIX)
        ):
            continue
        payload = info_file.with_name(info_file.name.replace(".info.json", ".json"))
        for cache_file in (info_file, payload):
            if cache_file.exists():
                mtimes[cache_file.name] = cache_file.stat().st_mtime_ns
    return mtimes


# =============================================================================
# Positive test cases
# =============================================================================


def test_create_offline_uses_cached_packages(conda, envs_dir):
    """``conda create --offline`` builds an env from a cache filled by ``--download-only``."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--download-only", PACKAGE_NAME).assert_ok()
    assert_env_not_created(envs_dir, env_name)

    conda("create", "-n", env_name, "--offline", PACKAGE_NAME).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)
    assert_package_importable(conda, PACKAGE_NAME, "-n", env_name)


def test_create_use_index_cache_uses_expired_repodata(conda, cache_dir):
    """``conda create -C`` solves from expired cached repodata without server contact.

    ``CONDA_LOCAL_REPODATA_TTL=0`` makes conda treat cached repodata as expired, so
    the unflagged baseline must revalidate; ``-C`` uses the cache regardless.
    """
    prime_name = unique_env_name()
    env_name = unique_env_name()

    conda("create", "-n", prime_name, "--download-only", PACKAGE_NAME).assert_ok()
    before = _repodata_cache_mtimes(cache_dir)
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

    # Nothing may change: neither a payload re-download nor a state-only 304 write.
    assert _repodata_cache_mtimes(cache_dir) == before, (
        "-C should reuse expired repodata without contacting the server"
    )


def test_create_without_use_index_cache_revalidates_expired_repodata(conda, cache_dir):
    """Without ``-C``, expired cached repodata is revalidated against the server."""
    prime_name = unique_env_name()
    env_name = unique_env_name()

    conda("create", "-n", prime_name, "--download-only", PACKAGE_NAME).assert_ok()
    before = _repodata_cache_mtimes(cache_dir)
    assert before, "priming should have populated the defaults repodata cache"

    conda(
        "create",
        "-n",
        env_name,
        "--download-only",
        PACKAGE_NAME,
        extra_env=_REPODATA_ALWAYS_STALE,
    ).assert_ok()

    # A deleted entry is not a revalidation: require an entry that was rewritten or added.
    after = _repodata_cache_mtimes(cache_dir)
    revalidated = {name for name, mtime in after.items() if before.get(name) != mtime}
    assert revalidated, (
        "without -C, conda should revalidate expired repodata with the server; "
        f"none of {len(after)} defaults cache entries changed"
    )


# =============================================================================
# Negative test cases
# =============================================================================


def test_create_offline_fails_when_package_not_cached(conda, envs_dir):
    """``conda create --offline`` fails on an empty cache instead of fetching the package.

    Same command as the positive test, minus the primed cache: only the cache differs,
    so success there is attributable to the cache rather than to network access.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--offline", PACKAGE_NAME).assert_error(
        code=1, contains="PackagesNotFoundInChannelsError"
    )

    assert_env_not_created(envs_dir, env_name)
