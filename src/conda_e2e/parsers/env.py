# SPDX-License-Identifier: BSD-3-Clause
"""Parser for plain and JSON ``conda env list`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from conda_e2e.utils import is_same_path

if TYPE_CHECKING:
    from collections.abc import Iterator

    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class EnvRecord:
    """One environment reported by ``conda env list`` in either output mode."""

    name: str
    prefix: Path
    active: bool = False
    base: bool | None = None
    frozen: bool = False
    writable: bool | None = None
    created: str | None = None
    last_modified: str | None = None
    size: int | None = None


@dataclass(frozen=True, slots=True)
class EnvList:
    """The environments reported by ``conda env list`` in either output mode."""

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

    def get_by_prefix(self, prefix: Path | str) -> EnvRecord | None:
        """Return the environment with the matching prefix path, or ``None``."""
        return next((env for env in self.envs if is_same_path(env.prefix, prefix)), None)

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
    def from_stdout(cls, result: CommandResult) -> EnvList:
        """Build from default (human) ``conda env list`` output.

        Each non-comment line is ``<name> [markers] <prefix>``; the prefix is
        the last whitespace-separated token, and any markers between name and
        prefix flag the active (``*``) and frozen (``+``) environments.

        Plain output does not expose base, writable, or timestamp fields, and
        renders ``--size`` values as rounded text, so those fields are ``None``.
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
                    active=any("*" in marker for marker in markers),
                    frozen=any("+" in marker for marker in markers),
                )
            )
        return cls(tuple(envs))

    @classmethod
    def from_json(cls, result: CommandResult) -> EnvList:
        """Build from ``conda env list --json`` output.

        ``active`` / ``frozen`` default to ``False`` if ``envs_details`` (or an
        entry) is absent, e.g. on older conda. Other detail fields remain
        ``None`` when the source does not report them.
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
                    base=detail.get("base"),
                    frozen=detail.get("frozen", False),
                    writable=detail.get("writable"),
                    created=detail.get("created"),
                    last_modified=detail.get("last_modified"),
                    size=detail.get("size"),
                )
            )
        return cls(tuple(envs))
