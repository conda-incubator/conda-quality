# SPDX-License-Identifier: BSD-3-Clause
"""Parser for ``conda info --json`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class CondaInfo:
    """Selected fields from ``conda info --json``.

    Prefixes are :class:`~pathlib.Path`. ``active_prefix`` is ``None`` when no
    environment is active.
    """

    conda_version: str
    root_prefix: Path
    active_prefix: Path | None
    active_prefix_name: str | None


def parse_info_json(result: CommandResult) -> CondaInfo:
    """Parse ``conda info --json`` into a :class:`CondaInfo`."""
    data = result.json()
    active_prefix = data.get("active_prefix")
    return CondaInfo(
        conda_version=data["conda_version"],
        root_prefix=Path(data["root_prefix"]),
        active_prefix=Path(active_prefix) if active_prefix is not None else None,
        active_prefix_name=data.get("active_prefix_name"),
    )
