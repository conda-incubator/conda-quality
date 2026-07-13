# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda config --show`` and ``conda config --show-sources`` output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable

    from conda_e2e.result import CommandResult

# Matches each "==> /path/to/config <==" source header.
_SOURCE_HEADER = re.compile(r"^==> (.+?) <==$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ConfigShow:
    """Parsed ``conda config --show`` output (all effective settings).

    Works for the full ``--show`` dump and for a single ``--show <key>``. The
    settings mapping is schemaless, so it is kept in ``values`` and typed
    accessors are exposed only for the fields under test.

    Attributes:
        values: The effective config as a ``setting -> value`` mapping.
    """

    values: dict[str, Any]

    def __contains__(self, key: object) -> bool:
        """Whether ``key``(i.e. channels) is present in the config (any setting name)."""
        return key in self.values

    @property
    def channels(self) -> list[str]:
        """The configured ``channels``."""
        return self.values.get("channels", [])

    @property
    def channel_priority(self) -> str | None:
        """The configured ``channel_priority``."""
        return self.values.get("channel_priority")

    @classmethod
    def from_stdout(cls, result: CommandResult) -> ConfigShow:
        """Build from ``conda config --show`` stdout.

        The output is a single YAML document. Note: conda prints Python-style
        ``None`` for unset values, which YAML reads as the string ``"None"``
        (``--json`` emits real null instead); this does not affect list/str
        settings such as ``channels``/``channel_priority``.
        """
        return cls(yaml.safe_load(result.stdout) or {})

    @classmethod
    def from_json(cls, result: CommandResult) -> ConfigShow:
        """Build from ``conda config --show --json`` output."""
        return cls(result.json())


@dataclass(frozen=True, slots=True)
class ConfigSources:
    """Parsed output from ``conda config --show-sources``.

    Attributes:
        sources: Mapping of resolved config-file path to its config values.
        env_sources: Mapping of non-file source label (i.e. ``"envvars"``)
        to its config values. Kept separate because these are not files
        and cannot be represented as :class:`~pathlib.Path`.
    """

    sources: dict[Path, dict[str, Any]]
    env_sources: dict[str, dict[str, Any]]

    @property
    def source_paths(self) -> tuple[Path, ...]:
        """The resolved path of each listed file source."""
        return tuple(self.sources)

    def has_source(self, path: Path) -> bool:
        """Whether ``path`` is listed as a file source (compares resolved paths)."""
        return path.resolve() in self.sources

    def channels(self, path: Path) -> list[str]:
        """The ``channels`` configured in the file source at ``path``."""
        return self.sources[path.resolve()].get("channels", [])

    @classmethod
    def from_json(cls, result: CommandResult) -> ConfigSources:
        """Build from ``conda config --show-sources --json`` output.

        The JSON maps each source to its config values. File sources are keyed
        by resolved path and non-file sources (``envvars``, etc) are
        kept in ``env_sources``.
        """
        return cls._partition(result.json().items())

    @classmethod
    def from_stdout(cls, result: CommandResult) -> ConfigSources:
        """Build from ``conda config --show-sources`` stdout.

        Each ``==> <source> <==`` header is followed by that source's settings
        as a YAML block, parsed so the result matches :meth:`from_json`.
        """
        # split() on the capturing header regex yields
        # [preamble, label, body, label, body, ...]. Pair each label with its body.
        parts = _SOURCE_HEADER.split(result.stdout)
        items = (
            (label.strip(), yaml.safe_load(body) or {})
            for label, body in zip(parts[1::2], parts[2::2], strict=True)
        )
        return cls._partition(items)

    @classmethod
    def _partition(cls, items: Iterable[tuple[str, dict[str, Any]]]) -> ConfigSources:
        """Split ``(source, values)`` pairs into file vs non-file sources.

        A file source is an absolute path; every other label conda may emit
        (like ``envvars``, etc) is a non-file source kept in ``env_sources``.
        """
        sources: dict[Path, dict[str, Any]] = {}
        env_sources: dict[str, dict[str, Any]] = {}
        for source, values in items:
            path = Path(source)
            if path.is_absolute():
                sources[path.resolve()] = values
            else:
                env_sources[source] = values
        return cls(sources, env_sources)
