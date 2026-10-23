# SPDX-License-Identifier: BSD-3-Clause
"""Assertions shared by the conda search tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conda_e2e.utils import IS_WINDOWS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from conda_e2e.parsers.search import SearchRecord

PACKAGE_NAME = "flask"
DEFAULT_CHANNEL_URL = "https://repo.anaconda.com/pkgs/main"
CONDA_FORGE_CHANNEL_URL = "https://conda.anaconda.org/conda-forge"
R_CHANNEL_URL = "https://repo.anaconda.com/pkgs/r"
MSYS2_CHANNEL_URL = "https://repo.anaconda.com/pkgs/msys2"
WILDCARD_CHANNEL_URLS = frozenset({DEFAULT_CHANNEL_URL, R_CHANNEL_URL}) | (
    frozenset({MSYS2_CHANNEL_URL}) if IS_WINDOWS else frozenset()
)
_CHANNEL_ALIASES = {
    "pkgs/main": DEFAULT_CHANNEL_URL,
    "pkgs/r": R_CHANNEL_URL,
    "pkgs/msys2": MSYS2_CHANNEL_URL,
    "conda-forge": CONDA_FORGE_CHANNEL_URL,
}


def _channel_origin(channel: str) -> str:
    return _CHANNEL_ALIASES.get(channel, channel)


def assert_records_from_exact_channels(
    records: Iterable[SearchRecord], expected_channels: set[str]
) -> None:
    """Assert the observed channel origins equal the expected channel set."""
    origins = {_channel_origin(record.channel) for record in records}
    assert origins == expected_channels, (
        f"Expected channel origins {sorted(expected_channels)}. Got: {sorted(origins)}"
    )


def assert_records_from_channels(
    records: Iterable[SearchRecord], allowed_channels: set[str] | frozenset[str]
) -> None:
    """Assert every result's channel origin belongs to an allowed channel set."""
    unexpected = {_channel_origin(record.channel) for record in records} - allowed_channels
    assert not unexpected, (
        f"Unexpected channel origins {sorted(unexpected)}; "
        f"expected a subset of {sorted(allowed_channels)}"
    )
