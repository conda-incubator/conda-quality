# SPDX-License-Identifier: BSD-3-Clause
"""Assertion helpers for ``conda info``/``conda info --json`` fields not tied to a single test.

Kept local to the ``info`` test package since these assertions are only
needed here: cross-checking the plain-text renderer against ``--json``, and
sandbox directories, host invariants, and activation env vars.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from conda_e2e.parsers.env import PlainEnvList
from conda_e2e.utils import is_same_path

if TYPE_CHECKING:
    from pathlib import Path

    from conda_e2e.parsers.env import EnvRecord
    from conda_e2e.parsers.info import CondaInfo, PlainCondaInfo
    from conda_e2e.result import CommandResult

# =============================================================================
# Plain/JSON renderer alignment helpers
# =============================================================================

_CHANNEL_URL_RE = re.compile(r"^https?://")
# Plain text redacts values in single-letter user-agent tokens, while JSON keeps them.
_USER_AGENT_TOKEN_RE = re.compile(r" ([a-z])/([^ ]+)")


def _redact_user_agent_tokens(user_agent: str) -> str:
    """Apply the plain-text renderer's own token redaction to a user-agent string."""
    return _USER_AGENT_TOKEN_RE.sub(r" \1/.", user_agent)


def assert_plain_and_json_info_match(plain: PlainCondaInfo, info: CondaInfo) -> None:
    """Assert every field the plain renderer shows agrees with ``conda info --json``.

    The JSON-derived fields are already proven correct (sandboxing, snapshot
    invariants, activation state) by the existing ``--json`` tests, so this
    only cross-checks that the plain-text renderer reports the same values —
    it does not re-derive or re-assert those invariants itself.
    """
    assert plain.active_env_name == info.active_prefix_name
    assert plain.active_env_location == info.active_prefix
    assert plain.shell_level == info.conda_shlvl
    assert plain.user_rc_path == info.user_rc_path
    assert plain.config_files == info.config_files
    assert plain.conda_version == info.conda_version
    assert plain.conda_build_version == info.conda_build_version
    assert plain.python_version == info.python_version
    assert plain.solver_name == info.solver_name
    assert plain.solver_default == info.solver_default
    assert plain.virtual_pkgs == info.virtual_pkgs
    assert plain.root_prefix == info.root_prefix
    assert plain.root_writable == info.root_writable
    assert plain.av_data_dir == info.av_data_dir
    assert plain.av_metadata_url_base == info.av_metadata_url_base
    assert plain.channels == info.channels
    assert plain.pkgs_dirs == info.pkgs_dirs
    assert plain.envs_dirs == info.envs_dirs
    assert plain.platform == info.platform
    assert plain.user_agent == _redact_user_agent_tokens(info.user_agent)
    assert plain.uid == info.uid
    assert plain.gid == info.gid
    assert plain.netrc_file == info.netrc_file
    assert plain.offline == info.offline


# =============================================================================
# Info helpers
# =============================================================================


def assert_sandboxed(info: CondaInfo, isolated_env_vars: dict[str, str]) -> None:
    """Assert the sandbox dirs from ``isolated_env_vars`` are the ones conda reports.

    Every path here comes from the per-test sandbox fixture, not a hardcoded
    value, so this holds regardless of where the test runs.
    """
    assert any(is_same_path(isolated_env_vars["CONDA_PKGS_DIRS"], path) for path in info.pkgs_dirs)
    assert any(is_same_path(isolated_env_vars["CONDA_ENVS_DIRS"], path) for path in info.envs_dirs)
    assert is_same_path(info.rc_path, isolated_env_vars["CONDARC"])
    assert is_same_path(info.user_rc_path, isolated_env_vars["CONDARC"])


def assert_info_self_consistent(info: CondaInfo) -> None:
    """Assert relationships among values from one ``conda info`` snapshot.

    Values are derived from the process (``os.getuid``/``os.getgid``), from
    fields in this snapshot (for example, ``root_prefix`` and
    ``conda_version``), or from the reported values' known structure.
    """
    if hasattr(os, "getuid") and info.uid is not None:  # os.getuid is POSIX-only
        assert info.uid == os.getuid()
    if hasattr(os, "getgid") and info.gid is not None:  # os.getgid is POSIX-only
        assert info.gid == os.getgid()

    assert info.av_data_dir == info.root_prefix / "etc" / "conda"
    assert info.sys_rc_path == info.root_prefix / ".condarc"

    # conda_prefix is where the conda *tool itself* is installed (the base env),
    # which is root_prefix regardless of which env is currently active.
    assert info.conda_prefix == info.root_prefix
    assert info.conda_location.is_relative_to(info.conda_prefix)
    assert info.conda_env_version == info.conda_version

    # conda always discovers its own base install among known envs.
    assert info.root_prefix in info.envs

    # conda-build may be "not installed"/"error" when absent; just require non-empty text.
    assert info.conda_build_version

    assert info.python_version.count(".") >= 2  # e.g. "3.12.7.final.0"
    # "3.12.7.final.0" -> "3.12.7" must prefix "3.12.7 | packaged by ...".
    major_minor_micro = ".".join(info.python_version.split(".")[:3])
    assert info.sys_version.startswith(major_minor_micro)

    # sys_rc_path always exists on disk, so it's always among the populated config files.
    assert info.sys_rc_path in info.config_files

    assert info.solver_name  # e.g. "libmamba" / "classic"
    assert info.solver_user_agent in info.user_agent

    assert info.virtual_pkgs
    for pkg in info.virtual_pkgs:
        assert len(pkg) == 3
        name, version, build = pkg
        assert name.startswith("__")
        assert version
        assert build is not None

    _assert_channels_are_url_shaped(info.channels)

    assert info.user_agent.startswith("conda/")

    assert info.platform  # non-empty, e.g. "osx-arm64" / "linux-64" / "win-64"

    assert info.requests_version

    # conda's own interpreter is always the base env's python, unaffected by activation.
    assert info.sys_prefix == info.conda_prefix
    assert info.sys_executable.is_relative_to(info.conda_prefix)


def assert_install_fields_unchanged(before: CondaInfo, after: CondaInfo) -> None:
    """Assert install and host fields remain unchanged across activation."""
    assert after.root_prefix == before.root_prefix
    assert after.pkgs_dirs == before.pkgs_dirs
    assert after.envs_dirs == before.envs_dirs
    assert after.config_files == before.config_files
    assert after.rc_path == before.rc_path
    assert after.channels == before.channels
    assert after.virtual_pkgs == before.virtual_pkgs
    assert after.solver_name == before.solver_name
    assert after.av_data_dir == before.av_data_dir
    assert after.uid == before.uid
    assert after.gid == before.gid


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
    assert is_same_path(info.env_vars.get("CONDA_PREFIX"), prefix)
    assert info.env_vars.get("CONDA_SHLVL") == str(shlvl)
    if prompt_modifier is not None:
        assert info.env_vars.get("CONDA_PROMPT_MODIFIER") == prompt_modifier


# =============================================================================
# Environment list helpers
# =============================================================================


def assert_envs_headers_present(output: str, envs_flag: str) -> None:
    """Assert the stable ``conda info --envs`` header lines are present."""
    expected_headers = (
        "# conda environments:",
        "# * -> active",
        "# + -> frozen",
    )
    missing_headers = [header for header in expected_headers if header not in output]
    assert not missing_headers, (
        f"{envs_flag} output missing {missing_headers}. Command output:\n{output}"
    )


def assert_created_env_listed(result: CommandResult, env_name: str, env_path: Path) -> None:
    """Assert the created env is listed with the expected name and prefix path."""
    env_list = PlainEnvList.from_stdout(result)

    assert env_name in env_list
    created_env = env_list.get_by_prefix(env_path)
    assert created_env is not None
    assert created_env.name == env_name


def assert_created_env_json_fields(created_env: EnvRecord, env_name: str, env_path: Path) -> None:
    """Assert stable JSON fields for a newly created environment entry."""
    assert created_env.name == env_name
    assert created_env.created
    assert created_env.last_modified
    assert created_env.base is False
    assert is_same_path(created_env.prefix, env_path)


# =============================================================================
# Channel helpers
# =============================================================================


def _assert_channels_are_url_shaped(channels: tuple[str, ...]) -> None:
    """Assert every reported channel has a URL-like shape."""
    assert channels
    for channel in channels:
        assert _CHANNEL_URL_RE.match(channel), f"not a URL-shaped channel: {channel}"


def assert_unsafe_channels_are_root_urls(channels: list[str] | tuple[str, ...]) -> None:
    """Assert unsafe channels are URL roots, not platform/noarch-expanded subdirs."""
    _assert_channels_are_url_shaped(tuple(channels))
    assert all("/noarch" not in channel for channel in channels)
    assert all("/linux-" not in channel for channel in channels)
    assert all("/osx-" not in channel for channel in channels)
    assert all("/win-" not in channel for channel in channels)
