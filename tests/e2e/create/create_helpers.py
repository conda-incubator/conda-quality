# SPDX-License-Identifier: BSD-3-Clause
"""Shared helpers for conda create E2E tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from conda_e2e.parsers.env import EnvList
from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import env_exists, env_prefix

if TYPE_CHECKING:
    from collections.abc import Callable

# Standard test package, consistent with install suite.
PACKAGE_NAME = "flask"

# Test data files
DATA_DIR = Path(__file__).parent.parent.parent / "data"
ENVIRONMENT_YML_FILE = DATA_DIR / "environment.yml"
REQUIREMENTS_FILE = DATA_DIR / "requirements.txt"

# Packages in test data files
FILE_PACKAGE = "click"


def assert_env_created(
    conda: Callable,
    envs_dir: Path,
    env_name: str,
    *,
    expected_package: str | None = None,
) -> None:
    """Assert an environment was created and optionally contains an expected package.

    Verifies:
    - Environment directory exists on disk
    - Environment is registered with conda (appears in ``conda env list``)
    - If expected_package provided, that package is installed

    Args:
        conda: The conda runner fixture.
        envs_dir: The sandbox envs directory.
        env_name: The environment name to check.
        expected_package: If provided, assert this package is installed.
    """
    prefix = env_prefix(envs_dir, env_name)

    # Verify env exists on disk
    assert env_exists(prefix), f"Environment {env_name} should exist at {prefix}"

    # Verify env is registered with conda
    env_list = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert env_list.get_by_prefix(prefix) is not None, (
        f"Environment {env_name} not in conda env list. Prefixes: {env_list.prefixes}"
    )

    if expected_package:
        installed = PackageList.from_json(conda("list", "-n", env_name, "--json").assert_ok())
        assert expected_package in installed, (
            f"{expected_package} should be installed in {env_name}. Got: {installed.names}"
        )


def assert_env_not_created(envs_dir: Path, env_name: str) -> None:
    """Assert an environment was NOT created."""
    prefix = env_prefix(envs_dir, env_name)
    assert not env_exists(prefix), f"Environment {env_name} should NOT exist at {prefix}"


def assert_package_from_channel(
    conda: Callable,
    env_name: str,
    package_name: str,
    expected_channel: str,
) -> None:
    """Assert a package was installed from the expected channel.

    Args:
        conda: The conda runner fixture.
        env_name: The environment name to check.
        package_name: The package to verify.
        expected_channel: Channel name that should appear in the package's channel field.
    """
    installed = PackageList.from_json(conda("list", "-n", env_name, "--json").assert_ok())
    pkg = installed.get(package_name)
    assert pkg is not None, f"{package_name} not found in {env_name}. Got: {installed.names}"
    assert expected_channel in pkg.channel, (
        f"{package_name} should be from {expected_channel}. Got channel: {pkg.channel}"
    )


def assert_package_importable(
    conda: Callable,
    package_name: str,
    *,
    import_name: str | None = None,
    env_name: str | None = None,
    prefix: Path | str | None = None,
) -> None:
    """Assert a package can be imported in the environment.

    Runs ``python -c "import <package>"`` inside the environment via ``conda run``.
    This verifies the environment is functional and the package is actually usable,
    not just listed in conda's metadata.

    Args:
        conda: The conda runner fixture.
        package_name: The package to import.
        import_name: The Python import name when it differs from package_name.
        env_name: The environment name (use -n).
        prefix: The environment prefix path (use -p). Mutually exclusive with env_name.
    """
    if env_name and prefix:
        raise ValueError("Specify env_name or prefix, not both")
    if not env_name and not prefix:
        raise ValueError("Must specify env_name or prefix")

    target = ("-n", env_name) if env_name else ("-p", str(prefix))
    module_name = import_name or package_name
    conda("run", *target, "python", "-c", f"import {module_name}").assert_ok()
