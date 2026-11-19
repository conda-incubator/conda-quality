# SPDX-License-Identifier: BSD-3-Clause
"""Target planning and assertions for ``conda init`` E2E tests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from conda_e2e.parsers.info import CondaInfo
from conda_e2e.runner import CliRunner
from conda_e2e.shells import Shell
from conda_e2e.utils import is_same_path
from conda_e2e.windows_registry import is_registry_target

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from conda_e2e.result import CommandResult

STATUSES = ("no change", "modified", "needs sudo")
IGNORED_OUTPUT = ("==> DRY RUN:", "No action taken.")
PROFILE_SENTINEL = b"# CONDA_E2E_PROFILE_SENTINEL=preserved\n"
BASH_PROFILES = (".bashrc", ".bash_profile")


@dataclass(frozen=True, slots=True)
class InitPlan:
    """The destinations an ``init`` run reported, split by kind."""

    prefix: Path
    profiles: tuple[Path, ...]
    installation: tuple[Path, ...]
    registry: tuple[str, ...]


def require_init_targets(result: CommandResult) -> list[tuple[str, str]]:
    """Return the ``(status, target)`` pairs of an ``init`` run, rejecting other output."""
    targets = [
        (status, line[len(status) :].strip())
        for line in result.stdout.splitlines()
        if (status := next((status for status in STATUSES if line.startswith(f"{status} ")), None))
    ]
    unexpected = [
        line
        for line in result.stdout.splitlines()
        if line.strip()
        and not line.startswith(IGNORED_OUTPUT)
        and not any(line.startswith(f"{status} ") for status in STATUSES)
    ]
    assert not unexpected, f"Unrecognized init targets: {unexpected}"
    assert targets, f"Expected init to report its targets. Got:\n{result.stdout}"
    return targets


def _rebase_home(path: Path, probe_home: Path, home: Path) -> Path:
    """Map a target reported under the disposable probe home onto the sandbox home."""
    resolved = path.resolve()
    probe = probe_home.resolve()
    if resolved.is_relative_to(probe):
        return home / resolved.relative_to(probe)
    return path


def require_init_plan(
    conda: CliRunner, home: Path, probe_home: Path, targets: Sequence[tuple[str, str]]
) -> InitPlan:
    """Split the reported targets and refuse plans that are unsafe to exercise."""
    prefix = CondaInfo.from_json(conda("info", "--json").assert_ok()).root_prefix
    files = [
        (status, Path(target))
        for status, target in targets
        if target and not is_registry_target(target)
    ]
    profiles = tuple(
        _rebase_home(path, probe_home, home)
        for _, path in files
        if not path.resolve().is_relative_to(prefix.resolve())
    )
    installation = tuple(
        path for _, path in files if path.resolve().is_relative_to(prefix.resolve())
    )
    unresolved = [target for _, target in targets if not target]
    elevated = [target for status, target in targets if status == "needs sudo"]
    outside = [path for path in profiles if not path.resolve().is_relative_to(home.resolve())]
    # The suite runs against the conda installation it also tests with, so refuse to
    # rewrite it; a stale installation skips instead of being repaired.
    stale = [
        path
        for status, path in files
        if status == "modified" and path.resolve().is_relative_to(prefix.resolve())
    ]
    problems = []
    if not profiles:
        problems.append("no user profile was reported")
    if unresolved:
        problems.append("a step has no target path, so $PROFILE did not resolve")
    if elevated:
        problems.append(f"elevated access is required for {elevated}")
    if outside:
        problems.append(f"a profile is outside the sandbox HOME: {outside}")
    if stale:
        problems.append(f"the installation would be rewritten: {stale}")
    if problems:
        pytest.skip("conda init cannot run safely here: " + "; ".join(problems))
    registry = tuple(target for _, target in targets if is_registry_target(target))
    return InitPlan(prefix, profiles, installation, registry)


def _block_pattern(profile: Path) -> str:
    """Return the initialization-block pattern for the shell that owns ``profile``."""
    if profile.suffix == ".ps1":
        return r"#region conda initialize\r?\n(.*?)#endregion"
    return r"# >>> conda initialize >>>\n(.*?)\n# <<< conda initialize <<<"


def _hook_pattern(hook: str) -> str:
    """Return a pattern matching an active, uncommented ``conda shell.<hook> hook`` line."""
    return rf"(?m)^(?!\s*#).*shell\.{hook}['\"]?\s+['\"]?hook"


def powershell_for(profile: Path) -> Shell:
    """Return the PowerShell host that owns ``profile``."""
    return (
        Shell.WINDOWS_POWERSHELL if profile.parent.name == "WindowsPowerShell" else Shell.POWERSHELL
    )


def assert_initialized(profile: Path, hook: str, prefix: Path) -> None:
    """Require one preserved initialization block with an active hook for ``prefix``."""
    initialized = profile.read_text()
    assert initialized.startswith(PROFILE_SENTINEL.decode()), (
        f"Init must preserve the existing profile content. Got:\n{initialized}"
    )
    blocks = re.findall(_block_pattern(profile), initialized, re.DOTALL)
    assert len(blocks) == 1, (
        f"Expected exactly one ordered conda initialization block. Got:\n{initialized}"
    )
    assert re.search(_hook_pattern(hook), blocks[0]), (
        f"Expected an active {hook} hook inside the initialization block. Got:\n{blocks[0]}"
    )
    shell_path = prefix / ("condabin" if profile.suffix == ".ps1" else "bin")
    assert str(shell_path) in blocks[0], (
        f"Initialization block must reference the running conda {shell_path}. Got:\n{blocks[0]}"
    )


def assert_activates(
    conda: CliRunner, profile: Path, prefix: Path, shell: Shell, extra_env: Mapping[str, str]
) -> None:
    """Source ``profile`` and require the generated block to activate base."""
    if not shell.is_available():
        pytest.skip(f"{shell.value} is not available to source {profile}")
    if shell in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL):
        script = (
            f'. "{profile}"; if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}; '
            "conda activate base; if ($LASTEXITCODE) { exit $LASTEXITCODE }; "
            "$env:CONDA_PREFIX"
        )
    else:
        script = f'source "{profile}" && conda activate base && printf "%s" "$CONDA_PREFIX"'
    result = CliRunner(executable=shell.value, environ=conda.environ, cwd=conda.cwd).run(
        *shell.command_flags, script, extra_env=extra_env
    )
    result.assert_ok()
    assert is_same_path(result.stdout.strip(), prefix), (
        f"Sourcing {profile} must let `conda activate base` set CONDA_PREFIX. "
        f"Got: {result.stdout.strip()!r}"
    )
