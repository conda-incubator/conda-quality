# SPDX-License-Identifier: BSD-3-Clause
"""Parser for ``conda info --json`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class CondaInfo:
    """Selected fields from ``conda info --json``.

    Prefixes are :class:`~pathlib.Path`. ``active_prefix`` is ``None`` when no
    environment is active. ``env_vars`` is a read-only mapping, so ``frozen=True``
    holds through it too (callers can't mutate it in place).
    """

    # NOTE: Add more fields if we need to test additional cases in the future.
    conda_version: str
    root_prefix: Path
    active_prefix: Path | None
    active_prefix_name: str | None
    env_vars: Mapping[str, str]

    @classmethod
    def from_json(cls, result: CommandResult) -> CondaInfo:
        """Build from ``conda info --json`` output."""
        data = result.json()
        active_prefix = data.get("active_prefix")
        return cls(
            conda_version=data["conda_version"],
            root_prefix=Path(data["root_prefix"]),
            active_prefix=Path(active_prefix) if active_prefix is not None else None,
            active_prefix_name=data.get("active_prefix_name"),
            # Read-only so env_vars can't be edited in place, matching frozen=True.
            env_vars=MappingProxyType(dict(data.get("env_vars") or {})),
        )
