# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for default ``conda init`` behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from init_asserts import (
    PROFILE_SENTINEL,
    assert_activates,
)

from conda_e2e.parsers.init import InitResult
from conda_e2e.shells import Shell
from conda_e2e.utils import IS_WINDOWS
from conda_e2e.windows_registry import is_registry_target, read_autorun

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(362)
@pytest.mark.smoke
def test_init_initializes_default_profile(conda, init_plan, seeded_profiles):
    """Bare ``conda init`` updates the default profile.

    The run preserves existing profile content and leaves a sibling bash profile
    untouched. On Windows it also sets the cmd.exe ``AutoRun`` value, which the
    fixture restores afterwards.
    """
    conda("init").assert_ok()
    for sibling in seeded_profiles:
        assert sibling.read_bytes() == PROFILE_SENTINEL, (
            f"Init changed an unplanned profile: {sibling}"
        )
    for target in init_plan.registry:
        value = read_autorun()
        assert value is not None, f"Init must set the cmd.exe AutoRun value {target}"
        hook_path = str(init_plan.prefix / "condabin" / "conda_hook.bat")
        assert hook_path in str(value[0]), f"AutoRun must reference {hook_path}. Got: {value[0]!r}"
    for profile in init_plan.profiles.values():
        content = profile.read_bytes()
        assert content.startswith(PROFILE_SENTINEL), f"Init did not preserve {profile}"
        assert content != PROFILE_SENTINEL, f"Init did not update {profile}"


@pytest.mark.covers(362)
@pytest.mark.parametrize(
    "shell", (Shell.WINDOWS_POWERSHELL, Shell.POWERSHELL) if IS_WINDOWS else (Shell.BASH,)
)
def test_init_profile_activates_base(conda, init_plan, shell):
    """Sourcing the profile written by ``conda init`` activates base."""
    conda("init").assert_ok()
    assert_activates(conda, init_plan.profiles[shell], init_plan.prefix, shell)


@pytest.mark.covers(362)
@pytest.mark.usefixtures("seeded_profiles")
def test_init_rerun_reports_no_change(conda, init_plan):
    """Repeating bare ``conda init`` reports no change and preserves profile bytes."""
    conda("init").assert_ok()
    before = {profile: profile.read_bytes() for profile in init_plan.profiles.values()}
    rerun = InitResult.from_stdout(conda("init").assert_ok()).targets
    statuses = {
        Path(target).resolve(): status for status, target in rerun if not is_registry_target(target)
    }
    assert set(statuses.values()) == {"no change"}, (
        f"A repeated init must report no change for every target. Got: {rerun}"
    )
    for profile in init_plan.profiles.values():
        assert statuses.get(profile.resolve()) == "no change", (
            f"A repeated init must report no change for {profile}. Got: {rerun}"
        )
        assert profile.read_bytes() == before[profile], f"Rerunning init changed {profile}"


@pytest.mark.covers(370)
def test_init_dry_run_reports_changes_without_writing(
    conda, init_plan, seeded_profiles, installation_files, init_state_guard
):
    """``conda init --dry-run`` reports the changes it would make and writes nothing."""
    assert installation_files, (
        f"Expected init to report installation targets. Planned targets: {init_plan}"
    )
    result = conda("init", "--dry-run").assert_ok()
    assert any(line.startswith("==> DRY RUN:") for line in result.stdout.splitlines()), (
        f"Expected a dry-run notice. Got:\n{result.stdout}"
    )
    targets = InitResult.from_stdout(result).targets
    modified = {
        Path(target).resolve()
        for status, target in targets
        if status == "modified" and not is_registry_target(target)
    }
    assert modified == {profile.resolve() for profile in init_plan.profiles.values()}, (
        f"Dry run must report every profile it would modify. Reported: {targets}"
    )
    for path in (*init_plan.profiles.values(), *seeded_profiles):
        assert path.read_bytes() == PROFILE_SENTINEL, f"A dry run changed {path}"
    for path, before in installation_files.items():
        assert path.read_bytes() == before, f"A dry run changed {path}"
    for target in init_plan.registry:
        assert read_autorun() == init_state_guard, f"A dry run changed the registry value {target}"
