# SPDX-License-Identifier: BSD-3-Clause
"""Read, lock, and restore the Windows registry values ``conda init`` reports as targets.

Bare ``conda init`` writes the cmd.exe ``AutoRun`` value in the real user
registry, not the sandbox, so callers snapshot and restore it around a run.
These helpers are only usable on Windows.
"""

from __future__ import annotations

import contextlib
import errno
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from conda_e2e.utils import IS_WINDOWS

if IS_WINDOWS:
    import msvcrt
    import winreg


if TYPE_CHECKING:
    from collections.abc import Iterator

REGISTRY_TARGET_PREFIX = "HKEY_"
CMD_AUTORUN_TARGET = r"HKEY_CURRENT_USER\Software\Microsoft\Command Processor\AutoRun"
_AUTORUN_LOCK_FILENAME = "conda-e2e-user-autorun.lock"
_LOCK_CONTENTION_ERRNOS = {errno.EACCES, errno.EAGAIN, errno.EDEADLK}


@contextlib.contextmanager
def preserve_autorun() -> Iterator[tuple[object, int] | None]:
    """Serialize, snapshot, and restore the current user's AutoRun value."""
    if not IS_WINDOWS:
        yield None
        return

    lock_path = Path(tempfile.gettempdir()) / _AUTORUN_LOCK_FILENAME
    with lock_path.open("a+b") as lock_file:
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()

        deadline = time.monotonic() + 120
        while True:
            lock_file.seek(0)
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                if exc.errno not in _LOCK_CONTENTION_ERRNOS:
                    raise
                if time.monotonic() >= deadline:
                    message = f"Timed out waiting for the AutoRun lock at {lock_path}"
                    raise TimeoutError(message) from exc
                time.sleep(0.1)
            else:
                break

        try:
            value = read_value(CMD_AUTORUN_TARGET)
            try:
                yield value
            finally:
                if read_value(CMD_AUTORUN_TARGET) != value:
                    restore_value(CMD_AUTORUN_TARGET, value)
        finally:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def is_registry_target(target: str) -> bool:
    """Return whether an ``init`` target is a Windows registry value rather than a path."""
    return target.startswith(REGISTRY_TARGET_PREFIX)


def _split_target(target: str) -> tuple[int, str, str]:
    """Split a full registry value path into its key root, subkey, and value name."""
    root, rest = target.split("\\", 1)
    subkey, value_name = rest.rsplit("\\", 1)
    return getattr(winreg, root), subkey, value_name


def read_value(target: str) -> tuple[object, int] | None:
    """Return the value and type stored at ``target``, or ``None`` when absent."""
    root, subkey, value_name = _split_target(target)
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


def restore_value(target: str, value: tuple[object, int] | None) -> None:
    """Restore the original value at ``target``, or delete it if it was absent.

    This intentionally does not delete the parent key even if conda init created
    it: another process may have added values since the snapshot, and deleting
    the key would destroy them. Leaving an empty key is harmless.
    """
    root, subkey, value_name = _split_target(target)
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
        return
    key = winreg.CreateKey(root, subkey)
    try:
        winreg.SetValueEx(key, value_name, 0, value[1], value[0])
    finally:
        winreg.CloseKey(key)
