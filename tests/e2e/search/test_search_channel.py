# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda search channel selection."""

from __future__ import annotations

import pytest
from search_asserts import (
    CONDA_FORGE_CHANNEL_NAME,
    DEFAULT_CHANNEL_NAME,
    PACKAGE_NAME,
    assert_channels_equal,
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
        "pkgs/main": "https://repo.anaconda.com/pkgs/main",
        "pkgs/r": "https://repo.anaconda.com/pkgs/r",
        "pkgs/msys2": "https://repo.anaconda.com/pkgs/msys2",
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
def test_search_additional_channel(conda):
    """``conda search -c conda-forge flask`` adds conda-forge to defaults."""
    assert_defaults_only_config(conda)
    result = conda("search", "-c", "conda-forge", PACKAGE_NAME).assert_ok()
    search = SearchResult.from_stdout(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert_channels_equal(records, {DEFAULT_CHANNEL_NAME, CONDA_FORGE_CHANNEL_NAME})


@pytest.mark.covers(572)
@pytest.mark.smoke
def test_search_channel_qualified_package(conda):
    """``conda search conda-forge::flask`` returns only conda-forge records."""
    assert_defaults_only_config(conda)
    result = conda("search", f"conda-forge::{PACKAGE_NAME}").assert_ok()
    search = SearchResult.from_stdout(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert_channels_equal(records, {CONDA_FORGE_CHANNEL_NAME})
