# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda search package matching."""

from __future__ import annotations

import pytest
from packaging.version import Version
from search_asserts import DEFAULT_CHANNEL_NAME, PACKAGE_NAME, assert_channels_equal
from shared.helpers import pick_second_newest_and_latest

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.parsers.search import SearchEnvironmentsResult, SearchResult
from conda_e2e.utils import is_same_path


@pytest.fixture
def local_search_channel(tmp_path):
    """Build a local channel with numeric-version and package-name contrasts."""
    packages = [Package("flask", version) for version in ("1.9", "1.10", "2.0")]
    packages.extend(
        Package(name, "1.0")
        for name in ("six", "six-prefix", "suffix-six", "middle-six-middle", "unrelated")
    )
    channel = build_local_channel(tmp_path / "search-channel", packages)
    return channel, packages


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(567)
@pytest.mark.smoke
def test_search_package_name(conda):
    """``conda search flask`` returns only flask records from defaults' pkgs/main."""
    result = conda("search", PACKAGE_NAME).assert_ok()
    search = SearchResult.from_stdout(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert_channels_equal(records, {DEFAULT_CHANNEL_NAME})


@pytest.mark.covers(568)
@pytest.mark.parametrize("operator", [">=", "<=", "=="])
def test_search_version_spec(conda, local_search_channel, operator):
    """Version operators match numeric flask versions, retaining their build metadata."""
    channel, packages = local_search_channel
    bound_version = "1.10"
    bound = Version(bound_version)
    predicate = {
        ">=": lambda version: version >= bound,
        "<=": lambda version: version <= bound,
        "==": lambda version: version == bound,
    }[operator]
    expected_packages = [
        package
        for package in packages
        if package.name == PACKAGE_NAME and predicate(Version(package.version))
    ]
    expected_records = sorted(
        (package.version, package.metadata["build"]) for package in expected_packages
    )
    result = conda(
        "search",
        f"{PACKAGE_NAME} {operator}{bound_version}",
        "-c",
        channel.as_uri(),
        "--override-channels",
    ).assert_ok()
    search = SearchResult.from_stdout(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    actual_records = sorted((record.version, record.build) for record in records)
    assert actual_records == expected_records, (
        f"Expected exactly these matching records: {expected_records}. Got: {actual_records}"
    )
    assert_channels_equal(records, {channel.name})


@pytest.mark.covers(569)
@pytest.mark.parametrize("pattern", ["six*", "*six", "*six*"])
def test_search_glob_matches_package_names(conda, local_search_channel, pattern):
    """Globs include exactly matching names and retain each package's version and build."""
    channel, packages = local_search_channel
    matches = {
        "six*": lambda name: name.startswith("six"),
        "*six": lambda name: name.endswith("six"),
        "*six*": lambda name: "six" in name,
    }[pattern]
    expected_packages = {package.name: package for package in packages if matches(package.name)}

    result = conda("search", pattern, "-c", channel.as_uri(), "--override-channels").assert_ok()
    search = SearchResult.from_stdout(result)
    assert set(search.packages) == set(expected_packages)
    for name, package in expected_packages.items():
        records = search.get(name)
        assert [(record.version, record.build) for record in records] == [
            (package.version, package.metadata["build"])
        ]
        assert_channels_equal(records, {channel.name})


@pytest.mark.covers(570)
def test_search_envs_finds_installed_package(conda, make_env):
    """``conda search --envs flask`` reports a pinned older version, not the latest release."""
    old_version, _ = pick_second_newest_and_latest(conda, PACKAGE_NAME)
    env_name, env_path = make_env()
    _, empty_env_path = make_env()
    conda("install", "-n", env_name, f"{PACKAGE_NAME}={old_version}").assert_ok()
    result = conda("search", "--envs", PACKAGE_NAME).assert_ok()
    environments = SearchEnvironmentsResult.from_stdout(result).environments
    locations = [environment.location for environment in environments]
    matching_envs = [
        environment for environment in environments if is_same_path(environment.location, env_path)
    ]
    assert len(matching_envs) == 1, (
        f"--envs should report exactly one entry for {env_path}. Got: {locations}"
    )
    assert not any(is_same_path(location, empty_env_path) for location in locations), (
        f"--envs should not report an environment without {PACKAGE_NAME}. Got: {locations}"
    )
    for environment in environments:
        names = {record.name for record in environment.packages}
        assert names == {PACKAGE_NAME}, (
            f"Expected only {PACKAGE_NAME} in search results for {environment.location}. "
            f"Got names: {sorted(names)}"
        )
    records = matching_envs[0].packages
    assert len(records) == 1, f"Expected one installed {PACKAGE_NAME} record. Got: {records}"
    assert records[0].version == old_version, (
        f"--envs should report the pinned {PACKAGE_NAME} version {old_version}. "
        f"Got: {records[0].version}"
    )
    assert_channels_equal(records, {DEFAULT_CHANNEL_NAME})


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.covers(659)
def test_search_nonexistent_package(conda):
    """An unavailable package produces a package-not-found error on stderr."""
    package_name = "conda-e2e-nonexistent-package-4fd7566ed19c43c5b8a37a5f2e01d403"
    result = conda("search", package_name).assert_error(
        code=1,
        contains="PackagesNotFoundInChannelsError",
        stream="stderr",
    )
    assert package_name in result.stderr, (
        f"The error should identify the unavailable package {package_name!r}. "
        f"Got stderr: {result.stderr}"
    )


@pytest.mark.covers(660)
def test_search_rejects_unsupported_option(conda):
    """``conda search`` rejects an unsupported option on stderr."""
    conda("search", "--not-a-real-option", PACKAGE_NAME).assert_error(
        code=2,
        contains="unrecognized arguments: --not-a-real-option",
        stream="stderr",
    )
