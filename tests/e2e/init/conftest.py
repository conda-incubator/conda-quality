# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures shared by ``conda init`` E2E tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from init_asserts import (
    BASH_PROFILES,
    PROFILE_SENTINEL,
    InitPlan,
    require_init_plan,
)

from conda_e2e.parsers.init import InitResult
from conda_e2e.shells import Shell
from conda_e2e.utils import IS_MACOS, IS_WINDOWS, is_same_path
from conda_e2e.windows_registry import preserve_autorun, read_autorun

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


@pytest.fixture
def sandbox_home(isolated_env_vars: Mapping[str, str]) -> Path:
    """Return the sandboxed home directory from the isolated environment."""
    return Path(isolated_env_vars["HOME"])


@pytest.fixture
def expected_profiles(sandbox_home: Path) -> dict[Shell, Path]:
    """Return the default shell profiles expected for this platform."""
    if IS_WINDOWS:
        (sandbox_home / "Documents").mkdir(exist_ok=True)
        return {
            Shell.WINDOWS_POWERSHELL: sandbox_home / "Documents/WindowsPowerShell/profile.ps1",
            Shell.POWERSHELL: sandbox_home / "Documents/PowerShell/profile.ps1",
        }
    return {Shell.BASH: sandbox_home / (".bash_profile" if IS_MACOS else ".bashrc")}


@pytest.fixture
def init_state_guard(allow_host_changes: bool) -> Iterator[tuple[object, int] | None]:
    """Gate, lock, snapshot, and restore AutoRun across discovery and the test."""
    if IS_WINDOWS and not allow_host_changes:
        pytest.skip(
            "conda init may write the host cmd.exe AutoRun registry value; "
            "pass --allow-host-changes to allow and restore it"
        )
    with preserve_autorun() as original_value:
        yield original_value


@pytest.fixture
def init_plan(conda, sandbox_home, install_root, expected_profiles, init_state_guard) -> InitPlan:
    """Discover and validate targets before running bare ``conda init``."""
    preview = conda("init", "--dry-run").assert_ok()
    if IS_WINDOWS and read_autorun() != init_state_guard:
        pytest.fail("Init discovery unexpectedly changed the AutoRun registry value")
    existing = [path for path in expected_profiles.values() if path.exists()]
    if existing:
        pytest.fail(f"Init discovery unexpectedly created profiles: {existing}")
    return require_init_plan(
        install_root, sandbox_home, expected_profiles, InitResult.from_stdout(preview).targets
    )


@pytest.fixture
def seeded_profiles(init_plan: InitPlan, sandbox_home: Path) -> tuple[Path, ...]:
    """Seed the sentinel into the planned profiles and return the sibling profiles.

    A sibling is a bash profile that bare ``init`` did not report, so a test can
    prove ``init`` leaves it untouched.
    """
    siblings = (
        ()
        if IS_WINDOWS
        else tuple(
            path
            for path in (sandbox_home / name for name in BASH_PROFILES)
            if not any(is_same_path(path, profile) for profile in init_plan.profiles.values())
        )
    )
    for path in (*init_plan.profiles.values(), *siblings):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PROFILE_SENTINEL)
    return siblings


@pytest.fixture
def installation_files(init_plan: InitPlan) -> dict[Path, bytes]:
    """Snapshot init targets inside the installation before a test invocation."""
    return {path: path.read_bytes() for path in init_plan.installation}
