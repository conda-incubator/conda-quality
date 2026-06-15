# SPDX-License-Identifier: BSD-3-Clause
"""CRUD E2E tests for conda environments.

A small sample showing how to use the conda test-automation framework; it does
not yet cover the full env CRUD surface.
"""

from __future__ import annotations

from conda_e2e.parsers.env import parse_env_list_json, parse_env_list_stdout
from conda_e2e.parsers.list import parse_list_stdout
from conda_e2e.utils import env_exists, env_prefix, unique_env_name


def test_create_list_remove_empty_env(conda, envs_dir):
    """Create an env, see it listed (stdout and --json), then remove it."""
    env_name = unique_env_name()
    env_path = env_prefix(envs_dir, env_name)

    # Check no env exists before create
    assert not env_exists(env_path), f"Environment shouldn't exist yet: {env_path}"

    # Create
    conda("create", "-n", env_name).assert_ok()
    assert env_exists(env_path), f"expected env directory at {env_path}"

    # List envs
    result_stdout = conda("env", "list").assert_ok()
    existing_envs_stdout = parse_env_list_stdout(result_stdout)
    assert env_name in existing_envs_stdout.names, (
        f"{env_name} not in reported envs: {existing_envs_stdout.names}"
    )

    # List envs with --json
    result_json = conda("env", "list", "--json").assert_ok()
    existing_envs_json = parse_env_list_json(result_json)
    assert env_path in existing_envs_json, (
        f"{env_path} not in reported envs (--json): {existing_envs_json.prefixes}"
    )

    # Delete env
    conda("env", "remove", "-n", env_name).assert_ok()
    assert not env_exists(env_path), f"env directory still present at {env_path}"

    # Check no env exists after delete via conda
    result_json = conda("env", "list", "--json").assert_ok()
    assert env_path not in parse_env_list_json(result_json), (
        f"{env_path} should not be present in conda env list"
    )

    # Check no env exists on FS
    assert not env_exists(env_path), f"Environment shouldn't exist on filesystem: {env_path}"


def test_remove_missing_env_fails(conda, envs_dir):
    """Test removing non-existing environment fails with a valid code/message."""
    env_name = unique_env_name()
    env_path = env_prefix(envs_dir, env_name)

    result = conda("env", "remove", "-n", env_name)
    result.assert_error(code=1, contains=f"Not a conda environment: {env_path}")


def test_cant_create_env_without_accepting_tos(conda_no_tos, envs_dir):
    """Test that env can't be created if ToS hasn't been accepted."""
    env_name = unique_env_name()
    env_path = env_prefix(envs_dir, env_name)

    result = conda_no_tos("create", "-n", env_name)
    result.assert_error(
        code=1,
        contains="Terms of Service have not been accepted",
    )

    # Check no env has been created on filesystem
    assert not env_exists(env_path), f"Environment shouldn't exist: {env_path}"


def test_create_duplicate_env_overwrites(conda):
    """Test creating env with already existing name must overwrite the env."""
    name = unique_env_name()

    # Create env with some packages
    conda("create", "-n", name, "python=3.13").assert_ok()

    # Make sure the env has at least one package
    result_stdout = conda("list", "-n", name).assert_ok()
    installed_packages = parse_list_stdout(result_stdout)
    assert installed_packages.names, f"{name} env should have at least 1 package"

    # Try creating the env with the same name
    conda("create", "-n", name).assert_ok()

    # Make sure the env has been overwritten and has zero packages
    result_stdout = conda("list", "-n", name).assert_ok()
    installed_packages = parse_list_stdout(result_stdout)
    assert not installed_packages.names, f"{name} env should be overwritten and has no packages"
