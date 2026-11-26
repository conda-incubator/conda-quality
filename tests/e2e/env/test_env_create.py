# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for creating environments from environment files."""

from __future__ import annotations

import re
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
import yaml
from packaging.version import Version
from shared.env_asserts import assert_registered_env_created
from shared.helpers import list_installed_packages
from shared.solver_constants import SOLVER_UNSATISFIABLE_ERRORS

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.parsers.env import EnvList
from conda_e2e.parsers.env_create import PlainEnvCreateOutput, environment_location_from_stdout
from conda_e2e.parsers.install import InstallResult as EnvCreateResult
from conda_e2e.utils import env_prefix, is_same_path, package_init_file, unique_env_name

if TYPE_CHECKING:
    from pathlib import Path

    from conda_e2e.parsers.list import PackageList
    from conda_e2e.result import CommandResult

PACKAGE_NAME = "click"
ENVIRONMENT_FILE_NAME = "environment.yml"


def _write_environment_file(path: Path, name: str) -> None:
    """Write a named YAML environment definition requesting the test package."""
    path.write_text(f"name: {name}\ndependencies:\n  - {PACKAGE_NAME}\n", encoding="utf-8")


def _assert_environment_created_with_package(conda, prefix: Path) -> PackageList:
    """Assert the environment is registered and the requested package is installed."""
    assert_registered_env_created(conda, prefix)
    package_file = package_init_file(prefix, PACKAGE_NAME)
    assert package_file.is_file(), f"Expected {PACKAGE_NAME} at {package_file}"
    installed = list_installed_packages(conda, "-p", str(prefix))
    assert PACKAGE_NAME in installed, f"{PACKAGE_NAME} not installed in {prefix}"
    return installed


def _assert_not_created(conda, prefix: Path) -> None:
    """Assert the target path and environment registration are absent."""
    assert not prefix.exists(), f"Unexpected target entry at {prefix}"
    listed = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert listed.get_by_prefix(prefix) is None, f"Unexpected registered environment: {prefix}"


def _assert_dry_run_spec(result: CommandResult, name: str) -> None:
    """Assert the legacy preview identifies the environment and resolved package."""
    lines = result.stdout.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("name:")]
    assert len(starts) == 1, f"Expected one YAML name field in output:\n{result.stdout}"
    output = yaml.safe_load("\n".join(lines[starts[0] :]))
    assert output["name"] == name
    dependencies = output["dependencies"]
    assert isinstance(dependencies, list), f"Expected dependency list, got {dependencies!r}"
    assert any(
        isinstance(spec, str) and re.fullmatch(rf"\S+::{re.escape(PACKAGE_NAME)}==\S+", spec)
        for spec in dependencies
    ), f"{PACKAGE_NAME} missing from resolved dependencies: {dependencies!r}"


def _assert_dry_run_plan(result: CommandResult, prefix: Path) -> None:
    """Assert the preview identifies the target and planned package."""
    assert "DryRunExit" in result.stderr
    assert is_same_path(environment_location_from_stdout(result), prefix)
    plan_parts = result.stdout.partition("The following NEW packages will be INSTALLED:")
    assert plan_parts[1], f"Missing installation plan in output:\n{result.stdout}"
    lines = plan_parts[2].strip().splitlines()
    end = next((i for i, line in enumerate(lines) if not line.strip()), len(lines))
    rows = [line.split() for line in lines[:end]]
    assert any(len(row) >= 2 and row[0] == PACKAGE_NAME for row in rows), (
        f"{PACKAGE_NAME} missing from installation plan:\n{rows}"
    )


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


@pytest.mark.covers(238)
def test_env_create_from_file_json(conda, envs_dir, tmp_path):
    """Report the created environment and linked packages in JSON."""
    name = unique_env_name()
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    prefix = env_prefix(envs_dir, name)
    _write_environment_file(environment_file, name)

    result = conda("env", "create", "--file", str(environment_file), "--json").assert_ok()

    output = EnvCreateResult.from_json(result)
    assert output.success
    assert is_same_path(output.prefix, prefix)
    assert not output.unlink_packages
    linked = {(package.name, package.version) for package in output.link_packages}
    installed = _assert_environment_created_with_package(conda, prefix)
    assert linked == {(package.name, package.version) for package in installed}


@pytest.mark.covers(237)
def test_env_create_from_file_verbose(conda, envs_dir, tmp_path):
    """Create with -v without the download progress banner and show activation guidance."""
    baseline_name = unique_env_name()
    verbose_name = unique_env_name()
    baseline_dir = tmp_path / "baseline"
    verbose_dir = tmp_path / "verbose"
    baseline_dir.mkdir()
    verbose_dir.mkdir()
    baseline_file = baseline_dir / ENVIRONMENT_FILE_NAME
    verbose_file = verbose_dir / ENVIRONMENT_FILE_NAME
    _write_environment_file(baseline_file, baseline_name)
    _write_environment_file(verbose_file, verbose_name)

    baseline = conda("env", "create", "--file", str(baseline_file)).assert_ok()
    verbose = conda("env", "create", "--file", str(verbose_file), "-v").assert_ok()

    banner = "Downloading and Extracting Packages"
    assert banner in baseline.stdout, f"Missing baseline progress banner:\n{baseline.stdout}"
    assert banner not in verbose.stdout, f"Unexpected verbose progress banner:\n{verbose.stdout}"
    assert PlainEnvCreateOutput.from_stdout(verbose).activation_target == verbose_name
    _assert_environment_created_with_package(conda, env_prefix(envs_dir, baseline_name))
    _assert_environment_created_with_package(conda, env_prefix(envs_dir, verbose_name))


@pytest.mark.covers(239)
@pytest.mark.isolated_pkgs_cache
def test_env_create_from_file_dry_run(conda, conda_version, envs_dir, tmp_path, cache_dir):
    """Preview the installation without creating an environment or downloading packages."""
    name = unique_env_name()
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    prefix = env_prefix(envs_dir, name)
    _write_environment_file(environment_file, name)
    before = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    before_dirs = set(envs_dir.iterdir())
    assert before.get_by_prefix(prefix) is None, f"Unexpected registered environment: {prefix}"
    assert not prefix.exists(), f"Unexpected target entry at {prefix}"

    result = conda("env", "create", "--file", str(environment_file), "--dry-run").assert_ok()

    # Before 26.7 the preview is YAML; newer plans report the prefix and DryRunExit.
    if Version(conda_version) < Version("26.7.0"):
        _assert_dry_run_spec(result, name)
    else:
        _assert_dry_run_plan(result, prefix)
    after = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert set(after.prefixes) == set(before.prefixes), "Registered environment prefixes changed"
    after_dirs = set(envs_dir.iterdir())
    envs_dir_probe_file = envs_dir / ".conda_envs_dir_test"
    assert after_dirs - {envs_dir_probe_file} == before_dirs - {envs_dir_probe_file}, (
        f"Entries in {envs_dir} changed: before={before_dirs}, after={after_dirs}"
    )
    assert not envs_dir_probe_file.exists() or envs_dir_probe_file.is_file()
    artifacts = {entry.name for entry in cache_dir.iterdir()} - {"cache", "urls", "urls.txt"}
    assert not artifacts, f"Unexpected package cache entries: {artifacts}"


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
    """Verify environment creation succeeds with each solver option.

    The successful output does not identify the solver used. Solver selection is
    checked separately by test_env_create_solver_overrides_configured_solver
    using distinguishable errors from a controlled failing solve.
    """
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
        dedent(f"""\
        solver: {baseline_solver}
        default_channels:
          - {channel_url}
        """),
        encoding="utf-8",
    )
    environment_file = tmp_path / ENVIRONMENT_FILE_NAME
    environment_file.write_text(
        dedent(f"""\
        channels:
          - {channel_url}
        dependencies:
          - a
        """),
        encoding="utf-8",
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
    ("file_args", "expected_file"),
    [
        pytest.param(
            ("--file", "missing.yml"),
            "missing.yml",
            marks=pytest.mark.covers(664),
            id="explicit-file",
        ),
        pytest.param((), ENVIRONMENT_FILE_NAME, marks=pytest.mark.covers(666), id="default-file"),
    ],
)
def test_env_create_missing_file_fails(conda, tmp_path, file_args, expected_file):
    """Reject a missing environment file, named or discovered, without creating an environment."""
    prefix = tmp_path / "target"

    result = conda("env", "create", "-p", str(prefix), *file_args, cwd=tmp_path).assert_error(
        code=1, contains="EnvironmentFileNotFound"
    )
    assert expected_file in result.stderr
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
