# SPDX-License-Identifier: BSD-3-Clause
"""Assertion helpers for ``conda info --json`` fields not tied to a single test.

Kept local to the ``info`` test package since these assertions are only
needed here for sandbox directories, host invariants, and activation env vars.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conda_e2e.parsers.info import CondaInfo

_CHANNEL_URL_RE = re.compile(r"^https?://")


def assert_sandboxed(info: CondaInfo, isolated_env_vars: dict[str, str]) -> None:
    """Assert the sandbox dirs from ``isolated_env_vars`` are the ones conda reports.

    Every path here comes from the per-test sandbox fixture, not a hardcoded
    value, so this holds regardless of where the test runs.
    """
    assert Path(isolated_env_vars["CONDA_PKGS_DIRS"]) in info.pkgs_dirs
    assert Path(isolated_env_vars["CONDA_ENVS_DIRS"]) in info.envs_dirs
    assert info.rc_path == Path(isolated_env_vars["CONDARC"])
    assert info.user_rc_path == Path(isolated_env_vars["CONDARC"])


def assert_host_invariants(info: CondaInfo, root_prefix: Path, conda_version: str) -> None:
    """Assert fields that describe the host/install and never vary with activation.

    Values are derived from the process (``os.getuid``/``os.getgid``), from
    ``root_prefix`` (``av_data_dir``, ``sys_rc_path`` live under it), or from
    ``conda_version`` reported alongside, never hardcoded.
    """
    if hasattr(os, "getuid") and info.uid is not None:  # os.getuid is POSIX-only
        assert info.uid == os.getuid()
    if hasattr(os, "getgid") and info.gid is not None:  # os.getgid is POSIX-only
        assert info.gid == os.getgid()

    assert info.av_data_dir == root_prefix / "etc" / "conda"
    assert info.sys_rc_path == root_prefix / ".condarc"

    # conda_prefix is where the conda *tool itself* is installed (the base env),
    # which is root_prefix regardless of which env is currently active.
    assert info.conda_prefix == root_prefix
    assert info.conda_location.startswith(str(info.conda_prefix))
    assert info.conda_env_version == conda_version

    # conda always discovers its own base install among known envs.
    assert root_prefix in info.envs

    # conda-build may be "not installed"/"error" when absent; just require non-empty text.
    assert info.conda_build_version

    assert info.python_version.count(".") >= 2  # e.g. "3.12.7.final.0"
    # "3.12.7.final.0" -> "3.12.7" must prefix "3.12.7 | packaged by ...".
    major_minor_micro = ".".join(info.python_version.split(".")[:3])
    assert info.sys_version.startswith(major_minor_micro)

    # sys_rc_path always exists on disk, so it's always among the populated config files.
    assert info.sys_rc_path in info.config_files

    assert info.solver_name  # e.g. "libmamba" / "classic"
    assert isinstance(info.solver_default, bool)
    assert info.solver_user_agent in info.user_agent

    assert info.virtual_pkgs
    for pkg in info.virtual_pkgs:
        assert len(pkg) == 3
        name, version, build = pkg
        assert name.startswith("__")
        assert version
        assert build is not None

    assert info.channels
    for channel in info.channels:
        assert _CHANNEL_URL_RE.match(channel), f"not a URL-shaped channel: {channel}"

    assert info.user_agent.startswith("conda/")

    assert isinstance(info.root_writable, bool)
    assert isinstance(info.offline, bool)
    assert info.platform  # non-empty, e.g. "osx-arm64" / "linux-64" / "win-64"

    assert info.requests_version
    assert isinstance(info.site_dirs, tuple)

    # conda's own interpreter is always the base env's python, unaffected by activation.
    assert info.sys_prefix == str(info.conda_prefix)
    assert info.sys_executable.startswith(str(info.conda_prefix))


def assert_activation_env_vars(
    info: CondaInfo,
    *,
    default_env: str | None,
    prefix: Path | str | None,
    shlvl: int,
    prompt_modifier: str | None = None,
) -> None:
    """Assert the key activation-related env vars exposed by ``conda info --json``."""
    assert info.env_vars.get("CONDA_DEFAULT_ENV") == default_env
    expected_prefix = str(prefix) if prefix is not None else None
    assert info.env_vars.get("CONDA_PREFIX") == expected_prefix
    assert info.env_vars.get("CONDA_SHLVL") == str(shlvl)
    if prompt_modifier is not None:
        assert info.env_vars.get("CONDA_PROMPT_MODIFIER") == prompt_modifier
