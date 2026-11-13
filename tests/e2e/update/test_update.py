# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for ``conda update``."""

from __future__ import annotations

import tarfile

import pytest
from shared.helpers import list_installed_packages

from conda_e2e.channel import Package, build_local_channel

PACKAGE_NAME = "conda-e2e-update-probe"
PACKAGE_FILE = f"{PACKAGE_NAME}.txt"


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.covers(637)
@pytest.mark.smoke
def test_update_package_in_current_environment(conda, conda_shell, make_env, condarc, tmp_path):
    """Bare ``conda update <package>`` upgrades that package in the active env."""
    older = Package(PACKAGE_NAME, "1.0", noarch="generic", files=(PACKAGE_FILE,))
    newer = Package(PACKAGE_NAME, "2.0", noarch="generic", files=(PACKAGE_FILE,))
    channel = build_local_channel(tmp_path / "update-channel", [older, newer])
    env_name, env_path = make_env()
    condarc.write_text(f"channels:\n  - {channel.as_uri()}\ndefault_channels: []\n")
    conda("install", "-n", env_name, f"{PACKAGE_NAME}=1.0").assert_ok()
    seeded = list_installed_packages(conda, "-n", env_name)
    assert sorted(seeded.names) == [PACKAGE_NAME], (
        f"Setup should install only {PACKAGE_NAME}. Got: {seeded.names}"
    )
    seeded_record = seeded.get(PACKAGE_NAME)
    assert seeded_record.version == older.version, (
        f"Setup should seed version {older.version}. Got: {seeded_record.version}"
    )
    package_file = env_path / PACKAGE_FILE
    assert package_file.is_file(), f"Setup: package must be unpacked at {package_file}"
    with tarfile.open(channel / "noarch" / older.filename) as archive:
        expected_old_file = archive.extractfile(PACKAGE_FILE).read()
    assert package_file.read_bytes() == expected_old_file, (
        f"Setup must install the old package payload at {package_file}"
    )

    conda_shell.run_in_activated_env(env_name, f"conda update {PACKAGE_NAME}").assert_ok()

    updated = list_installed_packages(conda, "-n", env_name)
    assert sorted(updated.names) == [PACKAGE_NAME], (
        f"Update must not add or remove packages. Got: {updated.names}"
    )
    updated_record = updated.get(PACKAGE_NAME)
    assert updated_record.version == newer.version, (
        f"Bare update should upgrade {PACKAGE_NAME} to {newer.version}. "
        f"Got: {updated_record.version}"
    )
    with tarfile.open(channel / "noarch" / newer.filename) as archive:
        expected_new_file = archive.extractfile(PACKAGE_FILE).read()
    assert package_file.read_bytes() == expected_new_file, (
        f"Updating {PACKAGE_NAME} must install the new package payload at {package_file}"
    )
