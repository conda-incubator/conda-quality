# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda list``."""

from __future__ import annotations

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
ENVIRONMENT_HEADER = "# packages in environment at "


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(439)
@pytest.mark.smoke
def test_list_reports_installed_packages(conda, conda_shell, make_env, tmp_path):
    """Bare ``conda list`` reports installed records from the activated environment.

    The install command names only the probe, so the listing must also report
    its implicitly installed dependency.
    """
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
    assert is_same_path(url2pathname(parsed_channel.path), channel), (
        f"Wrong channel: {record.channel!r}"
    )

    dependency_record = packages.get(DEPENDENCY_NAME)
    assert dependency_record.version == dependency.version, (
        f"Wrong dependency version: {dependency_record}"
    )

    header_paths = [
        line.removeprefix(ENVIRONMENT_HEADER).removesuffix(":")
        for line in result.stdout.splitlines()
        if line.startswith(ENVIRONMENT_HEADER)
    ]
    assert len(header_paths) == 1, f"Expected one environment header. Got: {header_paths}"
    assert is_same_path(header_paths[0], env_path), (
        f"Header points at {header_paths[0]!r}, expected {env_path}"
    )
