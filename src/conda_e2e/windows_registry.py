# SPDX-License-Identifier: BSD-3-Clause
"""Read, lock, and restore the Windows registry values ``conda init`` reports as targets.

Bare ``conda init`` writes the cmd.exe ``AutoRun`` value in the real user
registry, not the sandbox, so callers snapshot and restore it around a run.
These helpers are only usable on Windows.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock

from conda_e2e.utils import IS_WINDOWS

if IS_WINDOWS:
    import winreg


if TYPE_CHECKING:
    from collections.abc import Iterator

REGISTRY_TARGET_PREFIX = "HKEY_"
CMD_AUTORUN_TARGET = r"HKEY_CURRENT_USER\Software\Microsoft\Command Processor\AutoRun"
_AUTORUN_KEY = r"Software\Microsoft\Command Processor"
_AUTORUN_LOCK_FILENAME = "conda-e2e-user-autorun.lock"


@contextlib.contextmanager
def preserve_autorun() -> Iterator[tuple[object, int] | None]:
    """Serialize, snapshot, and restore the current user's AutoRun value."""
    if not IS_WINDOWS:
        yield None
        return

    lock_path = Path(tempfile.gettempdir()) / _AUTORUN_LOCK_FILENAME
    with FileLock(lock_path, timeout=120):
        value = read_autorun()
        try:
            yield value
        finally:
            if read_autorun() != value:
                restore_autorun(value)


def is_registry_target(target: str) -> bool:
    """Return whether an ``init`` target is a Windows registry value rather than a path."""
    return target.startswith(REGISTRY_TARGET_PREFIX)


def read_autorun() -> tuple[object, int] | None:
    """Return the AutoRun value and type, or ``None`` when absent."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTORUN_KEY, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return None
    try:
        return winreg.QueryValueEx(key, "AutoRun")
    except FileNotFoundError:
        return None
    finally:
        winreg.CloseKey(key)


def restore_autorun(value: tuple[object, int] | None) -> None:
    """Restore the original AutoRun value, or delete it if it was absent.

    This intentionally does not delete the parent key even if conda init created
    it: another process may have added values since the snapshot, and deleting
    the key would destroy them. Leaving an empty key is harmless.
    """
    if value is None:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTORUN_KEY, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            return
        try:
            winreg.DeleteValue(key, "AutoRun")
        except FileNotFoundError:
            pass
        finally:
            winreg.CloseKey(key)
        return
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _AUTORUN_KEY)
    try:
        winreg.SetValueEx(key, "AutoRun", 0, value[1], value[0])
    finally:
        winreg.CloseKey(key)
