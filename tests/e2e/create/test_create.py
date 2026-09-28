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
    assert_env_created,
    assert_env_not_created,
    assert_package_importable,
    list_installed_packages,
)

from conda_e2e.parsers.env import EnvList
from conda_e2e.utils import env_exists, env_prefix, unique_env_name

# =============================================================================
# Target Environment Specification (-n, -p)
# =============================================================================


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

    # Verify the package was installed
    installed = list_installed_packages(conda, *target)
    assert PACKAGE_NAME in installed, f"{PACKAGE_NAME} should be installed. Got: {installed.names}"

    # Verify environment is functional at runtime
    assert_package_importable(conda, PACKAGE_NAME, *target)


# =============================================================================
# options (--clone, --file)
# =============================================================================


@pytest.mark.parametrize("source_type", ["name", "path"])
def test_create_clone(conda, envs_dir, tmp_path, source_type):
    """``conda create --clone`` clones an environment by name or by prefix path."""
    source_name = unique_env_name()
    clone_name = unique_env_name()
    source_target = {
        "name": ("-n", source_name),
        "path": ("-p", str(tmp_path / "source-env")),
    }[source_type]
    clone_source = source_target[1]

    # Create source environment
    conda("create", *source_target, PACKAGE_NAME).assert_ok()
    source_packages = list_installed_packages(conda, *source_target)

    # Clone by name or by path
    conda("create", "-n", clone_name, "--clone", clone_source).assert_ok()

    assert_env_created(conda, envs_dir, clone_name)
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

    assert_package_importable(conda, PACKAGE_NAME, "-n", clone_name)


def test_create_from_requirements_file(conda, envs_dir):
    """``conda create --file`` creates an environment with every package it lists."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--file", str(REQUIREMENTS_FILE)).assert_ok()

    assert_env_created(conda, envs_dir, env_name)
    installed = list_installed_packages(conda, "-n", env_name)
    missing = set(REQUIREMENTS_PACKAGES) - set(installed.names)
    assert not missing, f"packages from {REQUIREMENTS_FILE.name} not installed: {missing}"
    assert_package_importable(conda, FILE_PACKAGE, "-n", env_name)


def test_create_from_environment_yml(conda, envs_dir):
    """``conda create --file environment.yml`` creates env, ignoring the name field.

    The environment.yml's ``name: should-be-ignored`` field must be ignored: the
    -n flag determines the env name, and no env named after the ignored field
    should exist.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--file", str(ENVIRONMENT_YML_FILE)).assert_ok()

    assert_env_created(conda, envs_dir, env_name)
    assert_env_not_created(envs_dir, "should-be-ignored")
    installed = list_installed_packages(conda, "-n", env_name)
    assert FILE_PACKAGE in installed, (
        f"{FILE_PACKAGE} from {ENVIRONMENT_YML_FILE.name} should be installed. "
        f"Got: {installed.names}"
    )


# =============================================================================
# Error handling
# =============================================================================


# Sentinels for args that need a tmp_path-derived value, resolved in the test body
# since parametrize's table is built before any fixture is available. Plain
# objects (not strings) so the `is` checks below can't accidentally match a
# real argument.
_MISSING_FILE = object()
_CONFLICT_PREFIX = object()


@pytest.mark.parametrize(
    ("args", "expected_code", "expected_error"),
    [
        (("--bogus-flag",), 2, "unrecognized arguments: --bogus-flag"),
        (("--clone", "nonexistent-env-12345"), 1, "EnvironmentLocationNotFound"),
        (("--file", _MISSING_FILE), 1, "EnvironmentFileNotFound"),
        (("-p", _CONFLICT_PREFIX, "python"), 2, "not allowed with argument"),
        (("nonexistent-pkg-xyz-99999",), 1, "PackagesNotFoundInChannelsError"),
    ],
    ids=[
        "unknown-option",
        "clone-nonexistent",
        "file-nonexistent",
        "name-prefix-conflict",
        "nonexistent-package",
    ],
)
def test_create_fails(conda, envs_dir, tmp_path, args, expected_code, expected_error):
    """``conda create`` fails with the expected exit code and error type."""
    env_name = unique_env_name()
    conflict_prefix = tmp_path / "some-env"
    substitutions = {
        _MISSING_FILE: str(tmp_path / "missing-env.yml"),
        _CONFLICT_PREFIX: str(conflict_prefix),
    }
    resolved_args = tuple(substitutions.get(arg, arg) for arg in args)

    conda("create", "-n", env_name, *resolved_args).assert_error(
        code=expected_code, contains=expected_error
    )
    assert_env_not_created(envs_dir, env_name)
    if _CONFLICT_PREFIX in args:
        # Only the name-prefix-conflict case ever passes conflict_prefix to conda;
        # for every other case this check would be vacuous, since nothing else
        # ever references that path.
        assert not env_exists(conflict_prefix), (
            f"Environment shouldn't exist at the conflicting prefix: {conflict_prefix}"
        )
