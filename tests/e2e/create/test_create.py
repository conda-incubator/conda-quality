# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create — Target Environment and top-level options."""

from __future__ import annotations

import pytest
from create_asserts import (
    ENVIRONMENT_YML_FILE,
    FILE_PACKAGE,
    PACKAGE_NAME,
    REQUIREMENTS_FILE,
    REQUIREMENTS_PACKAGES,
    assert_env_not_created,
    assert_package_importable,
    require_package_init_files,
)
from shared.helpers import list_installed_packages, pick_second_newest_and_latest

from conda_e2e.parsers.env import EnvList
from conda_e2e.utils import env_exists, env_prefix, unique_env_name

# =============================================================================
# Target Environment Specification (-n, -p)
# =============================================================================


@pytest.mark.covers(151, 153)
@pytest.mark.parametrize("target_type", ["name", "prefix"])
def test_create_env(conda, envs_dir, tmp_path, target_type):
    """``conda create -n NAME`` and ``-p PATH`` both create a working environment.

    The env must land at the chosen location (under ``envs_dirs`` for -n, at the
    exact path for -p), be registered by prefix in both env-list output modes,
    and contain the requested package.
    """
    env_name = unique_env_name()
    target, prefix = {
        "name": (("-n", env_name), env_prefix(envs_dir, env_name)),
        "prefix": (("-p", str(tmp_path / "prefix-env")), tmp_path / "prefix-env"),
    }[target_type]

    assert not env_exists(prefix), f"Environment shouldn't exist yet: {prefix}"
    conda("create", *target, PACKAGE_NAME).assert_ok()

    assert env_exists(prefix), f"Expected env directory at {prefix}"

    listed = EnvList.from_stdout(conda("env", "list").assert_ok())
    assert listed.get_by_prefix(prefix) is not None, (
        f"{prefix} not in reported envs: {listed.prefixes}"
    )

    listed_json = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert listed_json.get_by_prefix(prefix) is not None, (
        f"{prefix} not in reported envs (--json): {listed_json.prefixes}"
    )

    installed = list_installed_packages(conda, *target)
    assert PACKAGE_NAME in installed, f"{PACKAGE_NAME} should be installed. Got: {installed.names}"

    assert_package_importable(conda, PACKAGE_NAME, *target)


# =============================================================================
# options (--clone, --file)
# =============================================================================


@pytest.mark.covers(154, 155)
@pytest.mark.parametrize("source_type", ["name", "path"])
def test_create_clone(conda, tmp_path, source_type):
    """``conda create --clone`` clones an environment by name or by prefix path.

    The source env is seeded with an older (non-latest) version of the package:
    a broken clone that silently installs the latest version instead of copying
    the source's would otherwise be indistinguishable, since both resolve to the
    same records when the source is already at the latest version.
    """
    source_name = unique_env_name()
    clone_name = unique_env_name()
    source_target = {
        "name": ("-n", source_name),
        "path": ("-p", str(tmp_path / "source-env")),
    }[source_type]
    clone_source = source_target[1]
    source_version, _ = pick_second_newest_and_latest(conda, PACKAGE_NAME)

    # Create source environment at a non-latest version
    conda("create", *source_target, f"{PACKAGE_NAME}={source_version}").assert_ok()
    source_packages = list_installed_packages(conda, *source_target)

    conda("create", "-n", clone_name, "--clone", clone_source).assert_ok()

    clone_packages = list_installed_packages(conda, "-n", clone_name)

    source_records = {package.name: package for package in source_packages}
    clone_records = {package.name: package for package in clone_packages}
    common_names = source_records.keys() & clone_records.keys()
    differing = [name for name in common_names if source_records[name] != clone_records[name]]
    assert clone_records == source_records, (
        f"Clone should reproduce every source package exactly (version, build, channel). "
        f"Source-only: {source_records.keys() - clone_records.keys()}, "
        f"Clone-only: {clone_records.keys() - source_records.keys()}, "
        f"Differing: {differing}"
    )
    source_record = source_records[PACKAGE_NAME]
    assert source_record.version == source_version, (
        f"Source env should have {PACKAGE_NAME}=={source_version}. Got: {source_record.version}"
    )

    assert_package_importable(conda, PACKAGE_NAME, "-n", clone_name)


@pytest.mark.covers(185)
def test_create_from_requirements_file(conda):
    """``conda create --file`` creates an environment with every package it lists."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--file", str(REQUIREMENTS_FILE)).assert_ok()

    installed = list_installed_packages(conda, "-n", env_name)
    missing = set(REQUIREMENTS_PACKAGES) - set(installed.names)
    assert not missing, f"packages from {REQUIREMENTS_FILE.name} not installed: {missing}"


@pytest.mark.covers(197)
def test_create_from_environment_yml(conda, envs_dir):
    """``conda create --file environment.yml`` creates env, ignoring the name field.

    The environment.yml's ``name: should-be-ignored`` field must be ignored: the
    -n flag determines the env name, and no env named after the ignored field
    should exist.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--file", str(ENVIRONMENT_YML_FILE)).assert_ok()

    assert_env_not_created(envs_dir, "should-be-ignored")
    installed = list_installed_packages(conda, "-n", env_name)
    assert FILE_PACKAGE in installed, (
        f"{FILE_PACKAGE} from {ENVIRONMENT_YML_FILE.name} should be installed. "
        f"Got: {installed.names}"
    )


# =============================================================================
# Package linking (--copy)
# =============================================================================


def test_create_hardlinks_to_cache_by_default(conda, envs_dir, cache_dir):
    """``conda create`` hardlinks package files to the cache by default."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, PACKAGE_NAME).assert_ok()

    env_file, cache_file = require_package_init_files(
        cache_dir, env_prefix(envs_dir, env_name), PACKAGE_NAME
    )
    assert env_file.samefile(cache_file), (
        "create should hardlink to the cache by default, but made a copy instead"
    )


def test_create_copy_creates_file_copies(conda, envs_dir, cache_dir):
    """``conda create --copy`` copies package files instead of hardlinking to the cache."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--copy", PACKAGE_NAME).assert_ok()

    env_file, cache_file = require_package_init_files(
        cache_dir, env_prefix(envs_dir, env_name), PACKAGE_NAME
    )
    assert env_file.stat().st_size > 0, f"{env_file} is empty, so a byte comparison proves nothing"
    assert not env_file.samefile(cache_file), (
        "--copy should create an independent file, not a hardlink to the cache"
    )
    assert env_file.stat().st_nlink == 1, (
        "--copy should not hardlink the environment file to any other file"
    )
    assert env_file.read_bytes() == cache_file.read_bytes(), (
        "--copy should produce a file with content identical to the cache"
    )


# =============================================================================
# Error handling
# =============================================================================


@pytest.mark.covers(202)
@pytest.mark.parametrize(
    ("args", "expected_code", "expected_error"),
    [
        (("--bogus-flag",), 2, "unrecognized arguments: --bogus-flag"),
        (("--clone", "nonexistent-env-12345"), 1, "EnvironmentLocationNotFound"),
        (("nonexistent-pkg-xyz-99999",), 1, "PackagesNotFoundInChannelsError"),
    ],
    ids=[
        "unknown-option",
        "clone-nonexistent",
        "nonexistent-package",
    ],
)
def test_create_fails(conda, envs_dir, args, expected_code, expected_error):
    """``conda create`` fails with the expected exit code and error type."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, *args).assert_error(code=expected_code, contains=expected_error)
    assert_env_not_created(envs_dir, env_name)


@pytest.mark.covers(201)
def test_create_file_nonexistent_fails(conda, envs_dir, tmp_path):
    """``conda create --file`` fails when the file doesn't exist.

    Uses ``tmp_path`` so the path is guaranteed absent on every platform, rather
    than assuming e.g. ``/nonexistent`` doesn't exist.
    """
    env_name = unique_env_name()
    missing_file = tmp_path / "missing-env.yml"

    conda("create", "-n", env_name, "--file", str(missing_file)).assert_error(
        code=1, contains="EnvironmentFileNotFound"
    )
    assert_env_not_created(envs_dir, env_name)


@pytest.mark.covers(200)
def test_create_conflicting_name_and_prefix_fails(conda, envs_dir, tmp_path):
    """``conda create -n NAME -p PATH`` fails: -n and -p are mutually exclusive."""
    env_name = unique_env_name()
    conflict_prefix = tmp_path / "some-env"

    conda("create", "-n", env_name, "-p", str(conflict_prefix), "python").assert_error(
        code=2, contains="not allowed with argument"
    )
    assert_env_not_created(envs_dir, env_name)
    assert not env_exists(conflict_prefix), (
        f"Environment shouldn't exist at the conflicting prefix: {conflict_prefix}"
    )
