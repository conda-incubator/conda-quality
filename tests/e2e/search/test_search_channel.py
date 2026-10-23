# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda search channel selection."""

from __future__ import annotations

import pytest
from search_asserts import (
    CONDA_FORGE_CHANNEL_URL,
    DEFAULT_CHANNEL_URL,
    MSYS2_CHANNEL_URL,
    PACKAGE_NAME,
    R_CHANNEL_URL,
    assert_records_from_exact_channels,
)

from conda_e2e.parsers.config import ConfigShow
from conda_e2e.parsers.search import SearchResult


def assert_defaults_only_config(conda):
    """Observe the defaults-only channel precondition before channel selection."""
    config = ConfigShow.from_json(
        conda("config", "--show", "channels", "default_channels", "--json").assert_ok()
    )
    assert config.channels == ["defaults"], (
        f"The baseline must use defaults only. Got configured channels: {config.channels}"
    )
    default_channels = config.values["default_channels"]
    assert default_channels, "The baseline must have nonempty default channels."
    expected_defaults = {
        "pkgs/main": DEFAULT_CHANNEL_URL,
        "pkgs/r": R_CHANNEL_URL,
        "pkgs/msys2": MSYS2_CHANNEL_URL,
    }
    for channel in default_channels:
        name = channel["name"]
        url = f"{channel['scheme']}://{channel['location'].rstrip('/')}/{name.lstrip('/')}"
        assert url.rstrip("/") == expected_defaults.get(name), (
            f"Default channel {name!r} must use its expected repository URL. Got: {url}"
        )


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(571)
@pytest.mark.smoke
def test_search_additional_channel(conda):
    """``conda search -c conda-forge flask`` adds conda-forge to defaults."""
    assert_defaults_only_config(conda)
    result = conda("search", "-c", "conda-forge", PACKAGE_NAME).assert_ok()
    search = SearchResult.from_stdout(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert_records_from_exact_channels(records, {DEFAULT_CHANNEL_URL, CONDA_FORGE_CHANNEL_URL})


@pytest.mark.covers(572)
@pytest.mark.smoke
def test_search_channel_qualified_package(conda):
    """``conda search conda-forge::flask`` returns only conda-forge records."""
    assert_defaults_only_config(conda)
    result = conda("search", f"conda-forge::{PACKAGE_NAME}").assert_ok()
    search = SearchResult.from_stdout(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert_records_from_exact_channels(records, {CONDA_FORGE_CHANNEL_URL})
