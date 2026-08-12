# SPDX-License-Identifier: BSD-3-Clause
"""Assertion helpers for conda install E2E tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conda_e2e.utils import site_packages_dir

if TYPE_CHECKING:
    from pathlib import Path

    from conda_e2e.parsers.list import PackageList, PackageRecord
    from conda_e2e.result import CommandResult

NEW_PKG_INSTALLED_MSG = "The following NEW packages will be INSTALLED:"


def require_python_version(installed: PackageList) -> str:
    """Return the installed ``python`` package's version, asserting it's present."""
    python = installed.get("python")
    assert python is not None, "python should be installed as a dependency"
    return python.version


def assert_package_unpacked(
    env_path: Path,
    package_name: str,
    python_version: str | None = None,
) -> None:
    """Assert ``package_name`` is physically unpacked on disk (as a package dir)."""
    site_packages = site_packages_dir(env_path, python_version)
    init_file = site_packages / package_name / "__init__.py"
    assert init_file.is_file(), f"{package_name} should be unpacked on disk at {site_packages}"


def require_installed_record(
    installed: PackageList,
    package_name: str,
) -> PackageRecord:
    """Return ``package_name``'s record from ``installed``, asserting it's present."""
    record = installed.get(package_name)
    assert record is not None, f"{package_name} record should be found in conda list"
    return record


def assert_installed_version(
    installed: PackageList,
    package_name: str,
    expected_version: str,
    context: str | None = None,
) -> None:
    """Assert ``package_name`` is present in ``installed`` at exactly ``expected_version``.

    ``context`` is prefixed to the failure message to explain why this version was
    expected (e.g. a specific flag's documented behavior), for tests where the
    generic "expected X==Y" message alone wouldn't be diagnostic enough.
    """
    record = require_installed_record(installed, package_name)
    message = f"expected {package_name}=={expected_version}. Got: {record.version}"
    if context:
        message = f"{context} {message}"
    assert record.version == expected_version, message


def assert_install_output_has_new_packages(
    result: CommandResult,
    package_name: str | None = None,
) -> None:
    """Assert install output confirms package installation and optionally names a package."""
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    if package_name:
        assert package_name in result.stdout, (
            f"Install output should mention {package_name}. Got:\n{result.stdout}"
        )


def assert_package_present(installed: PackageList, package_name: str, env_name: str) -> None:
    """Assert ``package_name`` exists in ``installed`` for ``env_name``."""
    assert package_name in installed, (
        f"{package_name} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
