# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for the experimental ``conda package`` command."""

from __future__ import annotations

import json
import tarfile

from package_helpers import (
    PACKAGE_METADATA_BUILD,
    PACKAGE_METADATA_NAME,
    PACKAGE_METADATA_VERSION,
    assert_archive_contains,
    create_untracked_file,
    option_tokens,
    package_archive_path,
)

# =============================================================================
# Positive test cases
# =============================================================================


# -----------------------------------------------------------------------------
# Help and argument validation
# -----------------------------------------------------------------------------


def test_package_help(conda):
    """``conda package --help`` documents all flags and option groups."""
    expected_help = {
        "text": (
            "usage: conda package",
            "Create low-level conda packages. (EXPERIMENTAL)",
        ),
        "headers": (
            "options:",
            "Target Environment Specification:",
        ),
        "flags": (
            "-h",
            "--help",
            "-w",
            "--which",
            "-r",
            "--reset",
            "-u",
            "--untracked",
            "--pkg-name",
            "--pkg-version",
            "--pkg-build",
            "-n",
            "--name",
            "-p",
            "--prefix",
        ),
    }

    output = conda("package", "--help").assert_ok().stdout

    missing = {}
    for section, items in expected_help.items():
        absent = [item for item in items if item not in output]
        if absent:
            missing[section] = absent

    assert not missing, f"Help missing items by section: {missing}\nOutput:\n{output}"

    # Compare the complete expected-versus-actual option set so both missing and newly added
    # options fail clearly without depending on argparse's version-specific metavar rendering.
    expected_options = set(expected_help["flags"])
    actual_options = option_tokens(output)
    assert actual_options == expected_options, (
        f"Missing options: {sorted(expected_options - actual_options)}. "
        f"Unexpected options: {sorted(actual_options - expected_options)}.\nOutput:\n{output}"
    )


def test_package_help_short_flag_matches_long_form(conda):
    """``conda package -h`` renders identically to ``--help``.

    Kept as its own test (rather than appended to ``test_package_help``) because there's
    no setup to reuse: unlike the ``-w``/``-r``/``-n`` equivalence checks elsewhere in this
    module, which reuse an already-built installed package, populated environment, or
    created archive, this only needs two independent, stateless CLI calls.
    """
    long_form = conda("package", "--help").assert_ok().stdout
    short_form = conda("package", "-h").assert_ok().stdout

    assert short_form == long_form, "-h should match --help output byte-for-byte"


# -----------------------------------------------------------------------------
# File-ownership lookup (--which)
# -----------------------------------------------------------------------------


def test_package_which_reports_owners_for_multiple_paths(conda, empty_env):
    """``--which``/``-w`` report each tracked path's owner."""
    package_names = ("zlib", "xz")
    _, env_prefix = empty_env
    conda("install", "--prefix", env_prefix, *package_names).assert_ok()

    owned_files = []
    for package_name in package_names:
        manifest_paths = list((env_prefix / "conda-meta").glob(f"{package_name}-*.json"))
        assert manifest_paths, f"Expected a conda-meta record for {package_name!r}"
        manifest = json.loads(manifest_paths[0].read_text())
        assert manifest["files"], f"Expected {package_name!r} to ship at least one file: {manifest}"
        owned_files.append(env_prefix / manifest["files"][0])

    long_form = conda("package", "--prefix", env_prefix, "--which", *owned_files).assert_ok()
    short_form = conda("package", "-p", env_prefix, "-w", *owned_files).assert_ok()

    assert short_form.stdout == long_form.stdout, (
        "-p/-w should match --prefix/--which output byte-for-byte"
    )

    for package_name in package_names:
        assert package_name in long_form.stdout, (
            f"Expected {package_name!r} among owners for {owned_files}:\n{long_form.stdout}"
        )


# -----------------------------------------------------------------------------
# Untracked-file operations
# -----------------------------------------------------------------------------


def test_package_untracked_lists_planted_file(conda, empty_env):
    """``conda package --untracked`` reports files outside the manifest."""
    _, env_prefix = empty_env
    untracked_file = create_untracked_file(env_prefix)

    result = conda("package", "--prefix", env_prefix, "--untracked").assert_ok()

    assert untracked_file.name in result.stdout, (
        f"Expected {untracked_file.name!r}:\n{result.stdout}"
    )


def test_package_short_target_and_operation_aliases_match_long_forms(conda, empty_env):
    """``-p``/``-u`` produce the same untracked report as ``--prefix``/``--untracked``."""
    _, env_prefix = empty_env
    create_untracked_file(env_prefix)

    long_form = conda("package", "--prefix", env_prefix, "--untracked").assert_ok()
    short_form = conda("package", "-p", env_prefix, "-u").assert_ok()

    assert short_form.stdout == long_form.stdout


def test_package_reset_removes_untracked_file(conda, empty_env):
    """``conda package --reset``/``-r`` remove untracked files but preserve tracked state.

    Asserting only that the environment directory still exists would pass even for a
    broken implementation that deletes every tracked file underneath it; assert conda's
    own ``conda-meta/history`` record (always created by ``conda create``) survives too.
    """
    _, env_prefix = empty_env
    history_file = env_prefix / "conda-meta" / "history"
    assert history_file.is_file(), f"Expected {history_file} to exist before reset"

    untracked_file = create_untracked_file(env_prefix)
    before_reset = conda("package", "--prefix", env_prefix, "--untracked").assert_ok()
    assert untracked_file.name in before_reset.stdout, (
        f"Expected {untracked_file.name!r} before reset:\n{before_reset.stdout}"
    )

    conda("package", "--prefix", env_prefix, "--reset").assert_ok()

    assert not untracked_file.exists(), "--reset should remove the untracked file"
    assert env_prefix.is_dir(), "--reset should preserve the environment directory"
    assert history_file.is_file(), "--reset should preserve tracked conda-meta records"

    # -r is argparse's alias for --reset; repeat on a second planted file (--reset also
    # removes the now-empty `nested/` dir, so `create_untracked_file` can recreate it) to
    # prove -r has the same effect, not just the same help text.
    second_untracked_file = create_untracked_file(env_prefix)
    conda("package", "-p", env_prefix, "-r").assert_ok()

    assert not second_untracked_file.exists(), "-r should remove the untracked file"
    assert history_file.is_file(), "-r should preserve tracked conda-meta records"


# -----------------------------------------------------------------------------
# Package creation
# -----------------------------------------------------------------------------


def test_package_metadata_flags_set_archive_name_and_embedded_metadata(conda, empty_env, tmp_path):
    """``--pkg-name``/``--pkg-version``/``--pkg-build`` set the created package's identity.

    Each flag's documented contract is that it "designates" that field of the
    package being created; the derived archive filename is only a presentation
    detail of that identity. Using distinct values for all three flags in one
    invocation unambiguously attributes each embedded ``info/index.json`` field
    to its own flag, so the three contracts are proven together without
    duplicating environment/archive setup per flag.
    """
    _, env_prefix = empty_env
    archive = package_archive_path(tmp_path)

    conda(
        "package",
        "--prefix",
        env_prefix,
        "--pkg-name",
        PACKAGE_METADATA_NAME,
        "--pkg-version",
        PACKAGE_METADATA_VERSION,
        "--pkg-build",
        PACKAGE_METADATA_BUILD,
        cwd=tmp_path,
    ).assert_ok()

    assert archive.is_file(), f"Expected package archive at {archive}"
    with tarfile.open(archive) as created_package:
        index_file = created_package.extractfile("info/index.json")
        assert index_file is not None, "info/index.json should be present in the archive"
        index = json.loads(index_file.read())

    assert index["name"] == PACKAGE_METADATA_NAME, (
        f"Expected embedded package name {PACKAGE_METADATA_NAME!r}, got {index['name']!r}"
    )
    assert index["version"] == PACKAGE_METADATA_VERSION, (
        f"Expected embedded package version {PACKAGE_METADATA_VERSION!r}, got {index['version']!r}"
    )
    assert index["build"] == PACKAGE_METADATA_BUILD, (
        f"Expected embedded package build {PACKAGE_METADATA_BUILD!r}, got {index['build']!r}"
    )
    assert index["build_number"] == int(PACKAGE_METADATA_BUILD), (
        f"Expected embedded build_number {int(PACKAGE_METADATA_BUILD)}, got "
        f"{index['build_number']!r}"
    )


def test_package_name_target_creates_archive(conda, empty_env, tmp_path):
    """``conda package --name``/``-n`` select the named environment when creating a package.

    ``--prefix`` ("full path to environment location") is the canonical, more heavily
    exercised form used throughout this module, including the strongest embedded-metadata
    check in ``test_package_metadata_flags_set_archive_name_and_embedded_metadata``. This
    test covers the other half of the mutually exclusive "Target Environment Specification"
    group, ``--name``/``-n`` ("name of environment"), which conda resolves by looking the
    name up across configured ``envs_dirs`` instead of taking a path directly.

    An empty environment gives ``--name`` nothing distinctive to select: an archive would
    exist even if ``--name`` silently resolved to the wrong (also-empty) environment, so a
    unique marker file is planted in the named environment and asserted present inside the
    created archive, proving the *correct* environment was targeted. This does not assert
    byte-for-byte equivalence against a ``--prefix`` invocation of the same command.
    """
    env_name, env_prefix = empty_env
    marker_file = create_untracked_file(env_prefix)
    relative_marker = marker_file.relative_to(env_prefix).as_posix()
    archive = package_archive_path(tmp_path)

    conda(
        "package",
        "--name",
        env_name,
        "--pkg-name",
        PACKAGE_METADATA_NAME,
        "--pkg-version",
        PACKAGE_METADATA_VERSION,
        "--pkg-build",
        PACKAGE_METADATA_BUILD,
        cwd=tmp_path,
    ).assert_ok()

    assert archive.is_file(), f"Expected package archive at {archive}"
    assert_archive_contains(archive, relative_marker)

    # -n is argparse's alias for --name; repeat with a distinct package identity (so the
    # archive filename doesn't collide with the one above) to prove it resolves the same
    # environment, not just that it shares help text.
    short_form_name = f"{PACKAGE_METADATA_NAME}-short-name"
    short_form_archive = package_archive_path(tmp_path, short_form_name)

    conda(
        "package",
        "-n",
        env_name,
        "--pkg-name",
        short_form_name,
        "--pkg-version",
        PACKAGE_METADATA_VERSION,
        "--pkg-build",
        PACKAGE_METADATA_BUILD,
        cwd=tmp_path,
    ).assert_ok()

    assert short_form_archive.is_file(), f"Expected package archive at {short_form_archive}"
    assert_archive_contains(short_form_archive, relative_marker)


# =============================================================================
# Edge cases
# =============================================================================


def test_package_which_has_no_output_for_untracked_file(conda, empty_env):
    """``conda package --which`` finds no owner for an untracked file."""
    _, env_prefix = empty_env
    untracked_file = create_untracked_file(env_prefix)

    result = conda("package", "--prefix", env_prefix, "--which", untracked_file).assert_ok()

    assert not result.stdout.strip(), f"Untracked file unexpectedly had an owner:\n{result.stdout}"


# =============================================================================
# Negative test cases
# =============================================================================


def test_package_rejects_unsupported_option(conda):
    """``conda package`` reports unsupported options on stderr."""
    conda("package", "--not-a-real-option").assert_error(
        code=2,
        contains="unrecognized arguments: --not-a-real-option",
    )


def test_package_rejects_name_and_prefix_together(conda, empty_env):
    """``conda package`` rejects mutually exclusive environment selectors."""
    env_name, env_prefix = empty_env

    conda("package", "--name", env_name, "--prefix", env_prefix, "--untracked").assert_error(
        code=2,
        contains="not allowed with argument",
    )
