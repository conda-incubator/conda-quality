# SPDX-License-Identifier: BSD-3-Clause
"""E2E tests for conda activate flag.

Currently, this module contains just one test to show how to use conda
test automation framework for shell-dependent commands.
"""

from __future__ import annotations

from conda_e2e.parsers.info import parse_info_json
from conda_e2e.shells import conda_activate_script
from conda_e2e.utils import unique_env_name


def test_activate_makes_env_current(shell, conda, conda_exe):
    """``conda activate`` is shell-specific -- so it uses the ``shell`` fixture.

    Pattern: create the env, then activate it through the shell and confirm conda
    reports it as active. This test runs once per shell available on the OS.
    """
    name = unique_env_name()
    conda("create", "-n", name).assert_ok()

    script = conda_activate_script(shell.shell, name, "conda info --json", conda_exe=conda_exe)
    result = shell(script).assert_ok()
    assert parse_info_json(result).active_prefix_name == name
