# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for default ``conda init`` behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from init_asserts import (
    BASH_PROFILES,
    PROFILE_SENTINEL,
    assert_activates,
    assert_initialized,
    powershell_for,
    require_init_targets,
)

from conda_e2e.shells import Shell
from conda_e2e.utils import IS_WINDOWS
from conda_e2e.windows_registry import is_registry_target, read_value

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(362)
@pytest.mark.smoke
def test_init_initializes_default_profile(conda, init_plan, init_env, seeded_profiles):
    """Bare ``conda init`` writes one ordered block to the default profile.

    The run preserves existing profile content and leaves a sibling bash profile
    untouched. On Windows it also sets the cmd.exe ``AutoRun`` value, which the
    fixture restores afterwards.
    """
    if IS_WINDOWS:
        assert all(profile.suffix == ".ps1" for profile in init_plan.profiles), (
            f"Bare Windows init must target a PowerShell profile: {init_plan.profiles}"
        )
        assert init_plan.registry, (
            "Bare Windows init must report the cmd.exe AutoRun target. "
            f"Planned targets: {init_plan}"
        )
    else:
        assert {profile.name for profile in init_plan.profiles} <= set(BASH_PROFILES), (
            f"Bare POSIX init must target a bash profile: {init_plan.profiles}"
        )
    conda("init", extra_env=init_env).assert_ok()
    for sibling in seeded_profiles:
        assert sibling.read_bytes() == PROFILE_SENTINEL, (
            f"Init changed an unplanned profile: {sibling}"
        )
    for target in init_plan.registry:
        value = read_value(target)
        assert value is not None, f"Init must set the cmd.exe AutoRun value {target}"
        hook_path = str(init_plan.prefix / "condabin" / "conda_hook.bat")
        assert hook_path in str(value[0]), f"AutoRun must reference {hook_path}. Got: {value[0]!r}"
    hook = "powershell" if IS_WINDOWS else "bash"
    for profile in init_plan.profiles:
        assert_initialized(profile, hook, init_plan.prefix)


@pytest.mark.covers(362)
def test_init_profile_activates_base(conda, init_plan, init_env):
    """Sourcing the profile written by ``conda init`` activates base."""
    conda("init", extra_env=init_env).assert_ok()
    for profile in init_plan.profiles:
        shell = powershell_for(profile) if IS_WINDOWS else Shell.BASH
        assert_activates(conda, profile, init_plan.prefix, shell, init_env)


@pytest.mark.covers(362)
@pytest.mark.usefixtures("seeded_profiles")
def test_init_rerun_reports_no_change(conda, init_plan, init_env):
    """Repeating bare ``conda init`` reports no change and keeps a single block."""
    conda("init", extra_env=init_env).assert_ok()
    rerun = require_init_targets(conda("init", extra_env=init_env).assert_ok())
    statuses = {
        Path(target).resolve(): status for status, target in rerun if not is_registry_target(target)
    }
    assert set(statuses.values()) == {"no change"}, (
        f"A repeated init must report no change for every target. Got: {rerun}"
    )
    hook = "powershell" if IS_WINDOWS else "bash"
    for profile in init_plan.profiles:
        assert statuses.get(profile.resolve()) == "no change", (
            f"A repeated init must report no change for {profile}. Got: {rerun}"
        )
        assert_initialized(profile, hook, init_plan.prefix)


@pytest.mark.covers(370)
def test_init_dry_run_reports_changes_without_writing(
    conda, init_plan, init_env, seeded_profiles, installation_files, init_state_guard
):
    """``conda init --dry-run`` reports the changes it would make and writes nothing."""
    assert installation_files, (
        f"Expected init to report installation targets. Planned targets: {init_plan}"
    )
    result = conda("init", "--dry-run", extra_env=init_env).assert_ok()
    assert any(line.startswith("==> DRY RUN:") for line in result.stdout.splitlines()), (
        f"Expected a dry-run notice. Got:\n{result.stdout}"
    )
    targets = require_init_targets(result)
    modified = {
        Path(target).resolve()
        for status, target in targets
        if status == "modified" and not is_registry_target(target)
    }
    assert modified == {profile.resolve() for profile in init_plan.profiles}, (
        f"Dry run must report every profile it would modify. Reported: {targets}"
    )
    for path in (*init_plan.profiles, *seeded_profiles):
        assert path.read_bytes() == PROFILE_SENTINEL, f"A dry run changed {path}"
    for path, before in installation_files.items():
        assert path.read_bytes() == before, f"A dry run changed {path}"
    for target in init_plan.registry:
        assert read_value(target) == init_state_guard, (
            f"A dry run changed the registry value {target}"
        )
