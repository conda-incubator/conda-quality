# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for creating environments from environment files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from shared.env_asserts import assert_registered_env_created
from shared.helpers import list_installed_packages

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.parsers.env import EnvList
from conda_e2e.parsers.env_create import PlainEnvCreateOutput
from conda_e2e.utils import env_exists, env_prefix, is_same_path, package_init_file, unique_env_name

if TYPE_CHECKING:
    from pathlib import Path

PACKAGE_NAME = "click"
ENVIRONMENT_FILE_NAME = "environment.yml"
SOLVER_UNSATISFIABLE_ERRORS = {
    "classic": "PackagesNotFoundInChannelsError",
    "libmamba": "LibMambaUnsatisfiableError",
    "rattler": "RattlerUnsatisfiableError",
}


def _write_environment_file(path: Path, name: str) -> None:
    """Write a named YAML environment definition requesting the test package."""
    path.write_text(f"name: {name}\ndependencies:\n  - {PACKAGE_NAME}\n", encoding="utf-8")


def _assert_environment_created_with_package(conda, prefix: Path) -> None:
    """Assert the environment is registered and the requested package is installed."""
    assert_registered_env_created(conda, prefix)
    package_file = package_init_file(prefix, PACKAGE_NAME)
    assert package_file.is_file(), f"Expected {PACKAGE_NAME} at {package_file}"
    installed = list_installed_packages(conda, "-p", str(prefix))
    assert PACKAGE_NAME in installed, f"{PACKAGE_NAME} not installed in {prefix}"


def _assert_not_created(conda, prefix: Path) -> None:
    """Assert the target directory and environment registration are absent."""
    assert not env_exists(prefix), f"Unexpected environment at {prefix}"
    listed = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert listed.get_by_prefix(prefix) is None, f"Unexpected registered environment: {prefix}"


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(233)
@pytest.mark.smoke
def test_env_create_from_file(conda, envs_dir, tmp_path):
    """Create an environment from a YAML file using the name it specifies."""
    name = unique_env_name()
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    prefix = env_prefix(envs_dir, name)
    _write_environment_file(environment_file, name)

    result = conda("env", "create", "--file", str(environment_file)).assert_ok()

    _assert_environment_created_with_package(conda, prefix)
    output = PlainEnvCreateOutput.from_stdout(result)
    assert is_same_path(output.prefix, prefix), (
        f"Expected environment location {prefix}, got {output.prefix}"
    )
    assert output.activation_target == name, (
        f"Expected activation name {name!r}, got {output.activation_target!r}"
    )


@pytest.mark.covers(235)
@pytest.mark.smoke
def test_env_create_from_file_at_prefix(conda, envs_dir, tmp_path):
    """Create from the specified YAML file at the explicit prefix, not the default location."""
    name = unique_env_name()
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    prefix = tmp_path / "target"
    _write_environment_file(environment_file, name)

    result = conda("env", "create", "-p", str(prefix), "--file", str(environment_file)).assert_ok()

    _assert_environment_created_with_package(conda, prefix)
    _assert_not_created(conda, env_prefix(envs_dir, name))
    output = PlainEnvCreateOutput.from_stdout(result)
    assert is_same_path(output.prefix, prefix), (
        f"Expected environment location {prefix}, got {output.prefix}"
    )
    assert is_same_path(output.activation_target, prefix), (
        f"Expected activation prefix {prefix}, got {output.activation_target!r}"
    )


@pytest.mark.covers(665)
def test_env_create_at_prefix_uses_default_file(conda, envs_dir, tmp_path):
    """Discover the default YAML file and create at the prefix, not the default location."""
    name = unique_env_name()
    prefix = tmp_path / "target"
    _write_environment_file(tmp_path / ENVIRONMENT_FILE_NAME, name)

    conda("env", "create", "-p", str(prefix), cwd=tmp_path).assert_ok()

    _assert_environment_created_with_package(conda, prefix)
    _assert_not_created(conda, env_prefix(envs_dir, name))


@pytest.mark.parametrize(
    "solver",
    [
        pytest.param("classic", marks=[pytest.mark.covers(240), pytest.mark.smoke]),
        pytest.param("libmamba", marks=[pytest.mark.covers(236), pytest.mark.smoke]),
        pytest.param("rattler", marks=[pytest.mark.covers(662), pytest.mark.smoke]),
    ],
)
def test_env_create_with_solver(conda, envs_dir, tmp_path, solver):
    """Create an environment from a YAML file with the specified solver option."""
    name = unique_env_name()
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    prefix = env_prefix(envs_dir, name)
    _write_environment_file(environment_file, name)

    conda("env", "create", "--file", str(environment_file), "--solver", solver).assert_ok()

    _assert_environment_created_with_package(conda, prefix)


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.parametrize(
    ("solver", "baseline_solver"),
    [
        pytest.param("classic", "libmamba", marks=pytest.mark.covers(667), id="classic"),
        pytest.param("libmamba", "classic", marks=pytest.mark.covers(668), id="libmamba"),
        pytest.param("rattler", "libmamba", marks=pytest.mark.covers(669), id="rattler"),
    ],
)
def test_env_create_solver_overrides_configured_solver(
    conda, condarc, tmp_path, solver, baseline_solver
):
    """Override the configured solver without creating an environment on failure."""
    channel = build_local_channel(
        tmp_path / "channel", [Package("a", "1.0", depends=("b >=2.0",)), Package("b", "1.0")]
    )
    channel_url = channel.as_uri()
    condarc.write_text(
        f"solver: {baseline_solver}\nchannels:\n  - {channel_url}\n"
        f"default_channels:\n  - {channel_url}\n",
        encoding="utf-8",
    )
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    environment_file.write_text(
        f"channels:\n  - {channel_url}\ndependencies:\n  - a\n", encoding="utf-8"
    )
    prefix = tmp_path / "target"
    create_args = ("--file", str(environment_file), "-p", str(prefix))

    conda("env", "create", *create_args).assert_error(
        code=1, contains=SOLVER_UNSATISFIABLE_ERRORS[baseline_solver]
    )
    _assert_not_created(conda, prefix)

    conda("env", "create", *create_args, "--solver", solver).assert_error(
        code=1, contains=SOLVER_UNSATISFIABLE_ERRORS[solver]
    )
    _assert_not_created(conda, prefix)


@pytest.mark.covers(663)
def test_env_create_rejects_unsupported_option(conda):
    """``conda env create`` reports unsupported options on stderr."""
    conda("env", "create", "--not-a-real-option").assert_error(
        code=2,
        contains="unrecognized arguments: --not-a-real-option",
    )


@pytest.mark.parametrize(
    "file_args",
    [
        pytest.param(("--file", "missing.yml"), marks=pytest.mark.covers(664), id="explicit-file"),
        pytest.param((), marks=pytest.mark.covers(666), id="default-file"),
    ],
)
def test_env_create_missing_file_fails(conda, tmp_path, file_args):
    """Reject a missing environment file, named or discovered, without creating an environment."""
    prefix = tmp_path / "target"

    conda("env", "create", "-p", str(prefix), *file_args, cwd=tmp_path).assert_error(
        code=1, contains="EnvironmentFileNotFound"
    )
    _assert_not_created(conda, prefix)


@pytest.mark.covers(670)
def test_env_create_without_target_fails(conda, envs_dir, tmp_path):
    """Reject a YAML file without a name when no target is specified."""
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    environment_file.write_text(f"dependencies:\n  - {PACKAGE_NAME}\n", encoding="utf-8")
    before = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    before_dirs = set(envs_dir.iterdir())

    conda("env", "create", "--file", str(environment_file)).assert_error(
        code=2, contains="The environment file(s) do not specify a name or prefix"
    )

    after = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert set(after.prefixes) == set(before.prefixes), "Registered environment prefixes changed"
    assert set(envs_dir.iterdir()) == before_dirs, f"Entries in {envs_dir} changed"
