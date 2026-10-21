# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda search channel selection."""

from __future__ import annotations

import pytest
from search_asserts import (
    CONDA_FORGE_CHANNEL_URL,
    DEFAULT_CHANNEL_URL,
    PACKAGE_NAME,
    assert_records_from_channels,
)

from conda_e2e.parsers.config import ConfigShow
from conda_e2e.parsers.search import SearchResult

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(571)
def test_search_additional_channel(conda):
    """``conda search -c conda-forge flask`` adds conda-forge to defaults."""
    config = ConfigShow.from_json(
        conda("config", "--show", "channels", "default_channels", "--json").assert_ok()
    )
    assert config.channels == ["defaults"], (
        f"The baseline must use defaults only. Got configured channels: {config.channels}"
    )
    assert "conda-forge" not in config.default_channels, (
        f"Defaults must exclude conda-forge. Got default channels: {config.default_channels}"
    )

    result = conda("search", "-c", "conda-forge", PACKAGE_NAME, "--json").assert_ok()
    search = SearchResult.from_json(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert {record.name for record in records} == {PACKAGE_NAME}

    assert {record.channel.rsplit("/", 1)[0] for record in records} == {
        DEFAULT_CHANNEL_URL,
        CONDA_FORGE_CHANNEL_URL,
    }


@pytest.mark.covers(572)
def test_search_channel_qualified_package(conda):
    """``conda search conda-forge::flask`` returns only conda-forge records."""
    config = ConfigShow.from_json(
        conda("config", "--show", "channels", "default_channels", "--json").assert_ok()
    )
    assert config.channels == ["defaults"], (
        f"The baseline must use defaults only. Got configured channels: {config.channels}"
    )
    assert "conda-forge" not in config.default_channels, (
        f"Defaults must exclude conda-forge. Got default channels: {config.default_channels}"
    )

    result = conda("search", f"conda-forge::{PACKAGE_NAME}", "--json").assert_ok()
    search = SearchResult.from_json(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert {record.name for record in records} == {PACKAGE_NAME}
    assert_records_from_channels(records, {CONDA_FORGE_CHANNEL_URL})
