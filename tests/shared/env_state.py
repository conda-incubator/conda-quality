# SPDX-License-Identifier: BSD-3-Clause
"""Setup helpers shared by ``conda info --envs`` and ``conda env list`` tests.

Pure setup, no assertions: kept out of ``env_list_asserts.py`` and unregistered
for pytest assert-rewriting, per the convention that only assertion-helper
modules need that registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def freeze_env(env_path: Path) -> None:
    """Mark an environment frozen by creating conda's ``conda-meta/frozen`` marker file.

    ``touch()`` raises on its own if it can't create the file, so its return
    is itself the success check; no follow-up existence assert is needed.
    """
    (env_path / "conda-meta" / "frozen").touch()
