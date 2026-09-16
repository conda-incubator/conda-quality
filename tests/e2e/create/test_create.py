# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create — Target Environment and top-level options.

Covers ``-n``, ``-p``, ``--clone``, ``--file``, and general error handling.
Output, Prompt, and Flow Control options live in ``test_create_output.py``.
"""

from __future__ import annotations

import pytest
from create_helpers import (
    ENVIRONMENT_YML_FILE,
    FILE_PACKAGE,
    PACKAGE_NAME,
    REQUIREMENTS_FILE,
    assert_env_created,
    assert_env_not_created,
    assert_package_importable,
)

from conda_e2e.parsers.env import EnvList
from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import env_exists, env_prefix, unique_env_name

# =============================================================================
# Target Environment Specification (-n, -p)
# =============================================================================


@pytest.mark.parametrize("by_prefix", [False, True], ids=["name", "prefix"])
def test_create_env(conda, envs_dir, tmp_path, by_prefix):
    """``conda create -n NAME`` and ``-p PATH`` both create a working environment.

    The env must land at the chosen location (under ``envs_dirs`` for -n, at the
    exact path for -p), be registered by prefix in both env-list output modes,
    and contain the requested package.
    """
    env_name = unique_env_name()
    prefix = tmp_path / "prefix-env" if by_prefix else env_prefix(envs_dir, env_name)
    target = ("-p", prefix) if by_prefix else ("-n", env_name)

    assert not env_exists(prefix), f"Environment shouldn't exist yet: {prefix}"
    conda("create", *target, PACKAGE_NAME).assert_ok()

    assert env_exists(prefix), f"Expected env directory at {prefix}"

    # Prefix envs created by path report no name; named envs must appear by name.
    listed = EnvList.from_stdout(conda("env", "list").assert_ok())
    assert listed.get_by_prefix(prefix) is not None, (
        f"{prefix} not in reported envs: {listed.prefixes}"
    )
    if not by_prefix:
        assert env_name in listed.names, f"{env_name} not in reported envs: {listed.names}"

    listed_json = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert listed_json.get_by_prefix(prefix) is not None, (
        f"{prefix} not in reported envs (--json): {listed_json.prefixes}"
    )

    # Verify the package was installed
    installed = PackageList.from_json(conda("list", *target, "--json").assert_ok())
    assert PACKAGE_NAME in installed, f"{PACKAGE_NAME} should be installed. Got: {installed.names}"

    # Verify environment is functional at runtime
    if by_prefix:
        assert_package_importable(conda, PACKAGE_NAME, prefix=prefix)
    else:
        assert_package_importable(conda, PACKAGE_NAME, env_name=env_name)


# =============================================================================
# options (--clone, --file)
# =============================================================================


def test_create_clone_by_name(conda, envs_dir):
    """``conda create --clone <name>`` clones an environment by name."""
    source_name = unique_env_name()
    clone_name = unique_env_name()

    # Create source environment
    conda("create", "-n", source_name, PACKAGE_NAME).assert_ok()

    # Clone by name
    conda("create", "-n", clone_name, "--clone", source_name).assert_ok()

    assert_env_created(conda, envs_dir, clone_name, expected_package=PACKAGE_NAME)
    assert_package_importable(conda, PACKAGE_NAME, env_name=clone_name)


def test_create_clone_by_path(conda, envs_dir, tmp_path):
    """``conda create --clone <path>`` clones an environment by prefix path."""
    source_prefix = tmp_path / "source-env"
    clone_name = unique_env_name()

    # Create source environment at a custom path
    conda("create", "-p", str(source_prefix), PACKAGE_NAME).assert_ok()

    # Clone by path
    conda("create", "-n", clone_name, "--clone", str(source_prefix)).assert_ok()

    assert_env_created(conda, envs_dir, clone_name, expected_package=PACKAGE_NAME)
    assert_package_importable(conda, PACKAGE_NAME, env_name=clone_name)


@pytest.mark.parametrize("flag", ["--file", "-f"], ids=["long", "short"])
def test_create_from_requirements_file(conda, envs_dir, flag):
    """``conda create --file`` / ``-f`` creates environment from requirements.txt."""
    env_name = unique_env_name()

    conda("create", "-n", env_name, flag, str(REQUIREMENTS_FILE)).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=FILE_PACKAGE)
    assert_package_importable(conda, FILE_PACKAGE, env_name=env_name)


def test_create_from_environment_yml(conda, envs_dir):
    """``conda create --file environment.yml`` creates env, ignoring the name field.

    The name field in environment.yml is ignored; the -n flag determines the env name.
    """
    env_name = unique_env_name()

    conda("create", "-n", env_name, "--file", str(ENVIRONMENT_YML_FILE)).assert_ok()

    assert_env_created(conda, envs_dir, env_name, expected_package=FILE_PACKAGE)
    assert_package_importable(conda, FILE_PACKAGE, env_name=env_name)


# =============================================================================
# Error handling
# =============================================================================


def test_create_rejects_unknown_option(conda):
    """An unrecognized create option fails with the argparse error on stderr."""
    conda("create", "--bogus-flag", "-n", unique_env_name()).assert_error(
        code=2, contains="unrecognized arguments: --bogus-flag"
    )


def test_create_clone_nonexistent_fails(conda, envs_dir):
    """``conda create --clone`` fails when the source environment doesn't exist."""
    env_name = unique_env_name()
    conda("create", "-n", env_name, "--clone", "nonexistent-env-12345").assert_error(
        code=1, contains="nonexistent-env-12345"
    )
    assert_env_not_created(envs_dir, env_name)


def test_create_file_nonexistent_fails(conda, envs_dir, tmp_path):
    """``conda create --file`` fails when the file doesn't exist."""
    env_name = unique_env_name()
    missing_file = tmp_path / "missing-env.yml"
    conda("create", "-n", env_name, "--file", str(missing_file)).assert_error(
        code=1, contains="missing-env.yml"
    )
    assert_env_not_created(envs_dir, env_name)


def test_create_conflicting_name_and_prefix_fails(conda, envs_dir, tmp_path):
    """``conda create -n NAME -p PATH`` fails with mutually exclusive error."""
    env_name = unique_env_name()
    conda(
        "create",
        "-n",
        env_name,
        "-p",
        str(tmp_path / "some-env"),
        "python",
    ).assert_error(code=2, contains="not allowed with argument")
    assert_env_not_created(envs_dir, env_name)


def test_create_nonexistent_package_fails(conda, envs_dir):
    """``conda create`` with a package that doesn't exist fails."""
    env_name = unique_env_name()
    bad_package = "nonexistent-pkg-xyz-99999"
    result = conda("create", "-n", env_name, bad_package).assert_error(code=1)
    assert bad_package in result.stderr, (
        f"Error should mention the missing package name. Got:\n{result.stderr}"
    )
    assert_env_not_created(envs_dir, env_name)
