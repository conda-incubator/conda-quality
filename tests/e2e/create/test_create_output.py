# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Output, Prompt, and Flow Control options."""

from __future__ import annotations

import pytest
from create_asserts import (
    PACKAGE_NAME,
    assert_env_created,
    assert_env_not_created,
)

from conda_e2e.parsers.install import InstallResult
from conda_e2e.utils import unique_env_name

# =============================================================================
# Prompt and confirmation tests (-y, --yes)
# =============================================================================


@pytest.mark.covers(198)
def test_create_prompts_for_confirmation(conda, envs_dir):
    """``conda create`` prompts and aborts when the user declines.

    With the fixture's auto-yes disabled and the user declining via stdin,
    conda must show the prompt and leave no environment behind.
    """
    env_name = unique_env_name()
    result = conda(
        "create",
        "-n",
        env_name,
        PACKAGE_NAME,
        extra_env={"CONDA_ALWAYS_YES": "no"},
        stdin="n\n",
    ).assert_ok()
    assert "Proceed ([y]/n)?" in result.stdout, (
        f"Expected confirmation prompt. Got:\n{result.stdout}"
    )
    assert "CondaSystemExit: Exiting" in result.stderr, (
        f"Declining should exit cleanly via CondaSystemExit. Got stderr:\n{result.stderr}"
    )
    assert_env_not_created(envs_dir, env_name)


@pytest.mark.covers(151)
def test_create_yes_flag_skips_confirmation(conda, envs_dir):
    """``conda create -y`` proceeds without prompting.

    Even with auto-yes disabled and no stdin to answer a prompt, the ``-y`` flag
    makes conda proceed without blocking on confirmation.
    """
    env_name = unique_env_name()
    result = conda(
        "create",
        "-n",
        env_name,
        PACKAGE_NAME,
        "-y",
        extra_env={"CONDA_ALWAYS_YES": "no"},
    ).assert_ok()
    assert "Proceed ([y]/n)?" not in result.stdout, (
        f"-y should skip confirmation prompt. Got:\n{result.stdout}"
    )
    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)


# =============================================================================
# Output format tests (--json)
# =============================================================================


@pytest.mark.covers(173)
def test_create_json_output(conda, envs_dir):
    """``conda create --json`` produces valid JSON output."""
    env_name = unique_env_name()

    result = conda("create", "-n", env_name, PACKAGE_NAME, "--json").assert_ok()

    create_result = InstallResult.from_json(result)
    assert create_result.success, "JSON create result should report success."
    assert any(package.name == PACKAGE_NAME for package in create_result.link_packages), (
        f"actions.LINK should contain {PACKAGE_NAME}. Got: "
        f"{[package.name for package in create_result.link_packages]}"
    )
    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)


# =============================================================================
# Dry run tests (--dry-run, -d)
# =============================================================================


@pytest.mark.covers(168)
def test_create_dry_run_does_not_create_env(conda, envs_dir, cache_dir):
    """``conda create --dry-run`` shows plan without creating environment.

    ``-d`` is the same argparse alias for the same option, so only one flag
    variant is exercised here.
    """
    env_name = unique_env_name()

    result = conda("create", "-n", env_name, PACKAGE_NAME, "--dry-run").assert_ok()

    # Dry run exit message goes to stderr
    assert "DryRunExit" in result.stderr, (
        f"Expected dry run indicator on stderr. Got:\n{result.stderr}"
    )
    assert PACKAGE_NAME in result.stdout, (
        f"Dry-run output should mention {PACKAGE_NAME} as a candidate. Got:\n{result.stdout}"
    )
    assert_env_not_created(envs_dir, env_name)
    # Should NOT even download the package: conda fetches into the cache before
    # linking, so an env-only check can't tell dry-run apart from --download-only.
    cached = list(cache_dir.glob(f"{PACKAGE_NAME}-*"))
    assert not cached, f"--dry-run should not download {PACKAGE_NAME} into the cache. Got: {cached}"


# =============================================================================
# Verbosity tests (-v, -q)
# =============================================================================


@pytest.mark.covers(176)
def test_create_quiet_suppresses_output(conda, envs_dir):
    """``conda create --quiet`` suppresses progress output.

    ``-q`` is an alias for ``--quiet``, so only one variant is tested.

    Comparing output length against a non-quiet run is unreliable: with a warm
    cache, both outputs shrink to similar sizes. Instead, check whether specific
    banner lines appear. An empty env suffices, since conda prints them anyway.
    """
    baseline_env = unique_env_name()
    quiet_env = unique_env_name()

    baseline_result = conda("create", "-n", baseline_env).assert_ok()
    quiet_result = conda("create", "-n", quiet_env, "--quiet").assert_ok()

    assert "Downloading and Extracting Packages" in baseline_result.stdout, (
        f"Baseline (no quiet flag) should show the progress banner. Got:\n{baseline_result.stdout}"
    )
    assert "To activate this environment" in baseline_result.stdout, (
        f"Baseline (no quiet flag) should show the activation hint. Got:\n{baseline_result.stdout}"
    )

    assert "Downloading and Extracting Packages" not in quiet_result.stdout, (
        f"--quiet should suppress the progress banner. Got:\n{quiet_result.stdout}"
    )
    assert "To activate this environment" not in quiet_result.stdout, (
        f"--quiet should suppress the activation hint. Got:\n{quiet_result.stdout}"
    )

    assert_env_created(conda, envs_dir, baseline_env)
    assert_env_created(conda, envs_dir, quiet_env)


@pytest.mark.covers(175)
@pytest.mark.parametrize(("flag", "level"), [("-vv", "INFO"), ("-vvv", "DEBUG")])
def test_create_verbose_produces_logging(conda, envs_dir, flag, level):
    """``conda create -vv/-vvv`` produces INFO/DEBUG logging on stderr.

    An empty env is enough: conda logs plenty of INFO/DEBUG records (repodata
    fetch, solver setup, etc.) even with no package to download.
    """
    env_name = unique_env_name()

    result = conda("create", "-n", env_name, flag).assert_ok()

    assert level in result.stderr, (
        f"Verbose mode ({flag}) should produce {level} logging on stderr. "
        f"Got stderr:\n{result.stderr[:500]}"
    )

    assert_env_created(conda, envs_dir, env_name)
