# SPDX-License-Identifier: BSD-3-Clause
"""Failure coverage for ``conda list``."""

from __future__ import annotations

# =============================================================================
# Negative test cases
# =============================================================================


def test_list_rejects_unsupported_option(conda):
    """``conda list`` reports unsupported options on stderr."""
    conda("list", "--not-a-real-option").assert_error(
        code=2,
        contains="unrecognized arguments: --not-a-real-option",
    )


def test_list_rejects_name_and_prefix_together(conda, make_env):
    """``conda list`` rejects mutually exclusive environment selectors."""
    env_name, env_prefix = make_env()
    conda("list", "--name", env_name, "--prefix", env_prefix).assert_error(
        code=2,
        contains="not allowed with argument",
    )


def test_list_rejects_missing_named_environment(conda):
    """``conda list --name`` rejects an environment that does not exist."""
    conda("list", "--name", "definitely-missing-e2e-environment").assert_error(
        code=1,
        contains="EnvironmentLocationNotFound",
    )
