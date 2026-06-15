# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda list`` output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class PackageRecord:
    """One installed package as reported by ``conda list``."""

    name: str
    version: str
    build: str = ""
    channel: str = ""


@dataclass(frozen=True, slots=True)
class PackageList:
    """The packages reported by ``conda list``."""

    records: tuple[PackageRecord, ...]

    @property
    def names(self) -> tuple[str, ...]:
        """The package names, in report order."""
        return tuple(r.name for r in self.records)

    def __contains__(self, name: str) -> bool:
        """Support ``"python" in package_list``."""
        return name in self.names

    def get(self, name: str) -> PackageRecord | None:
        """Return the record for ``name``, or ``None`` if not installed."""
        return next((r for r in self.records if r.name == name), None)


def parse_list_json(result: CommandResult) -> PackageList:
    """Parse ``conda list --json`` output into a :class:`PackageList`."""
    return PackageList(
        tuple(
            PackageRecord(
                name=rec["name"],
                version=rec["version"],
                build=rec.get("build_string") or rec.get("build") or "",
                channel=rec.get("channel", ""),
            )
            for rec in result.json()
        )
    )


def parse_list_stdout(result: CommandResult) -> PackageList:
    """Parse the default (human) ``conda list`` output.

    Each non-comment line is ``Name  Version  Build  [Channel]`` split on
    whitespace; ``Channel`` is empty when conda omits it.
    """
    records = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        records.append(
            PackageRecord(
                name=parts[0],
                version=parts[1] if len(parts) > 1 else "",
                build=parts[2] if len(parts) > 2 else "",
                channel=parts[3] if len(parts) > 3 else "",
            )
        )
    return PackageList(tuple(records))
