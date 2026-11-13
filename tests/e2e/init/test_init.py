# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for default ``conda init`` behavior."""

from __future__ import annotations

import contextlib
import hashlib
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from conda_e2e.runner import CliRunner
from conda_e2e.shells import Shell
from conda_e2e.utils import IS_WINDOWS, is_same_path

if IS_WINDOWS:
    import winreg

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from conda_e2e.result import CommandResult

STATUSES = ("no change", "modified", "needs sudo")
IGNORED_OUTPUT = ("==> DRY RUN:", "No action taken.")
REGISTRY_PREFIX = "HKEY_"
PROFILE_SENTINEL = b"# CONDA_E2E_PROFILE_SENTINEL=preserved\n"
BASH_PROFILES = (".bashrc", ".bash_profile")


@dataclass(frozen=True)
class _InitPlan:
    """The destinations an ``init`` run reported, split by kind."""

    prefix: Path
    profiles: tuple[Path, ...]
    installation: tuple[Path, ...]
    registry: tuple[str, ...]


@dataclass(frozen=True)
class _Snapshot:
    """Pre-test content of every path an ``init`` run may touch."""

    profiles: dict[Path, bytes | None]
    installation: dict[Path, bytes | None]
    registry: dict[str, tuple[object, int] | None]


def _sandbox_home(environ: Mapping[str, str]) -> Path:
    """Return the sandboxed home directory from the isolated environment."""
    return Path(environ.get("HOME") or environ["USERPROFILE"])


def _prepare_windows_home(home: Path) -> dict[str, str]:
    """Seed the sandbox Documents folder and point PowerShell's home lookup at it.

    PowerShell resolves ``$PROFILE`` from the home and Documents folders; without
    them a host reports an empty profile path and ``conda init`` has nothing to write.
    """
    if not IS_WINDOWS:
        return {}
    for relative in ("Documents", "Documents/WindowsPowerShell", "Documents/PowerShell"):
        (home / relative).mkdir(parents=True, exist_ok=True)
    drive = home.drive
    return {"HOMEDRIVE": drive, "HOMEPATH": str(home)[len(drive) :]} if drive else {}


def _require_init_targets(result: CommandResult) -> list[tuple[str, str]]:
    """Return the ``(status, target)`` pairs of an ``init`` preview, rejecting other output."""
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
    assert not unexpected, f"Unrecognized init preview targets: {unexpected}"
    assert targets, f"Expected init to report its targets. Got:\n{result.stdout}"
    return targets


def _init_plan(conda, home: Path, targets: Sequence[tuple[str, str]]) -> _InitPlan:
    """Split the reported targets and refuse plans that are unsafe to exercise."""
    prefix = Path(conda("info", "--base").assert_ok().stdout.strip())
    files = [
        (status, Path(target))
        for status, target in targets
        if target and not _is_registry_target(target)
    ]
    profiles = tuple(
        path for _, path in files if not path.resolve().is_relative_to(prefix.resolve())
    )
    installation = tuple(
        path for _, path in files if path.resolve().is_relative_to(prefix.resolve())
    )
    unresolved = [target for status, target in targets if not target]
    elevated = [target for status, target in targets if status == "needs sudo"]
    outside = [path for path in profiles if not path.resolve().is_relative_to(home.resolve())]
    # The suite runs against the conda installation it also tests with, so refuse to
    # rewrite it; a stale installation skips instead of being repaired and restored.
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
    registry = tuple(target for _, target in targets if _is_registry_target(target))
    return _InitPlan(prefix, profiles, installation, registry)


def _read_optional(path: Path) -> bytes | None:
    """Return the file's bytes, or ``None`` when it does not exist."""
    return path.read_bytes() if path.exists() else None


def _block_pattern(profile: Path) -> str:
    """Return the initialization-block pattern for the shell that owns ``profile``."""
    if profile.suffix == ".ps1":
        return r"#region conda initialize\r?\n(.*?)#endregion"
    return r"# >>> conda initialize >>>\n(.*?)\n# <<< conda initialize <<<"


def _hook_pattern(hook: str) -> str:
    """Return a pattern matching an active, uncommented ``conda shell.<hook> hook`` line."""
    return rf"(?m)^(?!\s*#).*shell\.{hook}['\"]?\s+['\"]?hook"


def _powershell_for(profile: Path) -> Shell:
    """Return the PowerShell host that owns ``profile``."""
    return (
        Shell.WINDOWS_POWERSHELL if profile.parent.name == "WindowsPowerShell" else Shell.POWERSHELL
    )


@contextlib.contextmanager
def _exclusive_init_lock(prefix: Path) -> Iterator[None]:
    """Serialize ``conda init`` runs across processes, which share installation state."""
    digest = hashlib.sha256(str(prefix).encode()).hexdigest()[:12]
    path = Path(tempfile.gettempdir()) / f"conda-e2e-init-{digest}.lock"
    with path.open("w") as handle:
        handle.write("0")
        handle.flush()
        handle.seek(0)
        if IS_WINDOWS:
            import msvcrt

            # msvcrt has no blocking lock; retry until the other worker finishes.
            deadline = time.monotonic() + 600
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


@contextlib.contextmanager
def _seeded(plan: _InitPlan, extra: tuple[Path, ...] = ()) -> Iterator[_Snapshot]:
    """Seed the sentinel into every profile, then restore all touched state on exit."""
    with _exclusive_init_lock(plan.prefix):
        snapshot = _Snapshot(
            profiles={path: _read_optional(path) for path in (*plan.profiles, *extra)},
            installation={path: _read_optional(path) for path in plan.installation},
            registry={target: _read_registry(target) for target in plan.registry},
        )
        registry_keys = {target: _registry_key_exists(target) for target in plan.registry}
        try:
            for path in snapshot.profiles:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(PROFILE_SENTINEL)
            yield snapshot
        finally:
            for path, content in snapshot.profiles.items():
                if content is None:
                    path.unlink(missing_ok=True)
                elif path.read_bytes() != content:
                    path.write_bytes(content)
            for path, content in snapshot.installation.items():
                if content is None:
                    path.unlink(missing_ok=True)
                elif path.read_bytes() != content:
                    path.write_bytes(content)
            for target, value in snapshot.registry.items():
                if _read_registry(target) != value:
                    _restore_registry(target, value, registry_keys[target])


def _assert_initialized(profile: Path, hook: str, prefix: Path) -> None:
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
    assert str(prefix) in blocks[0], (
        f"Initialization block must reference the running conda prefix {prefix}. Got:\n{blocks[0]}"
    )


def _assert_activates(
    conda, profile: Path, prefix: Path, shell: Shell, extra_env: Mapping[str, str]
) -> None:
    """Source ``profile`` and require the generated block to activate base."""
    if not shell.is_available():
        pytest.skip(f"{shell.value} is not available to source {profile}")
    if shell is Shell.CMD:
        raise AssertionError("cmd.exe has no profile to source")
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


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(362)
@pytest.mark.smoke
def test_init_initializes_default_profile(conda, isolated_env_vars):
    """Bare ``conda init`` initializes the sandbox profile for the default shells.

    The preview also names the shell-integration files inside the conda
    installation and, on Windows, the cmd.exe ``AutoRun`` registry value. The
    test restores everything the run touches, so the conda under test and the
    host are left as they were found. It skips rather than rewrite an
    installation whose own shell files are out of date.
    """
    home = _sandbox_home(isolated_env_vars)
    home_env = _prepare_windows_home(home)
    preview = conda("init", "--dry-run", extra_env=home_env).assert_ok()
    plan = _init_plan(conda, home, _require_init_targets(preview))
    if IS_WINDOWS:
        assert all(profile.suffix == ".ps1" for profile in plan.profiles), (
            f"Bare Windows init must target a PowerShell profile: {plan.profiles}"
        )
    else:
        assert {profile.name for profile in plan.profiles} <= set(BASH_PROFILES), (
            f"Bare POSIX init must target a bash profile: {plan.profiles}"
        )
    siblings = (
        ()
        if IS_WINDOWS
        else tuple(
            path
            for path in (home / name for name in BASH_PROFILES)
            if not any(is_same_path(path, profile) for profile in plan.profiles)
        )
    )

    with _seeded(plan, siblings) as snapshot:
        targets = _require_init_targets(conda("init", "--dry-run", extra_env=home_env).assert_ok())
        for path in snapshot.profiles:
            assert path.read_bytes() == PROFILE_SENTINEL, f"A repeated dry run changed {path}"
        for path, content in snapshot.installation.items():
            assert _read_optional(path) == content, f"A repeated dry run changed {path}"
        for target, value in snapshot.registry.items():
            assert _read_registry(target) == value, f"A repeated dry run changed {target}"

        modified = {Path(target).resolve() for status, target in targets if status == "modified"}
        assert modified & {profile.resolve() for profile in plan.profiles} == {
            profile.resolve() for profile in plan.profiles
        }, f"Init must report every profile it modifies. Planned targets: {targets}"

        conda("init", extra_env=home_env).assert_ok()
        for sibling in siblings:
            assert sibling.read_bytes() == PROFILE_SENTINEL, (
                f"Init changed an unplanned profile: {sibling}"
            )
        for target in plan.registry:
            value = _read_registry(target)
            assert value is not None, f"Init must set the cmd.exe AutoRun value {target}"
            hook_path = str(plan.prefix / "condabin" / "conda_hook.bat")
            assert hook_path in str(value[0]), (
                f"AutoRun must reference {hook_path}. Got: {value[0]!r}"
            )
        shell = _powershell_for(plan.profiles[0]) if IS_WINDOWS else Shell.BASH
        hook = "powershell" if IS_WINDOWS else "bash"
        for profile in plan.profiles:
            _assert_initialized(profile, hook, plan.prefix)
            _assert_activates(conda, profile, plan.prefix, shell, home_env)

        rerun = _require_init_targets(conda("init", extra_env=home_env).assert_ok())
        statuses = {
            Path(target).resolve(): status
            for status, target in rerun
            if not _is_registry_target(target)
        }
        for profile in plan.profiles:
            assert statuses.get(profile.resolve()) == "no change", (
                f"A repeated init must report no change for {profile}. Got: {rerun}"
            )
            _assert_initialized(profile, hook, plan.prefix)


# =============================================================================
# Windows registry backup and restore
# =============================================================================


def _is_registry_target(target: str) -> bool:
    """Return whether an ``init`` target is a Windows registry value rather than a path."""
    return target.startswith(REGISTRY_PREFIX)


def _split_registry_target(target: str) -> tuple[int, str, str]:
    """Split a full registry value path into its key root, subkey, and value name."""
    root, rest = target.split("\\", 1)
    subkey, value_name = rest.rsplit("\\", 1)
    return getattr(winreg, root), subkey, value_name


def _read_registry(target: str) -> tuple[object, int] | None:
    """Return the value and type stored at ``target``, or ``None`` when absent."""
    root, subkey, value_name = _split_registry_target(target)
    try:
        key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return None
    try:
        return winreg.QueryValueEx(key, value_name)
    except FileNotFoundError:
        return None
    finally:
        winreg.CloseKey(key)


def _registry_key_exists(target: str) -> bool:
    """Return whether the registry key that holds ``target`` exists."""
    root, subkey, _ = _split_registry_target(target)
    try:
        key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return False
    winreg.CloseKey(key)
    return True


def _restore_registry(target: str, value: tuple[object, int] | None, key_existed: bool) -> None:
    """Put the original value back at ``target``, dropping a value or key ``init`` created."""
    root, subkey, value_name = _split_registry_target(target)
    if value is None:
        try:
            key = winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            return
        try:
            winreg.DeleteValue(key, value_name)
        except FileNotFoundError:
            pass
        finally:
            winreg.CloseKey(key)
        if not key_existed:
            with contextlib.suppress(OSError):
                winreg.DeleteKey(root, subkey)
        return
    key = winreg.CreateKey(root, subkey)
    try:
        winreg.SetValueEx(key, value_name, 0, value[1], value[0])
    finally:
        winreg.CloseKey(key)
