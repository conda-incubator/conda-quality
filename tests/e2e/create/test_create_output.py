# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda create Output, Prompt, and Flow Control options."""

from __future__ import annotations

import pytest
from helpers import (
    PACKAGE_NAME,
    assert_env_created,
    assert_env_not_created,
)

from conda_e2e.utils import unique_env_name

# =============================================================================
# Prompt and confirmation tests (-y, --yes)
# =============================================================================


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
    )
    assert "Proceed ([y]/n)?" in result.stdout, (
        f"Expected confirmation prompt. Got:\n{result.stdout}"
    )
    assert_env_not_created(envs_dir, env_name)


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


def test_create_json_output(conda, envs_dir):
    """``conda create --json`` produces valid JSON output."""
    env_name = unique_env_name()

    result = conda("create", "-n", env_name, PACKAGE_NAME, "--json").assert_ok()

    data = result.json()
    assert data.get("success") is True, f"Expected success=True in JSON. Got: {data}"
    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)


# =============================================================================
# Dry run tests (--dry-run, -d)
# =============================================================================


@pytest.mark.parametrize("flag", ["--dry-run", "-d"], ids=["long", "short"])
def test_create_dry_run_does_not_create_env(conda, envs_dir, flag):
    """``conda create --dry-run`` / ``-d`` shows plan without creating environment."""
    env_name = unique_env_name()

    result = conda("create", "-n", env_name, PACKAGE_NAME, flag).assert_ok()

    # Dry run exit message goes to stderr
    assert "DryRunExit" in result.stderr or "Dry run" in result.stderr, (
        f"Expected dry run indicator on stderr. Got:\n{result.stderr}"
    )
    # Package plan goes to stdout
    assert PACKAGE_NAME in result.stdout, (
        f"Dry-run output should mention {PACKAGE_NAME} as a candidate. Got:\n{result.stdout}"
    )
    # But should NOT create the environment
    assert_env_not_created(envs_dir, env_name)


# =============================================================================
# Verbosity tests (-v, -q)
# =============================================================================


@pytest.mark.parametrize("flag", ["-q", "--quiet"], ids=["short", "long"])
def test_create_quiet_suppresses_output(conda, envs_dir, flag):
    """``conda create -q`` / ``--quiet`` suppresses progress output.

    Quiet mode should produce less stdout than a baseline run without the flag.
    Both environments are verified to ensure the comparison is valid.
    """
    quiet_env = unique_env_name()
    baseline_env = unique_env_name()

    # Run baseline first, then quiet - order matters for cache consistency
    baseline_result = conda("create", "-n", baseline_env, PACKAGE_NAME).assert_ok()
    quiet_result = conda("create", "-n", quiet_env, PACKAGE_NAME, flag).assert_ok()

    # Verify both environments were created
    assert_env_created(conda, envs_dir, baseline_env, expected_package=PACKAGE_NAME)
    assert_env_created(conda, envs_dir, quiet_env, expected_package=PACKAGE_NAME)

    # Quiet mode should produce less output than baseline
    assert len(quiet_result.stdout) <= len(baseline_result.stdout), (
        f"Quiet mode ({len(quiet_result.stdout)} chars) should produce no more output "
        f"than baseline ({len(baseline_result.stdout)} chars)"
    )


@pytest.mark.parametrize(("flag", "level"), [("-vv", "INFO"), ("-vvv", "DEBUG")])
def test_create_verbose_produces_logging(conda, envs_dir, flag, level):
    """``conda create -vv/-vvv`` produces INFO/DEBUG logging on stderr."""
    env_name = unique_env_name()

    result = conda("create", "-n", env_name, flag, PACKAGE_NAME).assert_ok()

    assert level in result.stderr, (
        f"Verbose mode ({flag}) should produce {level} logging on stderr. "
        f"Got stderr:\n{result.stderr[:500]}"
    )

    assert_env_created(conda, envs_dir, env_name, expected_package=PACKAGE_NAME)
