# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda install command."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from packaging.version import Version

from conda_e2e.parsers.config import ConfigShow
from conda_e2e.parsers.info import CondaInfo
from conda_e2e.parsers.list import PackageList
from conda_e2e.utils import site_packages_dir

if TYPE_CHECKING:
    from pathlib import Path

NEW_PKG_INSTALLED_MSG = "The following NEW packages will be INSTALLED:"
PACKAGE_NAME = "flask"
DEPENDENCY_PACKAGE_NAME = "werkzeug"

# =============================================================================
# Helper functions
# =============================================================================


def _python_version(installed: PackageList) -> str:
    """Return the installed ``python`` package's version, asserting it's present."""
    python = installed.get("python")
    assert python is not None, "python should be installed as a dependency"
    return python.version


def _assert_package_unpacked(
    env_path: Path,
    package_name: str,
    python_version: str | None = None,
) -> None:
    """Assert ``package_name`` is physically unpacked on disk (as a package dir)."""
    site_packages = site_packages_dir(env_path, python_version)
    init_file = site_packages / package_name / "__init__.py"
    assert init_file.is_file(), f"{package_name} should be unpacked on disk at {site_packages}"


def _search_versions(conda, package_name: str) -> list[str]:
    """Return all available versions for ``package_name``, sorted ascending."""
    search_result = conda("search", package_name, "--json").assert_ok()
    return sorted(
        {p["version"] for p in search_result.json().get(package_name, [])},
        key=Version,
    )


def _pick_second_newest_and_latest(conda, package_name: str) -> tuple[str, str]:
    """Return ``(old_version, latest_version)`` for ``package_name``, picked dynamically.

    ``old_version`` is the second-newest available version, so it's guaranteed to
    differ from ``latest_version`` without hardcoding a version that could age out.
    """
    versions = _search_versions(conda, package_name)
    assert len(versions) >= 2, f"need at least 2 {package_name} versions to pick from"
    return versions[-2], versions[-1]


# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.parametrize("use_path", [False, True], ids=["name", "path"])
def test_install_package(conda, empty_env, use_path):
    """``conda install`` by env name or path installs flask and it appears in ``conda list``."""
    env_name, env_path = empty_env
    target = str(env_path) if use_path else env_name
    flag = "-p" if use_path else "-n"

    # Execute: install flask into the env
    result = conda("install", flag, target, PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Install output should mention {PACKAGE_NAME}. Got:\n{result.stdout}"
    )

    # Verify flask appears in conda list
    list_result = conda("list", flag, target).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {target} after install. "
        f"Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


def test_install_multiple_packages(conda, empty_env):
    """``conda install click six`` installs multiple packages at once."""
    env_name, env_path = empty_env
    packages = ("click", "six")

    # Execute: install multiple packages in one command
    result = conda("install", "-n", env_name, *packages).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify all packages appear in conda list
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    for pkg in packages:
        assert pkg in installed, (
            f"{pkg} should be present in {env_name} after install. "
            f"Installed packages: {installed.names}"
        )

    # Verify both are physically present on disk, not just in conda-meta.
    # click is a package (dir with __init__.py); six is a single module file.
    python_version = _python_version(installed)
    _assert_package_unpacked(env_path, packages[0], python_version)
    site_packages = site_packages_dir(env_path, python_version)
    assert (site_packages / f"{packages[1]}.py").is_file(), (
        f"{packages[1]} should be unpacked on disk at {site_packages}"
    )


def test_install_from_conda_forge(conda, empty_env):
    """``conda install -c conda-forge <package>`` installs from the conda-forge channel."""
    env_name, env_path = empty_env

    # Execute: install flask from conda-forge
    result = conda("install", "-n", env_name, "-c", "conda-forge", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify flask is installed and came from conda-forge
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get(PACKAGE_NAME)
    assert record is not None, f"{PACKAGE_NAME} record should be found in conda list"
    assert record.channel == "conda-forge", (
        f"{PACKAGE_NAME} should come from conda-forge. Got channel: {record.channel}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


def test_install_override_channels_excludes_defaults(conda, empty_env):
    """``conda install -c conda-forge --override-channels <pkg>`` excludes defaults."""
    env_name, env_path = empty_env
    package_name = "neo4j"

    # defaults is excluded, and since neo4j isn't on conda-forge either, the
    # install must fail, leaving the env untouched.
    failure = conda(
        "install",
        "-n",
        env_name,
        "-c",
        "conda-forge",
        "--override-channels",
        package_name,
    )
    failure.assert_error(code=1, contains="PackagesNotFoundInChannelsError")
    assert not list(env_path.glob("lib/python*")), (
        f"a failed install should not unpack any packages at {env_path}"
    )
    assert not (env_path / "Lib").exists(), (
        f"a failed install should not unpack any packages at {env_path}"
    )


def test_install_channel_fallback_to_defaults(conda, empty_env):
    """``conda install -c conda-forge <pkg>`` falls back to defaults when absent."""
    env_name, env_path = empty_env
    package_name = "neo4j"
    channel_name = "pkgs/main"

    # conda-forge is preferred but neo4j isn't there, so it falls back to
    # defaults and the install succeeds.
    result = conda("install", "-n", env_name, "-c", "conda-forge", package_name).assert_ok()

    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert package_name in installed, (
        f"{package_name} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get(package_name)
    assert record is not None, f"{package_name} record should be found in conda list"
    assert record.channel == channel_name, (
        f"{package_name} should come from defaults ({channel_name}). Got channel: {record.channel}"
    )

    # Verify neo4j is physically present on disk, not just in conda-meta
    _assert_package_unpacked(env_path, package_name, _python_version(installed))


def test_install_specific_version(conda, empty_env):
    """``conda install flask=<version>`` installs the exact pinned (non-latest) version."""
    env_name, env_path = empty_env

    search_result = conda("search", PACKAGE_NAME, "--json").assert_ok()
    versions = sorted(
        {p["version"] for p in search_result.json().get(PACKAGE_NAME, [])},
        key=Version,
    )
    assert len(versions) >= 2, (
        f"need at least 2 {PACKAGE_NAME} versions to verify pinning is respected"
    )
    pinned_version = versions[-2]  # not latest, so we can tell the pin was actually respected

    # Execute: install the pinned version
    result = conda("install", "-n", env_name, f"{PACKAGE_NAME}={pinned_version}").assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Install output should mention {PACKAGE_NAME}. Got:\n{result.stdout}"
    )

    # Verify the exact pinned version is installed
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    record = installed.get(PACKAGE_NAME)
    assert record is not None, f"{PACKAGE_NAME} record should be found in conda list"
    assert record.version == pinned_version, (
        f"{PACKAGE_NAME} version should be {pinned_version}. Got: {record.version}"
    )

    # Verify flask is physically present on disk, not just in conda-meta
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


def test_install_no_deps(conda, empty_env):
    """``conda install --no-deps flask`` installs only flask, no dependencies."""
    env_name, env_path = empty_env

    # Execute: install flask without dependencies
    result = conda("install", "-n", env_name, "--no-deps", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Install output should mention {PACKAGE_NAME}. Got:\n{result.stdout}"
    )

    # Verify flask is the only package installed (env started empty)
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert installed.names == (PACKAGE_NAME,), (
        f"--no-deps should install only {PACKAGE_NAME}. Installed packages: {installed.names}"
    )

    _assert_package_unpacked(env_path, PACKAGE_NAME)


def test_install_dry_run(conda, empty_env):
    """``conda install --dry-run`` shows what would be installed without making changes."""
    env_name, env_path = empty_env
    files_before = sorted(str(p) for p in env_path.rglob("*"))

    # Execute: dry-run install of flask
    result = conda("install", "-n", env_name, "--dry-run", PACKAGE_NAME).assert_ok()

    # Verify output indicates dry run and lists flask
    assert "DryRunExit" in result.stderr or "Dry run" in result.stderr, (
        f"Output should indicate dry run. Got:\n{result.stderr}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Dry-run output should mention {PACKAGE_NAME} as a candidate. Got:\n{result.stdout}"
    )

    # Verify flask was not installed in conda's metadata
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME not in installed, (
        f"{PACKAGE_NAME} should NOT be installed after a dry run. "
        f"Installed packages: {installed.names}"
    )

    # Verify nothing was written to disk either (not just absent from metadata)
    files_after = sorted(str(p) for p in env_path.rglob("*"))
    assert files_after == files_before, (
        f"dry run should not write any files to {env_path}. "
        f"Before: {files_before}, after: {files_after}"
    )


def test_install_reports_full_details(conda, empty_env):
    """``conda install`` output reports the actual channel, platform, and environment location."""
    env_name, env_path = empty_env

    # Ground truth: the platform and channel this conda is actually configured for.
    info_result = conda("info", "--json").assert_ok()
    info = CondaInfo.from_json(info_result)
    config_result = conda("config", "--show", "channels", "--json").assert_ok()
    config = ConfigShow.from_json(config_result)

    result = conda("install", "-n", env_name, PACKAGE_NAME).assert_ok()

    assert f"environment location: {env_path}" in result.stdout, (
        f"Install output should report the environment location. Got:\n{result.stdout}"
    )
    assert f"Platform: {info.platform}" in result.stdout, (
        f"Install output should report platform {info.platform!r}. Got:\n{result.stdout}"
    )
    for channel in config.channels:
        assert channel in result.stdout, (
            f"Install output should report channel {channel!r}. Got:\n{result.stdout}"
        )


@pytest.mark.parametrize("solver", ["classic", "libmamba", "rattler"])
def test_install_with_solver(conda, empty_env, solver):
    """``conda install --solver <solver>`` uses the specified solver backend."""
    env_name, env_path = empty_env

    # Execute: install flask using the specified solver
    result = conda("install", "-n", env_name, "--solver", solver, PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify flask appears in conda list
    list_result = conda("list", "-n", env_name).assert_ok()
    installed = PackageList.from_stdout(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


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
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify every installed package (flask + all deps) came from conda-forge only
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    channels = {pkg.channel for pkg in installed}
    assert channels == {"conda-forge"}, (
        f"--strict-channel-priority should pull every package from conda-forge only. "
        f"Got channels: {channels}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


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
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify at least one dependency came from defaults (pkgs/main), proving
    # the strict channel_priority config was overridden
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )
    channels = {pkg.channel for pkg in installed}
    assert channel_name in channels, (
        f"--no-channel-priority should allow deps from defaults ({channel_name}) despite "
        f"channel_priority: strict. Got channels: {channels}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


def test_install_only_deps(conda, empty_env):
    """``conda install --only-deps flask`` installs flask's dependencies but not flask itself."""
    env_name, env_path = empty_env

    # Execute: install only flask's dependencies
    result = conda("install", "-n", env_name, "--only-deps", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify flask itself was NOT installed, but its dependencies were
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    assert PACKAGE_NAME not in installed, (
        f"--only-deps should not install {PACKAGE_NAME} itself. "
        f"Installed packages: {installed.names}"
    )
    assert DEPENDENCY_PACKAGE_NAME in installed, (
        f"--only-deps should install {PACKAGE_NAME}'s dependencies "
        f"(e.g. {DEPENDENCY_PACKAGE_NAME}). Installed packages: {installed.names}"
    )
    assert len(installed) > 1, (
        f"--only-deps should install more than one dependency for {PACKAGE_NAME}. "
        f"Installed packages: {installed.names}"
    )

    # Verify werkzeug is physically present on disk, not just in conda-meta
    _assert_package_unpacked(env_path, DEPENDENCY_PACKAGE_NAME, _python_version(installed))


def test_install_no_pin(conda, empty_env, condarc):
    """``conda install --no-pin flask`` ignores a pinned version and installs the latest."""
    env_name, env_path = empty_env
    pinned_version, latest_version = _pick_second_newest_and_latest(conda, PACKAGE_NAME)
    condarc.write_text(
        dedent(f"""\
        pinned_packages:
          - {PACKAGE_NAME}={pinned_version}
        """)
    )

    # Execute: install flask, overriding the pinned version
    result = conda("install", "-n", env_name, "--no-pin", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify the pin was ignored: the latest version was installed, not the pinned one
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    record = installed.get(PACKAGE_NAME)
    assert record is not None, f"{PACKAGE_NAME} record should be found in conda list"
    assert record.version == latest_version, (
        f"--no-pin should ignore the pinned version ({pinned_version}) and install the latest "
        f"({latest_version}). Got: {record.version}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


@pytest.mark.parametrize("flag", ["--no-update-deps", "--freeze-installed"])
def test_install_freeze_deps(conda, empty_env, flag):
    """``conda install --no-update-deps``/``--freeze-installed`` freezes installed deps."""
    env_name, env_path = empty_env
    old_werkzeug_version, latest_werkzeug_version = _pick_second_newest_and_latest(
        conda, DEPENDENCY_PACKAGE_NAME
    )
    # Precondition: the seeded version must actually be upgradable, otherwise this test
    # can't tell an implementation that ignores {flag} from one that honors it (there'd be
    # nothing to freeze either way).
    assert Version(old_werkzeug_version) < Version(latest_werkzeug_version), (
        f"test precondition: seeded {DEPENDENCY_PACKAGE_NAME} version {old_werkzeug_version} "
        f"must be older than the latest ({latest_werkzeug_version})"
    )
    pkg_spec = f"{DEPENDENCY_PACKAGE_NAME}={old_werkzeug_version}"

    # Seed: pre-install an old werkzeug (flask's dependency) in the env under test
    conda("install", "-n", env_name, pkg_spec).assert_ok()

    # Execute: install flask, freezing already-installed dependencies
    result = conda("install", "-n", env_name, flag, PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify werkzeug was NOT upgraded (frozen), and flask was still installed
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    werkzeug = installed.get(DEPENDENCY_PACKAGE_NAME)
    assert werkzeug is not None, f"{DEPENDENCY_PACKAGE_NAME} record should be found in conda list"
    assert werkzeug.version == old_werkzeug_version, (
        f"{flag} should not upgrade the already-installed {DEPENDENCY_PACKAGE_NAME} "
        f"({old_werkzeug_version}). Got: {werkzeug.version}"
    )
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


def test_install_update_deps(conda, empty_env):
    """``conda install --update-deps flask`` updates already-installed dependencies."""
    env_name, env_path = empty_env
    old_werkzeug_version, _ = _pick_second_newest_and_latest(conda, DEPENDENCY_PACKAGE_NAME)

    # Seed: pre-install an old werkzeug (flask's dependency)
    pkg_spec = f"{DEPENDENCY_PACKAGE_NAME}={old_werkzeug_version}"
    conda("install", "-n", env_name, pkg_spec).assert_ok()

    # Execute: install flask, updating already-installed dependencies
    result = conda("install", "-n", env_name, "--update-deps", PACKAGE_NAME).assert_ok()

    # Verify output message
    assert NEW_PKG_INSTALLED_MSG in result.stdout, (
        f"Install output should confirm new packages. Got:\n{result.stdout}"
    )

    # Verify werkzeug WAS upgraded (a strictly newer version, not just "different") beyond
    # the old seeded version
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    werkzeug = installed.get(DEPENDENCY_PACKAGE_NAME)
    assert werkzeug is not None, f"{DEPENDENCY_PACKAGE_NAME} record should be found in conda list"
    assert Version(werkzeug.version) > Version(old_werkzeug_version), (
        f"--update-deps should upgrade the already-installed {DEPENDENCY_PACKAGE_NAME} beyond "
        f"{old_werkzeug_version}. Got: {werkzeug.version}"
    )
    assert PACKAGE_NAME in installed, (
        f"{PACKAGE_NAME} should be present in {env_name} after install. "
        f"Installed packages: {installed.names}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


@pytest.mark.parametrize("flag", ["--update-all", "--all"])
def test_install_update_all(conda, empty_env, flag):
    """``conda install --update-all``/``--all`` updates every installed package."""
    env_name, env_path = empty_env
    # A near-latest flask alone still resolves the newest werkzeug (loose dependency
    # ranges), leaving nothing to update. Pin both packages to their oldest available
    # version instead, so the seeded environment is genuinely stale.
    old_flask_version = _search_versions(conda, PACKAGE_NAME)[0]
    old_werkzeug_version = _search_versions(conda, DEPENDENCY_PACKAGE_NAME)[0]

    # Seed: pre-install the oldest available flask and werkzeug together
    conda(
        "install",
        "-n",
        env_name,
        f"{PACKAGE_NAME}={old_flask_version}",
        f"{DEPENDENCY_PACKAGE_NAME}={old_werkzeug_version}",
    ).assert_ok()

    # Capture the FULL seeded package list (not just flask/werkzeug) so we can verify
    # update-all behavior across every package in the environment, not a cherry-picked
    seed_list = conda("list", "-n", env_name, "--json").assert_ok()
    seeded = PackageList.from_json(seed_list)

    # Execute: update all installed packages
    # NOTE: `conda install` (unlike `conda update`) always requires a package_spec,
    # --file, or --revision -- even with --update-all/--all. Omitting it fails with
    # "too few arguments" (see test_install_fails[update-all-no-spec]).
    conda("install", "-n", env_name, flag, PACKAGE_NAME).assert_ok()

    # Verify no seeded package regressed to an older version, across the WHOLE seeded set
    list_result = conda("list", "-n", env_name, "--json").assert_ok()
    installed = PackageList.from_json(list_result)
    for seeded_record in seeded:
        after_record = installed.get(seeded_record.name)
        assert after_record is not None, (
            f"{seeded_record.name} should still be present in {env_name} after {flag}. "
            f"Installed packages: {installed.names}"
        )
        assert Version(after_record.version) >= Version(seeded_record.version), (
            f"{flag} should never downgrade {seeded_record.name}. "
            f"Seeded: {seeded_record.version}, got: {after_record.version}"
        )

    # Verify both explicitly-stale seeded packages (flask and its dependency werkzeug)
    # were genuinely upgraded, not merely "changed"
    flask = installed.get(PACKAGE_NAME)
    werkzeug = installed.get(DEPENDENCY_PACKAGE_NAME)
    assert flask is not None, f"{PACKAGE_NAME} record should be found in conda list"
    assert werkzeug is not None, f"{DEPENDENCY_PACKAGE_NAME} record should be found in conda list"
    assert Version(flask.version) > Version(old_flask_version), (
        f"{flag} should upgrade {PACKAGE_NAME} beyond {old_flask_version}. Got: {flask.version}"
    )
    assert Version(werkzeug.version) > Version(old_werkzeug_version), (
        f"{flag} should upgrade {DEPENDENCY_PACKAGE_NAME} beyond {old_werkzeug_version}. "
        f"Got: {werkzeug.version}"
    )

    # Verify flask is physically present on disk
    _assert_package_unpacked(env_path, PACKAGE_NAME, _python_version(installed))


# =============================================================================
# Negative test cases
# =============================================================================


@pytest.mark.parametrize(
    ("args", "expected_code", "expected_message"),
    [
        (("totally-fake-package-xyz123",), 1, "PackagesNotFoundInChannelsError"),
        ((), 1, "too few arguments"),
        (("--invalid-flag", PACKAGE_NAME), 2, "unrecognized arguments: --invalid-flag"),
        (("--update-all",), 1, "too few arguments"),
        (
            ("--no-deps", "--only-deps", PACKAGE_NAME),
            2,
            "not allowed with argument",
        ),
    ],
    ids=[
        "nonexistent-package",
        "no-packages",
        "invalid-flag",
        "update-all-no-spec",
        "no-deps-conflicts-only-deps",
    ],
)
def test_install_fails(conda, empty_env, args, expected_code, expected_message):
    """``conda install`` fails with the expected exit code and message."""
    env_name, _ = empty_env

    result = conda("install", "-n", env_name, *args)
    result.assert_error(code=expected_code, contains=expected_message)


def test_install_nonexistent_env_fails(conda):
    """``conda install -n <nonexistent-env>`` fails with an environment-not-found error."""
    result = conda("install", "-n", "totally-nonexistent-env-xyz", PACKAGE_NAME)
    result.assert_error(code=1, contains="EnvironmentLocationNotFound")


def test_install_invalid_solver_fails(conda):
    """``conda install --solver <invalid>`` fails with invalid choice error."""
    result = conda("install", "--solver", "fake_solver", PACKAGE_NAME)
    result.assert_error(code=2, contains="invalid choice")
