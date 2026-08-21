# SPDX-License-Identifier: BSD-3-Clause
"""Parser for ``conda install --json`` output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class PackageAction:
    """A package action from install JSON output (LINK, UNLINK, FETCH)."""

    name: str
    version: str
    channel: str
    base_url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackageAction:
        """Build from a package dict in actions."""
        return cls(
            name=data["name"],
            version=data["version"],
            channel=data.get("channel", ""),
            base_url=data.get("base_url", ""),
        )


@dataclass(frozen=True, slots=True)
class InstallResult:
    """Parsed ``conda install --json`` output.

    Attributes:
        success: Whether the install succeeded.
        link_packages: Packages that were linked (installed).
    """

    success: bool
    link_packages: tuple[PackageAction, ...]

    @classmethod
    def from_json(cls, result: CommandResult) -> InstallResult:
        """Build from ``conda install --json`` output."""
        data = result.json()
        actions = data["actions"]
        return cls(
            success=data["success"],
            link_packages=tuple(PackageAction.from_dict(pkg) for pkg in actions.get("LINK", [])),
        )
