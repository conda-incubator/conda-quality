# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda env list`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class EnvRecord:
    """One environment reported by ``conda env list``."""

    name: str
    prefix: Path
    active: bool = False
    frozen: bool = False


@dataclass(frozen=True, slots=True)
class EnvList:
    """The environments reported by ``conda env list``."""

    envs: tuple[EnvRecord, ...]

    @property
    def prefixes(self) -> tuple[Path, ...]:
        """The prefix path of each environment, in report order."""
        return tuple(env.prefix for env in self.envs)

    @property
    def names(self) -> tuple[str, ...]:
        """The reported name of each environment (e.g. ``base``)."""
        return tuple(env.name for env in self.envs)

    @property
    def active_env(self) -> EnvRecord | None:
        """The active environment, or ``None`` if none is marked active."""
        return next((env for env in self.envs if env.active), None)

    def get(self, name: str) -> EnvRecord | None:
        """Return the environment named ``name`` (first match), or ``None``."""
        return next((env for env in self.envs if env.name == name), None)

    def __contains__(self, name: object) -> bool:
        """Support ``"base" in env_list`` membership tests by name."""
        return any(env.name == name for env in self.envs)

    def __iter__(self) -> Iterator[EnvRecord]:
        """Iterate over the environment records."""
        return iter(self.envs)

    def __len__(self) -> int:
        """Return the number of environments."""
        return len(self.envs)

    @classmethod
    def from_json(cls, result: CommandResult) -> EnvList:
        """Build from ``conda env list --json`` output.

        ``active`` / ``frozen`` come from the ``envs_details`` map; both default
        to ``False`` if it (or an entry) is absent, e.g. on older conda.
        """
        data = result.json()
        details = data.get("envs_details", {})
        envs = []
        for prefix in data["envs"]:
            detail = details.get(prefix, {})
            envs.append(
                EnvRecord(
                    name=detail.get("name", Path(prefix).name),
                    prefix=Path(prefix),
                    active=detail.get("active", False),
                    frozen=detail.get("frozen", False),
                )
            )
        return cls(tuple(envs))

    @classmethod
    def from_stdout(cls, result: CommandResult) -> EnvList:
        """Build from the default (human) ``conda env list`` output.

        Each non-comment line is ``<name> [markers] <prefix>``; the prefix is
        the last whitespace-separated token, and any markers between name and
        prefix flag the active (``*``) and frozen (``+``) environments.
        """
        envs = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            markers = parts[1:-1]
            envs.append(
                EnvRecord(
                    name=parts[0],
                    prefix=Path(parts[-1]),
                    active=any("*" in m for m in markers),
                    frozen=any("+" in m for m in markers),
                )
            )
        return cls(tuple(envs))
