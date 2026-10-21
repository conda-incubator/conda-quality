# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda search`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class SearchRecord:
    """One package record returned by ``conda search --json``."""

    name: str
    version: str
    channel: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchRecord:
        """Build from one JSON package record."""
        return cls(name=data["name"], version=data["version"], channel=data["channel"])


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Package records grouped by name from ``conda search --json``."""

    packages: dict[str, tuple[SearchRecord, ...]]

    def get(self, name: str) -> tuple[SearchRecord, ...]:
        """Return records for ``name``, or an empty tuple when absent."""
        return self.packages.get(name, ())

    @classmethod
    def from_json(cls, result: CommandResult) -> SearchResult:
        """Build from ``conda search --json`` output."""
        return cls(
            packages={
                name: tuple(SearchRecord.from_dict(record) for record in records)
                for name, records in result.json().items()
            }
        )


@dataclass(frozen=True, slots=True)
class SearchEnvironment:
    """An installed environment and matching package records from ``--envs --json``."""

    location: Path
    packages: tuple[SearchRecord, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchEnvironment:
        """Build from one environment entry in ``conda search --envs --json``."""
        return cls(
            location=Path(data["location"]),
            packages=tuple(SearchRecord.from_dict(record) for record in data["package_records"]),
        )


@dataclass(frozen=True, slots=True)
class SearchEnvironments:
    """Environments containing a package from ``conda search --envs --json``."""

    environments: tuple[SearchEnvironment, ...]

    @classmethod
    def from_json(cls, result: CommandResult) -> SearchEnvironments:
        """Build from ``conda search --envs --json`` output."""
        return cls(tuple(SearchEnvironment.from_dict(item) for item in result.json()))
