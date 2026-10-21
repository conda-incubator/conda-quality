# SPDX-License-Identifier: BSD-3-Clause
"""Assertions shared by the conda search tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from conda_e2e.parsers.search import SearchRecord

PACKAGE_NAME = "flask"
DEFAULT_CHANNEL_URL = "https://repo.anaconda.com/pkgs/main"
CONDA_FORGE_CHANNEL_URL = "https://conda.anaconda.org/conda-forge"


def assert_records_from_channels(
    records: Iterable[SearchRecord], allowed_channels: set[str]
) -> None:
    """Assert every result's channel URL belongs to an allowed channel base URL."""
    for record in records:
        assert record.channel.rsplit("/", 1)[0] in allowed_channels, (
            f"{record.name} {record.version} came from unexpected channel {record.channel!r}; "
            f"expected one of {allowed_channels}"
        )
