# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda search`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


def _table_rows(result: CommandResult, columns: tuple[str, ...]) -> list[list[str]]:
    """Read rows below a search table header, retaining spaces in the final location."""
    lines = result.stdout.splitlines()
    header = next(
        (index for index, line in enumerate(lines) if line.split() == ["#", *columns]),
        None,
    )
    if header is None:
        raise ValueError(f"Missing conda search table header: {' '.join(columns)}")
    rows = []
    for line in lines[header + 1 :]:
        if not line.strip():
            continue
        fields = line.rstrip().split(maxsplit=len(columns) - 1)
        if len(fields) != len(columns):
            raise ValueError(f"Malformed conda search row: {line!r}")
        rows.append(fields)
    return rows


@dataclass(frozen=True, slots=True)
class SearchRecord:
    """One package record returned by ``conda search``."""

    name: str
    version: str
    build: str
    channel: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchRecord:
        """Build from one JSON package record."""
        return cls(
            name=data["name"], version=data["version"], build=data["build"], channel=data["channel"]
        )


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Package records grouped by name from ``conda search``."""

    packages: dict[str, tuple[SearchRecord, ...]]

    def get(self, name: str) -> tuple[SearchRecord, ...]:
        """Return records for ``name``, or an empty tuple when absent."""
        return self.packages.get(name, ())

    @classmethod
    def from_stdout(cls, result: CommandResult) -> SearchResult:
        """Build from the plain ``Name Version Build Channel`` table."""
        packages: dict[str, list[SearchRecord]] = {}
        for name, version, build, channel in _table_rows(
            result, ("Name", "Version", "Build", "Channel")
        ):
            packages.setdefault(name, []).append(SearchRecord(name, version, build, channel))
        return cls({name: tuple(records) for name, records in packages.items()})

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
    """An installed environment and matching package records from ``--envs``."""

    location: Path
    packages: tuple[SearchRecord, ...]


@dataclass(frozen=True, slots=True)
class SearchEnvironmentsResult:
    """Environments containing a package from ``conda search --envs``."""

    environments: tuple[SearchEnvironment, ...]

    @classmethod
    def from_stdout(cls, result: CommandResult) -> SearchEnvironmentsResult:
        """Group plain search records by their complete ``Location`` column."""
        environments: dict[Path, list[SearchRecord]] = {}
        for name, version, build, channel, location in _table_rows(
            result, ("Name", "Version", "Build", "Channel", "Location")
        ):
            environments.setdefault(Path(location), []).append(
                SearchRecord(name, version, build, channel)
            )
        return cls(
            tuple(
                SearchEnvironment(location, tuple(records))
                for location, records in environments.items()
            )
        )
