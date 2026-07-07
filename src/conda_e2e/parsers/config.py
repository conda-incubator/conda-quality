# SPDX-License-Identifier: BSD-3-Clause
"""Parser for ``conda config --show-sources`` output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class ConfigSources:
    """Parsed output from ``conda config --show-sources``.

    Attributes:
        sources: Mapping of source path to its config values (from JSON).
        source_paths: List of source paths mentioned in the output (from stdout).
    """

    sources: dict[Path, dict]
    source_paths: list[Path]

    @classmethod
    def from_json(cls, result: CommandResult) -> ConfigSources:
        """Build from ``conda config --show-sources --json`` output.

        The JSON format is a dict mapping source path strings to their config values.
        """
        data = result.json()
        sources = {Path(path).resolve(): values for path, values in data.items()}
        return cls(sources=sources, source_paths=list(sources.keys()))

    @classmethod
    def from_stdout(cls, result: CommandResult) -> ConfigSources:
        """Build from ``conda config --show-sources`` stdout.

        Parses the ==> /path/to/config <== headers to extract source paths.
        """
        header_pattern = re.compile(r"==> (.+?) <==")
        paths = []
        for match in header_pattern.finditer(result.stdout):
            path_str = match.group(1).strip()
            paths.append(Path(path_str).resolve())
        return cls(sources={}, source_paths=paths)

    def has_source(self, path: Path) -> bool:
        """Check if a source path is listed (compares resolved paths)."""
        resolved = path.resolve()
        return any(p == resolved for p in self.source_paths)

    def get_config(self, path: Path) -> dict | None:
        """Get config values for a source path (from JSON only)."""
        resolved = path.resolve()
        return self.sources.get(resolved)
