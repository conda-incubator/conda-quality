# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda search package matching."""

from __future__ import annotations

import pytest
from packaging.version import Version
from search_asserts import DEFAULT_CHANNEL_URL, PACKAGE_NAME, assert_records_from_channels
from shared.helpers import list_installed_packages, search_versions

from conda_e2e.parsers.search import SearchEnvironments, SearchResult
from conda_e2e.utils import is_same_path, package_init_file

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(567)
def test_search_package_name(conda):
    """``conda search flask`` returns only flask records from defaults' pkgs/main."""
    result = conda("search", PACKAGE_NAME, "--json").assert_ok()
    search = SearchResult.from_json(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert {record.name for record in records} == {PACKAGE_NAME}

    assert_records_from_channels(records, {DEFAULT_CHANNEL_URL})


@pytest.mark.covers(568)
@pytest.mark.parametrize("operator", [">=", "<=", "=="])
def test_search_version_spec(conda, operator):
    """Version operators return exactly the available flask versions they match."""
    all_versions = search_versions(conda, PACKAGE_NAME)
    assert len(all_versions) >= 3, (
        f"Need at least 3 {PACKAGE_NAME} versions to distinguish version operators. "
        f"Got: {all_versions}"
    )
    bound_version = all_versions[-2]
    bound = Version(bound_version)
    predicate = {
        ">=": lambda version: version >= bound,
        "<=": lambda version: version <= bound,
        "==": lambda version: version == bound,
    }[operator]
    expected = {version for value in all_versions if predicate(version := Version(value))}

    result = conda("search", f"{PACKAGE_NAME} {operator}{bound_version}", "--json").assert_ok()
    search = SearchResult.from_json(result)
    assert set(search.packages) == {PACKAGE_NAME}
    records = search.get(PACKAGE_NAME)
    assert {record.name for record in records} == {PACKAGE_NAME}
    returned_versions = {Version(record.version) for record in records}
    assert returned_versions == expected, (
        f"{PACKAGE_NAME}{operator}{bound_version} should return exactly {expected}. "
        f"Got: {returned_versions}"
    )
    assert_records_from_channels(records, {DEFAULT_CHANNEL_URL})


@pytest.mark.covers(569)
def test_search_glob_matches_package_names(conda):
    """``conda search *six*`` matches names requiring both surrounding wildcards."""
    required_names = {"six", "r-sixsigma"}
    for name in sorted(required_names):
        exact = SearchResult.from_json(conda("search", name, "--json").assert_ok())
        assert set(exact.packages) == {name}
        assert {record.name for record in exact.get(name)} == {name}

    pattern = "*six*"
    result = conda("search", pattern, "--json").assert_ok()
    search = SearchResult.from_json(result)
    assert required_names <= search.packages.keys(), (
        f"{pattern} should include independently observed names {required_names}. "
        f"Got: {tuple(search.packages)}"
    )
    assert all("six" in name for name in search.packages), (
        f"Every returned name should match {pattern}. Got: {tuple(search.packages)}"
    )
    assert all(
        {record.name for record in records} == {name} for name, records in search.packages.items()
    ), f"Every result key should have matching package records. Got: {search.packages}"
    records = tuple(
        record for package_records in search.packages.values() for record in package_records
    )
    assert_records_from_channels(
        records,
        {
            DEFAULT_CHANNEL_URL,
            "https://repo.anaconda.com/pkgs/r",
            "https://repo.anaconda.com/pkgs/msys2",
        },
    )


@pytest.mark.covers(570)
def test_search_envs_finds_installed_package(conda, make_env):
    """``conda search --envs flask`` reports the installed version in the matching env."""
    env_name, env_path = make_env()
    _, empty_env_path = make_env()
    conda("install", "-n", env_name, PACKAGE_NAME).assert_ok()
    init_file = package_init_file(env_path, PACKAGE_NAME)
    assert init_file.is_file(), f"Expected {PACKAGE_NAME} installed on disk at {init_file}"
    installed = list_installed_packages(conda, "-p", str(env_path)).get(PACKAGE_NAME)
    assert installed is not None, f"conda list should report {PACKAGE_NAME} in {env_path}"

    result = conda("search", "--envs", PACKAGE_NAME, "--json").assert_ok()
    environments = SearchEnvironments.from_json(result).environments
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
    assert all(
        {record.name for record in environment.packages} == {PACKAGE_NAME}
        for environment in environments
    ), f"Every matching environment should report only {PACKAGE_NAME}. Got: {environments}"
    records = matching_envs[0].packages
    assert {record.version for record in records} == {installed.version}, (
        f"--envs should report the installed {PACKAGE_NAME} version {installed.version}. "
        f"Got: {[record.version for record in records]}"
    )
    assert_records_from_channels(records, {DEFAULT_CHANNEL_URL})


# =============================================================================
# Negative test cases
# =============================================================================


def test_search_rejects_unsupported_option(conda):
    """``conda search`` rejects an unsupported option on stderr."""
    conda("search", "--not-a-real-option", PACKAGE_NAME).assert_error(
        code=2,
        contains="unrecognized arguments: --not-a-real-option",
        stream="stderr",
    )
