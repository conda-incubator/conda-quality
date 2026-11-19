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
    require_init_targets,
)

from conda_e2e.utils import IS_WINDOWS, is_same_path
from conda_e2e.windows_registry import preserve_autorun

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


@pytest.fixture
def sandbox_home(isolated_env_vars: Mapping[str, str]) -> Path:
    """Return the sandboxed home directory from the isolated environment."""
    return Path(isolated_env_vars.get("HOME") or isolated_env_vars["USERPROFILE"])


def _prepare_home(home: Path) -> dict[str, str]:
    """Seed ``home``'s Documents folder and point PowerShell's home lookup at it.

    PowerShell resolves ``$PROFILE`` from the home and Documents folders; without
    them a host reports an empty profile path and ``conda init`` has nothing to write.
    """
    if not IS_WINDOWS:
        return {}
    for relative in ("Documents", "Documents/WindowsPowerShell", "Documents/PowerShell"):
        (home / relative).mkdir(parents=True, exist_ok=True)
    drive = home.drive
    return {"HOMEDRIVE": drive, "HOMEPATH": str(home)[len(drive) :]} if drive else {}


@pytest.fixture
def init_env(sandbox_home: Path) -> dict[str, str]:
    """Extra environment that resolves ``$PROFILE`` inside the sandbox home."""
    return _prepare_home(sandbox_home)


@pytest.fixture
def host_changes_allowed(allow_host_changes: bool) -> None:
    """Skip init tests before any invocation unless host changes are explicitly allowed."""
    if IS_WINDOWS and not allow_host_changes:
        pytest.skip(
            "conda init may write the host cmd.exe AutoRun registry value; "
            "pass --allow-host-changes to allow and restore it"
        )


@pytest.fixture(autouse=True)
def init_state_guard(request: pytest.FixtureRequest) -> Iterator[tuple[object, int] | None]:
    """Gate, lock, snapshot, and restore AutoRun across discovery and the test."""
    request.getfixturevalue("host_changes_allowed")
    with preserve_autorun() as original_value:
        yield original_value


@pytest.fixture
def init_plan(conda, sandbox_home, tmp_path) -> InitPlan:
    """Discover the targets a bare ``conda init`` run would touch.

    Discovery uses a disposable home, so it cannot seed or mutate the profile
    used by the invocation under test. The autouse registry guard has already
    gated access, acquired the lock, and saved AutoRun before discovery runs.
    """
    probe_home = tmp_path / "probe-home"
    probe_home.mkdir()
    probe_env = {"HOME": str(probe_home), "USERPROFILE": str(probe_home)} | _prepare_home(
        probe_home
    )
    preview = conda("init", "--dry-run", extra_env=probe_env).assert_ok()
    return require_init_plan(conda, sandbox_home, probe_home, require_init_targets(preview))


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
            if not any(is_same_path(path, profile) for profile in init_plan.profiles)
        )
    )
    for path in (*init_plan.profiles, *siblings):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PROFILE_SENTINEL)
    return siblings


@pytest.fixture
def installation_files(init_plan: InitPlan) -> dict[Path, bytes]:
    """Snapshot init targets inside the installation before a test invocation."""
    return {path: path.read_bytes() for path in init_plan.installation}
