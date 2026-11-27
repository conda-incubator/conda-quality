# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda list``."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pytest

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import is_same_path

PACKAGE_NAME = "conda-e2e-list-probe"
DEPENDENCY_NAME = "conda-e2e-list-dependency"
PROBE_FILE = f"{PACKAGE_NAME}.txt"
DEPENDENCY_FILE = f"{DEPENDENCY_NAME}.txt"


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.fixture
def installed_list_environment(conda, make_env, tmp_path):
    """Create an environment with a local package and its dependency."""
    dependency = Package(DEPENDENCY_NAME, "1.0", noarch="generic", files=(DEPENDENCY_FILE,))
    probe = Package(
        PACKAGE_NAME, "1.0", depends=(dependency.name,), noarch="generic", files=(PROBE_FILE,)
    )
    channel = build_local_channel(tmp_path / "list-channel", [dependency, probe])
    env_name, env_path = make_env()
    conda(
        "install", "-n", env_name, PACKAGE_NAME, "-c", channel.as_uri(), "--override-channels"
    ).assert_ok()
    probe_file = env_path / PROBE_FILE
    assert probe_file.is_file(), f"Setup: probe must be unpacked at {probe_file}"
    dependency_file = env_path / DEPENDENCY_FILE
    assert dependency_file.is_file(), f"Setup: dependency must be unpacked at {dependency_file}"

    return env_name, env_path, channel, probe, dependency


@pytest.mark.covers(439)
@pytest.mark.smoke
def test_list_reports_installed_packages(conda_shell, installed_list_environment):
    """Bare ``conda list`` reports installed records from the activated environment.

    The install command names only the probe, so the listing must also report
    its implicitly installed dependency.
    """
    env_name, env_path, channel, probe, dependency = installed_list_environment
    result = conda_shell.run_in_activated_env(env_name, "conda list").assert_ok()
    packages = PackageList.from_stdout(result)

    assert sorted(packages.names) == sorted((PACKAGE_NAME, DEPENDENCY_NAME)), (
        f"Unexpected records. Got: {packages.names}"
    )
    record = packages.get(PACKAGE_NAME)
    assert record.version == probe.version, f"Wrong version: {record}"
    assert record.build == probe.metadata["build"], f"Wrong build: {record}"
    parsed_channel = urlparse(record.channel)
    assert parsed_channel.scheme == "file", f"Expected file:// channel URL, got {record.channel!r}"
    assert not parsed_channel.netloc, f"Expected local channel URL, got {record.channel!r}"
    assert is_same_path(url2pathname(parsed_channel.path), channel), (
        f"Wrong channel: {record.channel!r}"
    )

    dependency_record = packages.get(DEPENDENCY_NAME)
    assert dependency_record.version == dependency.version, (
        f"Wrong dependency version: {dependency_record}"
    )

    assert is_same_path(packages.environment, env_path), (
        f"Header points at {packages.environment!r}, expected {env_path}"
    )


@pytest.mark.covers(440)
def test_list_reports_installed_packages_json(conda_shell, installed_list_environment):
    """``conda list --json`` reports installed records and their expected fields."""
    env_name, _, channel, probe, dependency = installed_list_environment
    result = conda_shell.run_in_activated_env(env_name, "conda list --json").assert_ok()
    packages = PackageList.from_json(result)

    assert sorted(packages.names) == sorted((probe.name, dependency.name)), (
        f"Unexpected records. Got: {packages.names}"
    )
    expected_keys = {
        "base_url",
        "build_number",
        "build_string",
        "channel",
        "dist_name",
        "name",
        "platform",
        "version",
    }
    for record in packages:
        assert expected_keys <= record.json_keys, (
            f"Expected JSON fields {expected_keys} for {record.name}, got {record.json_keys}"
        )

    record = packages.get(probe.name)
    assert record.version == probe.version, f"Wrong version: {record}"
    assert record.build_string == probe.metadata["build"], f"Wrong build string: {record}"
    assert type(record.build_number) is int, f"Build number must be an integer: {record}"
    assert record.build_number == probe.metadata["build_number"], f"Wrong build number: {record}"
    assert record.channel == channel.name, f"Wrong channel: {record.channel!r}"
    assert record.dist_name == probe.filename.removesuffix(".tar.bz2"), f"Wrong dist name: {record}"
    assert record.platform == probe.metadata["subdir"], f"Wrong platform: {record}"
    assert record.base_url is not None, f"Missing base URL: {record}"
    parsed_base_url = urlparse(record.base_url)
    assert parsed_base_url.scheme == "file", f"Expected file:// URL, got {record.base_url!r}"
    assert not parsed_base_url.netloc, f"Expected local base URL, got {record.base_url!r}"
    assert is_same_path(url2pathname(parsed_base_url.path), channel), (
        f"Wrong base URL: {record.base_url!r}"
    )


@pytest.mark.covers(441)
def test_list_named_environment(conda, make_env, installed_list_environment):
    """``conda list -n`` selects the named environment instead of the current one."""
    env_name, env_path, _, probe, dependency = installed_list_environment
    _, current_env_path = make_env()
    current_env = {"CONDA_PREFIX": str(current_env_path)}

    baseline = PackageList.from_stdout(conda("list", extra_env=current_env).assert_ok())
    assert is_same_path(baseline.environment, current_env_path), (
        f"Baseline header points at {baseline.environment!r}, expected {current_env_path}"
    )
    assert not baseline.names, f"Current environment should be empty: {baseline.names}"

    result = conda("list", "-n", env_name, extra_env=current_env).assert_ok()
    packages = PackageList.from_stdout(result)
    assert is_same_path(packages.environment, env_path), (
        f"Header points at {packages.environment!r}, expected {env_path}"
    )
    assert sorted(packages.names) == sorted((probe.name, dependency.name)), (
        f"Unexpected records. Got: {packages.names}"
    )

    long_form = conda("list", "--name", env_name, extra_env=current_env).assert_ok()
    assert long_form.stdout == result.stdout, "The -n and --name outputs differ"


@pytest.mark.covers(442)
def test_list_environment_by_prefix(conda, installed_list_environment):
    """``conda list -p`` reports packages from the environment at the given path."""
    _, env_path, _, probe, dependency = installed_list_environment
    result = conda("list", "-p", env_path).assert_ok()
    packages = PackageList.from_stdout(result)
    assert is_same_path(packages.environment, env_path), (
        f"Header points at {packages.environment!r}, expected {env_path}"
    )
    assert sorted(packages.names) == sorted((probe.name, dependency.name)), (
        f"Unexpected records: {packages.names}"
    )


@pytest.mark.covers(452)
def test_list_full_name_matches_only_exact_package(conda, tmp_path, installed_list_environment):
    """``conda list --full-name`` excludes longer package names containing the match."""
    env_name, env_path, _, probe, dependency = installed_list_environment
    # Match at both ends so omitting either full-name boundary includes this package.
    related_name = f"{probe.name}-{probe.name}"
    related_file = f"{related_name}.txt"
    related = Package(related_name, probe.version, noarch="generic", files=(related_file,))
    channel = build_local_channel(tmp_path / "full-name-channel", [probe, dependency, related])
    conda(
        "install", "-n", env_name, related.name, "-c", channel.as_uri(), "--override-channels"
    ).assert_ok()
    assert (env_path / related_file).is_file(), f"Setup: {related.name} must be unpacked"

    baseline = PackageList.from_stdout(conda("list", "-n", env_name, probe.name).assert_ok())
    assert sorted(baseline.names) == sorted((probe.name, related.name)), (
        f"Unexpected partial matches: {baseline.names}"
    )

    result = conda("list", "-n", env_name, "--full-name", probe.name).assert_ok()
    packages = PackageList.from_stdout(result)
    assert is_same_path(packages.environment, env_path), (
        f"Header points at {packages.environment!r}, expected {env_path}"
    )
    assert packages.names == (probe.name,), f"Unexpected exact matches: {packages.names}"


@pytest.mark.covers(453)
def test_list_explicit_reports_package_urls(conda_shell, installed_list_environment):
    """``conda list --explicit`` reports URLs for the installed packages."""
    env_name, _, channel, probe, dependency = installed_list_environment
    result = conda_shell.run_in_activated_env(env_name, "conda list --explicit").assert_ok()
    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines[:1] == ["@EXPLICIT"], f"Missing explicit marker: {result.stdout}"

    urls = [urlparse(line) for line in lines[1:]]
    expected_paths = [
        channel / package.metadata["subdir"] / package.filename for package in (probe, dependency)
    ]
    assert len(urls) == len(expected_paths), f"Unexpected package URLs: {lines[1:]}"
    for url in urls:
        assert url.scheme == "file", f"Expected a file URL: {url.geturl()}"
        assert not url.netloc, f"Expected a local file URL: {url.geturl()}"

    paths = [Path(url2pathname(url.path)) for url in urls]
    for expected in expected_paths:
        assert sum(is_same_path(path, expected) for path in paths) == 1, (
            f"Expected package URL for {expected}, got {lines[1:]}"
        )
