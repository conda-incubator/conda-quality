# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda env list`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class EnvList:
    """The environments reported by ``conda env list``."""

    prefixes: tuple[Path, ...]

    @property
    def names(self) -> tuple[str, ...]:
        """The name of each environment prefix."""
        return tuple(p.name for p in self.prefixes)

    def __contains__(self, prefix: Path | str) -> bool:
        """Return whether ``prefix`` is in the list.

        Both sides are resolved with :meth:`~pathlib.Path.resolve` before
        comparing, so symlinks and other path aliases match.
        """
        target = Path(prefix).resolve()
        return any(p.resolve() == target for p in self.prefixes)


def parse_env_list_json(result: CommandResult) -> EnvList:
    """Parse ``conda env list --json`` output into an :class:`EnvList`."""
    return EnvList(tuple(Path(p) for p in result.json()["envs"]))


def parse_env_list_stdout(result: CommandResult) -> EnvList:
    """Parse the default (human) ``conda env list`` output.

    Each non-comment line is ``<name> [*] <prefix>``. The prefix is the last
    whitespace-separated token.
    """
    prefixes = [
        Path(stripped.split()[-1])
        for line in result.stdout.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]
    return EnvList(tuple(prefixes))
