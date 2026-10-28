# SPDX-License-Identifier: BSD-3-Clause
"""Assertions shared by the conda search tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from conda_e2e.parsers.search import SearchRecord

PACKAGE_NAME = "flask"
DEFAULT_CHANNEL_NAME = "pkgs/main"
CONDA_FORGE_CHANNEL_NAME = "conda-forge"


def assert_channels_equal(records: Iterable[SearchRecord], expected_channels: set[str]) -> None:
    """Assert the reported channel names equal the expected channel set."""
    actual_channels = {record.channel for record in records}
    assert actual_channels == expected_channels, (
        f"Expected channels {sorted(expected_channels)}. Got: {sorted(actual_channels)}"
    )
