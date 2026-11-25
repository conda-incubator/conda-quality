# SPDX-License-Identifier: BSD-3-Clause
"""Target planning and assertions for ``conda init`` E2E tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from conda_e2e.runner import CliRunner
from conda_e2e.shells import Shell
from conda_e2e.utils import IS_WINDOWS, is_same_path
from conda_e2e.windows_registry import CMD_AUTORUN_TARGET, is_registry_target

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

PROFILE_SENTINEL = b"# CONDA_E2E_PROFILE_SENTINEL=preserved\n"
BASH_PROFILES = (".bashrc", ".bash_profile")


@dataclass(frozen=True, slots=True)
class InitPlan:
    """The destinations an ``init`` run reported, split by kind."""

    prefix: Path
    profiles: Mapping[Shell, Path]
    installation: tuple[Path, ...]
    registry: tuple[str, ...]


def require_init_plan(
    prefix: Path,
    home: Path,
    expected_profiles: Mapping[Shell, Path],
    targets: Sequence[tuple[str, str]],
) -> InitPlan:
    """Split the reported targets and refuse plans that are unsafe to exercise."""
    files = [
        (status, Path(target))
        for status, target in targets
        if target and not is_registry_target(target)
    ]
    profiles = tuple(
        path for _, path in files if not path.resolve().is_relative_to(prefix.resolve())
    )
    installation = tuple(
        path for _, path in files if path.resolve().is_relative_to(prefix.resolve())
    )
    unresolved = [target for _, target in targets if not target]
    elevated = [target for status, target in targets if status == "needs sudo"]
    outside = [path for path in profiles if not path.resolve().is_relative_to(home.resolve())]
    # Refuse to rewrite the conda installation used by the suite.
    stale = [
        path
        for status, path in files
        if status == "modified" and path.resolve().is_relative_to(prefix.resolve())
    ]
    problems = []
    if len(profiles) != len(expected_profiles) or any(
        not any(is_same_path(path, expected) for path in profiles)
        for expected in expected_profiles.values()
    ):
        problems.append(
            f"unexpected profiles: {profiles}; expected {tuple(expected_profiles.values())}"
        )
    if unresolved:
        problems.append("a step has no target path, so $PROFILE did not resolve")
    if elevated:
        problems.append(f"elevated access is required for {elevated}")
    if outside:
        problems.append(f"a profile is outside the sandbox HOME: {outside}")
    if stale:
        problems.append(f"the installation would be rewritten: {stale}")
    registry = tuple(target for _, target in targets if is_registry_target(target))
    expected_registry = (CMD_AUTORUN_TARGET,) if IS_WINDOWS else ()
    if registry != expected_registry:
        problems.append(f"unexpected registry targets: {registry}; expected {expected_registry}")
    if problems:
        pytest.fail("conda init cannot run safely here: " + "; ".join(problems))
    return InitPlan(prefix, expected_profiles, installation, registry)


def assert_activates(conda: CliRunner, profile: Path, prefix: Path, shell: Shell) -> None:
    """Source ``profile`` and require the generated block to activate base."""
    if not shell.is_available():
        pytest.skip(f"{shell.value} is not available to source {profile}")
    if shell in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL):
        source = f'. "{profile}"; if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}; '
        display_prefix = "$env:CONDA_PREFIX"
    else:
        source = f'source "{profile}" && '
        display_prefix = 'printf "%s" "$CONDA_PREFIX"'
    script = source + shell.activate_script("base", display_prefix)
    result = CliRunner(executable=shell.value, environ=conda.environ, cwd=conda.cwd).run(
        *shell.command_flags, script
    )
    result.assert_ok()
    assert is_same_path(result.stdout.strip(), prefix), (
        f"Sourcing {profile} must let `conda activate base` set CONDA_PREFIX. "
        f"Got: {result.stdout.strip()!r}"
    )
