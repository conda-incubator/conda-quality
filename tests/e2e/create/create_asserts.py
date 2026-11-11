# SPDX-License-Identifier: BSD-3-Clause
"""Shared assertion helpers and test data for conda create E2E tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from shared.helpers import list_installed_packages
from shared.package_asserts import require_cached_package_init_file

from conda_e2e.parsers.env import EnvList
from conda_e2e.utils import env_exists, env_prefix, package_init_file

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
# All packages declared in REQUIREMENTS_FILE, read from the file itself so this
# can't drift out of sync if tests/data/requirements.txt ever changes.
REQUIREMENTS_PACKAGES = tuple(
    line.strip() for line in REQUIREMENTS_FILE.read_text().splitlines() if line.strip()
)

# Fabricated packages for the local-channel priority tests in test_create_channel.py
# and test_create_solver.py. PRIORITY_PACKAGE exists in both a "high" and "low" local
# channel at different versions; LOW_ONLY_PACKAGE exists only in "low".
PRIORITY_PACKAGE = "conda-e2e-priority-pkg"
LOW_ONLY_PACKAGE = "conda-e2e-low-only-pkg"
# Exists only in the sandbox's "local" bld channel (CONDA_BLD_PATH), used by the
# --use-local tests. Nowhere else, so resolution proves the flag was honored.
LOCAL_PACKAGE = "conda-e2e-local-pkg"


def assert_env_created(
    conda: Callable,
    envs_dir: Path,
    env_name: str,
    *,
    expected_package: str | None = None,
) -> None:
    """Assert an environment was created and optionally contains an expected package.

    Args:
        conda: The conda runner fixture.
        envs_dir: The sandbox envs directory.
        env_name: The environment name to check.
        expected_package: If provided, assert this package is installed.
    """
    prefix = env_prefix(envs_dir, env_name)

    assert env_exists(prefix), f"Environment {env_name} should exist at {prefix}"

    env_list = EnvList.from_json(conda("env", "list", "--json").assert_ok())
    assert env_list.get_by_prefix(prefix) is not None, (
        f"Environment {env_name} not in conda env list. Prefixes: {env_list.prefixes}"
    )

    if expected_package:
        installed = list_installed_packages(conda, "-n", env_name)
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
    installed = list_installed_packages(conda, "-n", env_name)
    pkg = installed.get(package_name)
    assert pkg is not None, f"{package_name} not found in {env_name}. Got: {installed.names}"
    assert expected_channel in pkg.channel, (
        f"{package_name} should be from {expected_channel}. Got channel: {pkg.channel}"
    )


def require_package_init_files(
    cache_dir: Path,
    env_path: Path,
    package_name: str,
) -> tuple[Path, Path]:
    """Return ``package_name``'s ``__init__.py`` as ``(env_file, cache_file)``.

    Asserts the package is unpacked in the env and extracted once in the package
    cache, so callers can compare how the two files are stored.
    """
    env_file = package_init_file(env_path, package_name)
    assert env_file.is_file(), f"{package_name} should be unpacked on disk at {env_file}"
    return env_file, require_cached_package_init_file(cache_dir, package_name)


def assert_package_importable(
    conda: Callable,
    package_name: str,
    *target: str,
    import_name: str | None = None,
) -> None:
    """Assert a package can be imported in the environment.

    Runs ``python -c "import <package>"`` inside the environment via ``conda run``.
    This verifies the environment is functional and the package is actually usable,
    not just listed in conda's metadata.

    Args:
        conda: The conda runner fixture.
        package_name: The package to import.
        target: The environment selector conda expects, e.g. ``("-n", name)``
            or ``("-p", str(prefix))``.
        import_name: The Python import name when it differs from package_name.
    """
    if not target:
        raise ValueError("Must specify a target, e.g. ('-n', env_name) or ('-p', prefix)")

    module_name = import_name or package_name
    conda("run", *target, "python", "-c", f"import {module_name}").assert_ok()
