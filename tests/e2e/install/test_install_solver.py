# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install Solver Mode Modifiers options."""

from __future__ import annotations

from textwrap import dedent

import pytest
from helpers import (
    DEPENDENCY_PACKAGE_NAME,
    PACKAGE_NAME,
    list_installed_packages,
    pick_second_newest_and_latest,
    search_versions,
)
from install_asserts import (
    assert_install_output_has_new_packages,
    assert_installed_version,
    assert_package_present,
    assert_package_unpacked,
    require_installed_record,
    require_python_version,
)
from packaging.version import InvalidVersion, Version

from conda_e2e.parsers.install import InstallResult
from conda_e2e.utils import package_init_file


@pytest.mark.parametrize("solver", ["classic", "libmamba", "rattler"])
def test_install_with_solver(conda, empty_env, solver):
    """``conda install --solver <solver>`` uses the specified solver backend."""
    env_name, env_path = empty_env

    # Execute: install flask using the specified solver
    result = conda("install", "-n", env_name, "--solver", solver, PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify flask appears in conda list
    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_force_reinstall(conda, empty_env):
    """``conda install --force-reinstall <pkg>`` unlinks and relinks the package."""
    env_name, env_path = empty_env

    # Seed: install flask, then delete one of its files so a relink is observable on disk.
    # A correct --json report alone wouldn't prove anything actually changed physically.
    conda("install", "-n", env_name, PACKAGE_NAME).assert_ok()
    seeded = list_installed_packages(conda, "-n", env_name)
    py_version = require_python_version(seeded)
    init_file = package_init_file(env_path, PACKAGE_NAME, py_version)
    init_file.unlink()

    # Execute: force-reinstall flask, capturing the transaction actions
    result = conda(
        "install", "-n", env_name, "--force-reinstall", "--json", PACKAGE_NAME
    ).assert_ok()

    # Verify the transaction unlinked and relinked exactly flask, not other packages
    install_result = InstallResult.from_json(result)
    assert install_result.success, "JSON install result should report success."
    unlinked = {pkg.name for pkg in install_result.unlink_packages}
    linked = {pkg.name for pkg in install_result.link_packages}
    assert unlinked == {PACKAGE_NAME}, (
        f"actions.UNLINK should be exactly {{{PACKAGE_NAME}}}. Got: {unlinked}"
    )
    assert linked == {PACKAGE_NAME}, (
        f"actions.LINK should be exactly {{{PACKAGE_NAME}}}. Got: {linked}"
    )

    # Verify the deleted file came back, proving flask was physically relinked
    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_strict_channel_priority(conda, empty_env, condarc):
    """``conda install --strict-channel-priority`` only pulls from the top channel."""
    env_name, env_path = empty_env
    condarc.write_text(
        dedent("""\
        channels:
          - conda-forge
          - defaults
        """)
    )

    # Execute: install flask, restricting the channel priority to the top channel only
    result = conda("install", "-n", env_name, "--strict-channel-priority", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify every installed package (flask + all deps) came from conda-forge only
    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    channels = {pkg.channel for pkg in installed}
    assert channels == {"conda-forge"}, (
        f"--strict-channel-priority should pull every package from conda-forge only. "
        f"Got channels: {channels}"
    )

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_no_channel_priority_mixes_channels(conda, empty_env, condarc):
    """``conda install --no-channel-priority`` overrides a strict .condarc setting."""
    env_name, env_path = empty_env
    channel_name = "pkgs/main"
    condarc.write_text(
        dedent("""\
        channels:
          - conda-forge
          - defaults
        channel_priority: strict
        """)
    )

    # Execute: install flask, overriding the strict channel_priority config
    result = conda("install", "-n", env_name, "--no-channel-priority", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify at least one dependency came from defaults (pkgs/main), proving
    # the strict channel_priority config was overridden
    installed = list_installed_packages(conda, "-n", env_name)
    assert_package_present(installed, PACKAGE_NAME, env_name)
    channels = {pkg.channel for pkg in installed}
    assert channel_name in channels, (
        f"--no-channel-priority should allow deps from defaults ({channel_name}) despite "
        f"channel_priority: strict. Got channels: {channels}"
    )

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_no_deps(conda, empty_env):
    """``conda install --no-deps flask`` installs only flask, no dependencies."""
    env_name, env_path = empty_env

    # Execute: install flask without dependencies
    result = conda("install", "-n", env_name, "--no-deps", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result, PACKAGE_NAME)

    # Verify flask is the only package installed (env started empty)
    installed = list_installed_packages(conda, "-n", env_name)
    assert installed.names == (PACKAGE_NAME,), (
        f"--no-deps should install only {PACKAGE_NAME}. Installed packages: {installed.names}"
    )

    assert_package_unpacked(env_path, PACKAGE_NAME)


def test_install_only_deps(conda, empty_env):
    """``conda install --only-deps flask`` installs flask's dependencies but not flask itself."""
    env_name, env_path = empty_env

    # Execute: install only flask's dependencies
    result = conda("install", "-n", env_name, "--only-deps", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify flask itself was NOT installed, but its dependencies were
    installed = list_installed_packages(conda, "-n", env_name)
    assert PACKAGE_NAME not in installed, (
        f"--only-deps should not install {PACKAGE_NAME} itself. "
        f"Installed packages: {installed.names}"
    )
    assert_package_present(installed, DEPENDENCY_PACKAGE_NAME, env_name)
    assert len(installed) > 1, (
        f"--only-deps should install more than one dependency for {PACKAGE_NAME}. "
        f"Installed packages: {installed.names}"
    )

    # Verify werkzeug is physically present on disk, not just in conda-meta
    assert_package_unpacked(env_path, DEPENDENCY_PACKAGE_NAME, require_python_version(installed))


def test_install_pin_honored_by_default(conda, empty_env, condarc):
    """``conda install flask`` (no ``--no-pin``) respects a pinned version in .condarc.

    Complements ``test_install_no_pin``: together they prove ``--no-pin`` actually
    overrides a real, working pin -- rather than the pin having no effect either way,
    which would make ``--no-pin``'s effect unobservable.
    """
    env_name, env_path = empty_env
    pinned_version, _ = pick_second_newest_and_latest(conda, PACKAGE_NAME)
    condarc.write_text(
        dedent(f"""\
        pinned_packages:
          - {PACKAGE_NAME}={pinned_version}
        """)
    )

    # Execute: install flask, with no --no-pin, so the pin should be honored
    result = conda("install", "-n", env_name, PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify the pinned version was installed, not the latest
    installed = list_installed_packages(conda, "-n", env_name)
    assert_installed_version(
        installed,
        PACKAGE_NAME,
        pinned_version,
        context="pinned_packages in .condarc should be honored by default (no --no-pin).",
    )

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_no_pin(conda, empty_env, condarc):
    """``conda install --no-pin flask`` ignores a pinned version and installs the latest."""
    env_name, env_path = empty_env
    pinned_version, latest_version = pick_second_newest_and_latest(conda, PACKAGE_NAME)
    condarc.write_text(
        dedent(f"""\
        pinned_packages:
          - {PACKAGE_NAME}={pinned_version}
        """)
    )

    # Execute: install flask, overriding the pinned version
    result = conda("install", "-n", env_name, "--no-pin", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify the pin was ignored: the latest version was installed, not the pinned one
    installed = list_installed_packages(conda, "-n", env_name)
    assert_installed_version(
        installed,
        PACKAGE_NAME,
        latest_version,
        context=f"--no-pin should ignore the pinned version ({pinned_version}).",
    )

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


@pytest.mark.parametrize("flag", ["--no-update-deps", "--freeze-installed"])
def test_install_freeze_deps(conda, empty_env, flag):
    """``conda install --no-update-deps``/``--freeze-installed`` freezes installed deps."""
    env_name, env_path = empty_env
    old_dep_version, _ = pick_second_newest_and_latest(conda, DEPENDENCY_PACKAGE_NAME)
    pkg_spec = f"{DEPENDENCY_PACKAGE_NAME}={old_dep_version}"

    # Seed: pre-install an old werkzeug (flask's dependency)
    conda("install", "-n", env_name, pkg_spec).assert_ok()

    # Verify the seed landed at the expected old version before proceeding
    seeded = list_installed_packages(conda, "-n", env_name)
    assert_installed_version(seeded, DEPENDENCY_PACKAGE_NAME, old_dep_version)

    # Execute: install flask, freezing already-installed dependencies
    result = conda("install", "-n", env_name, flag, PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify werkzeug was NOT upgraded (frozen), and flask was still installed
    installed = list_installed_packages(conda, "-n", env_name)
    assert_installed_version(installed, DEPENDENCY_PACKAGE_NAME, old_dep_version)
    assert_package_present(installed, PACKAGE_NAME, env_name)

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


def test_install_update_deps(conda, empty_env):
    """``conda install --update-deps flask`` updates already-installed dependencies."""
    env_name, env_path = empty_env
    old_dep_version, new_dep_version = pick_second_newest_and_latest(conda, DEPENDENCY_PACKAGE_NAME)

    # Seed: pre-install an old werkzeug (flask's dependency)
    pkg_spec = f"{DEPENDENCY_PACKAGE_NAME}={old_dep_version}"
    conda("install", "-n", env_name, pkg_spec).assert_ok()

    # Verify the seed landed at the expected old version before proceeding
    seeded = list_installed_packages(conda, "-n", env_name)
    assert_installed_version(seeded, DEPENDENCY_PACKAGE_NAME, old_dep_version)

    # Execute: install flask, updating already-installed dependencies
    result = conda("install", "-n", env_name, "--update-deps", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert_install_output_has_new_packages(result)

    # Verify werkzeug WAS upgraded to exactly the known latest version (not just "different")
    installed = list_installed_packages(conda, "-n", env_name)
    assert_installed_version(installed, DEPENDENCY_PACKAGE_NAME, new_dep_version)
    assert_package_present(installed, PACKAGE_NAME, env_name)

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))


@pytest.mark.parametrize("flag", ["--update-all", "--all"])
def test_install_update_all(conda, empty_env, flag):
    """``conda install --update-all``/``--all`` updates every installed package."""
    env_name, env_path = empty_env
    # A near-latest flask alone still resolves the newest werkzeug (loose dependency
    # ranges), leaving nothing to update. Pin both packages to their oldest available
    # version instead, so the seeded environment is genuinely stale.
    pkg_versions = search_versions(conda, PACKAGE_NAME)
    dep_versions = search_versions(conda, DEPENDENCY_PACKAGE_NAME)
    old_pkg_version = pkg_versions[0]
    old_dep_version = dep_versions[0]

    # Seed: pre-install the oldest available flask and werkzeug together
    conda(
        "install",
        "-n",
        env_name,
        f"{PACKAGE_NAME}={old_pkg_version}",
        f"{DEPENDENCY_PACKAGE_NAME}={old_dep_version}",
    ).assert_ok()

    # Capture the FULL seeded package list (not just flask/werkzeug) so we can verify
    # update-all behavior across every package in the environment, not a cherry-picked
    seeded = list_installed_packages(conda, "-n", env_name)

    # Verify the old versions were actually seeded before proceeding
    assert_installed_version(seeded, PACKAGE_NAME, old_pkg_version)
    assert_installed_version(seeded, DEPENDENCY_PACKAGE_NAME, old_dep_version)

    # Execute: update all installed packages
    # NOTE: `conda install` (unlike `conda update`) always requires a package_spec,
    # --file, or --revision -- even with --update-all/--all. Omitting it fails with
    # "too few arguments" (see test_install_fails[update-all-no-spec]).
    conda("install", "-n", env_name, flag, PACKAGE_NAME).assert_ok()

    # Verify no seeded package regressed to an older version, across the WHOLE seeded set
    installed = list_installed_packages(conda, "-n", env_name)
    for seeded_record in seeded:
        after_record = require_installed_record(installed, seeded_record.name)
        # Skip the downgrade check below for packages with non-PEP440 versions
        # (e.g. openssl's "1.1.1w"), which packaging.version.Version can't parse.
        # Presence is still verified above for every seeded package, PEP440 or not.
        try:
            seeded_ver = Version(seeded_record.version)
            after_ver = Version(after_record.version)
        except InvalidVersion:
            continue
        assert after_ver >= seeded_ver, (
            f"{flag} should never downgrade {seeded_record.name}. "
            f"Seeded: {seeded_record.version}, got: {after_record.version}"
        )

    # Verify flask and werkzeug were genuinely upgraded beyond their seeded versions.
    # Not asserting they reached the absolute latest: an old seeded Python may cap how
    # far --update-all can go without bumping Python itself.
    package = require_installed_record(installed, PACKAGE_NAME)
    dependency = require_installed_record(installed, DEPENDENCY_PACKAGE_NAME)
    assert Version(package.version) > Version(old_pkg_version), (
        f"{flag} should upgrade {PACKAGE_NAME} beyond {old_pkg_version}. Got: {package.version}"
    )
    assert Version(dependency.version) > Version(old_dep_version), (
        f"{flag} should upgrade {DEPENDENCY_PACKAGE_NAME} beyond {old_dep_version}. "
        f"Got: {dependency.version}"
    )

    # Verify flask is physically present on disk
    assert_package_unpacked(env_path, PACKAGE_NAME, require_python_version(installed))
