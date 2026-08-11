# SPDX-License-Identifier: BSD-3-Clause
"""Assertion helpers for ``conda info``/``conda info --json`` fields not tied to a single test.

Kept local to the ``info`` test package since these assertions are only
needed here: cross-checking the plain-text renderer against ``--json``, and
sandbox directories, host invariants, and activation env vars.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from conda_e2e.parsers.info import CONDA_ENVIRONMENTS_HEADER
from conda_e2e.runner import CliRunner
from conda_e2e.utils import is_same_path

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from conda_e2e.parsers.env import EnvRecord
    from conda_e2e.parsers.info import (
        CondaInfo,
        PlainCondaInfo,
        PlainCondaSystemInfo,
    )

# =============================================================================
# Shared support
# =============================================================================

_CHANNEL_URL_RE = re.compile(r"^https?://")
# Plain text redacts values in single-letter user-agent tokens, while JSON keeps them.
_USER_AGENT_TOKEN_RE = re.compile(r" ([a-z])/([^ ]+)")


@dataclass(frozen=True, slots=True)
class TokenChannel:
    """A configured channel URL that carries a token in its path."""

    url: str
    token: str


def _redact_user_agent_tokens(user_agent: str) -> str:
    """Apply the plain-text renderer's own token redaction to a user-agent string."""
    return _USER_AGENT_TOKEN_RE.sub(r" \1/.", user_agent)


def _assert_same_paths(plain_paths: tuple[Path, ...], json_paths: tuple[Path, ...]) -> None:
    """Assert ordered path collections identify the same locations."""
    assert len(plain_paths) == len(json_paths), (
        f"path collection lengths differ: plain={plain_paths!r}, JSON={json_paths!r}"
    )
    for index, (plain_path, json_path) in enumerate(zip(plain_paths, json_paths, strict=True)):
        assert is_same_path(plain_path, json_path), (
            f"paths differ at index {index}: "
            f"plain={plain_path!r} ({plain_path.resolve()!r}), "
            f"JSON={json_path!r} ({json_path.resolve()!r})"
        )


# =============================================================================
# Plain/JSON renderer assertions
# =============================================================================


def assert_plain_and_json_info_match(plain: PlainCondaInfo, info: CondaInfo) -> None:
    """Assert every field the plain renderer shows agrees with ``conda info --json``.

    The JSON-derived fields are already proven correct (sandboxing, snapshot
    invariants, activation state) by the existing ``--json`` tests, so this
    only cross-checks that the plain-text renderer reports the same values —
    it does not re-derive or re-assert those invariants itself.
    """
    assert plain.active_env_name == info.active_prefix_name
    assert is_same_path(plain.active_env_location, info.active_prefix)
    assert plain.shell_level == info.conda_shlvl
    assert is_same_path(plain.user_rc_path, info.user_rc_path)
    _assert_same_paths(plain.config_files, info.config_files)
    assert plain.conda_version == info.conda_version
    assert plain.conda_build_version == info.conda_build_version
    assert plain.python_version == info.python_version
    assert plain.solver_name == info.solver_name
    assert plain.solver_default == info.solver_default
    assert plain.virtual_pkgs == info.virtual_pkgs
    assert is_same_path(plain.root_prefix, info.root_prefix)
    assert plain.root_writable == info.root_writable
    assert is_same_path(plain.av_data_dir, info.av_data_dir)
    assert plain.av_metadata_url_base == info.av_metadata_url_base
    assert plain.channels == info.channels
    _assert_same_paths(plain.pkgs_dirs, info.pkgs_dirs)
    _assert_same_paths(plain.envs_dirs, info.envs_dirs)
    assert plain.platform == info.platform
    assert plain.user_agent == _redact_user_agent_tokens(info.user_agent)
    assert plain.uid == info.uid
    assert plain.gid == info.gid
    assert is_same_path(plain.netrc_file, info.netrc_file)
    assert plain.offline == info.offline


def assert_plain_and_json_system_info_match(plain: PlainCondaSystemInfo, info: CondaInfo) -> None:
    """Assert every shared ``conda info --system`` field agrees with ``--json``."""
    assert info.sys_version.startswith(plain.sys_version.removesuffix("..."))
    assert is_same_path(plain.sys_prefix, info.sys_prefix)
    assert is_same_path(plain.sys_executable, info.sys_executable)
    assert is_same_path(plain.conda_location, info.conda_location)
    # Each conda invocation lists user site dirs independently and conda doesn't
    # guarantee a stable order, so compare the sets rather than the sequences.
    assert {p.resolve() for p in plain.site_dirs} == {p.resolve() for p in info.site_dirs}
    # Plain output cannot represent trailing value whitespace; JSON preserves it.
    expected_plain_env_vars = {name: value.rstrip() for name, value in info.env_vars.items()}
    assert plain.env_vars == expected_plain_env_vars


# =============================================================================
# JSON snapshot assertions
# =============================================================================


def assert_sandboxed(info: CondaInfo, isolated_env_vars: dict[str, str]) -> None:
    """Assert the sandbox dirs from ``isolated_env_vars`` are the ones conda reports.

    Every path here comes from the per-test sandbox fixture, not a hardcoded
    value, so this holds regardless of where the test runs.
    """
    assert len(info.pkgs_dirs) == 1
    assert is_same_path(info.pkgs_dirs[0], isolated_env_vars["CONDA_PKGS_DIRS"])
    assert any(is_same_path(isolated_env_vars["CONDA_ENVS_DIRS"], path) for path in info.envs_dirs)
    assert is_same_path(info.rc_path, isolated_env_vars["CONDARC"])
    assert is_same_path(info.user_rc_path, isolated_env_vars["CONDARC"])


def assert_info_json_interpreter_versions(info: CondaInfo) -> None:
    """Assert interpreter versions agree with the reported Python executable."""
    python_version_result = CliRunner(executable=str(info.sys_executable))(
        "--version", timeout=30
    ).assert_ok()
    expected_python_version = python_version_result.stdout.strip().removeprefix("Python ")

    assert info.sys_version.startswith(expected_python_version)
    assert info.python_version.startswith(expected_python_version)


def assert_info_json_bare_activation_state(info: CondaInfo) -> None:
    """Assert a direct invocation reports no active environment."""
    assert info.default_prefix == info.root_prefix
    assert info.active_prefix is None
    assert info.active_prefix_name is None
    # Bare invocations commonly report -1; Windows launcher wrappers can report 0.
    assert info.conda_shlvl in {-1, 0}


def assert_info_json_expected_env_vars(
    info: CondaInfo, expected_env_vars: Mapping[str, str], *, install_root: Path
) -> None:
    """Assert fixture-controlled variables are reported by a JSON snapshot."""
    for name, expected_value in expected_env_vars.items():
        if name in {"CONDARC", "CONDA_ENVS_DIRS", "CONDA_PKGS_DIRS"}:
            assert is_same_path(info.env_vars[name], expected_value)
        else:
            assert info.env_vars[name] == expected_value
    assert is_same_path(info.env_vars["CONDA_ROOT"], install_root)


def assert_info_json_host_identity(info: CondaInfo) -> None:
    """Assert reported POSIX identity fields agree with the current process."""
    if hasattr(os, "getuid") and info.uid is not None:  # os.getuid is POSIX-only
        assert info.uid == os.getuid()
    if hasattr(os, "getgid") and info.gid is not None:  # os.getgid is POSIX-only
        assert info.gid == os.getgid()


def assert_info_json_installation_paths(info: CondaInfo) -> None:
    """Assert reported installation paths form a consistent base layout."""
    assert info.av_data_dir == info.root_prefix / "etc" / "conda"
    assert info.sys_rc_path == info.root_prefix / ".condarc"
    assert info.conda_prefix == info.root_prefix
    assert info.conda_location.is_relative_to(info.conda_prefix)
    assert info.conda_location.is_dir()
    assert info.sys_prefix == info.conda_prefix
    assert info.sys_executable.is_relative_to(info.conda_prefix)


def assert_info_json_installation_discovered(info: CondaInfo) -> None:
    """Assert conda discovers its base environment and system configuration."""
    assert info.root_prefix in info.envs
    assert info.sys_rc_path in info.config_files


def assert_info_json_version_metadata(info: CondaInfo) -> None:
    """Assert version metadata is populated and internally consistent."""
    assert info.conda_env_version == info.conda_version
    assert info.conda_build_version
    assert info.requests_version


def assert_info_json_solver_metadata(info: CondaInfo) -> None:
    """Assert solver metadata is present in the reported user agent."""
    assert info.solver_name  # e.g. "libmamba" / "classic"
    assert info.solver_user_agent in info.user_agent


def assert_info_json_virtual_packages(info: CondaInfo) -> None:
    """Assert every reported virtual package has the public three-part shape."""
    assert info.virtual_pkgs
    for pkg in info.virtual_pkgs:
        assert len(pkg) == 3, f"expected name/version/build virtual package tuple, got {pkg!r}"
        name, version, build = pkg
        assert name.startswith("__")
        assert version
        assert build is not None


def assert_info_json_runtime_metadata(info: CondaInfo) -> None:
    """Assert required runtime identifiers are populated."""
    assert info.user_agent.startswith("conda/")
    assert info.platform  # non-empty, e.g. "osx-arm64" / "linux-64" / "win-64"


def assert_info_json_channel_urls_are_http(channels: tuple[str, ...]) -> None:
    """Assert every reported channel starts with an HTTP URL scheme."""
    assert channels, "At least one channel is expected."
    for channel in channels:
        assert _CHANNEL_URL_RE.match(channel), f"not an HTTP channel URL: {channel}"


# =============================================================================
# Activation assertions
# =============================================================================


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
# Environment list assertions
# =============================================================================


def assert_envs_headers_present(output: str, envs_flag: str) -> None:
    """Assert the stable ``conda info --envs`` header lines are present."""
    expected_headers = (
        CONDA_ENVIRONMENTS_HEADER,
        "# * -> active",
        "# + -> frozen",
    )
    missing_headers = [header for header in expected_headers if header not in output]
    assert not missing_headers, (
        f"{envs_flag} output missing {missing_headers}. Command output:\n{output}"
    )


def assert_created_env_listed(created_env: EnvRecord, env_name: str, env_path: Path) -> None:
    """Assert the created env is listed with the expected name and prefix path."""
    assert created_env.name == env_name
    assert is_same_path(created_env.prefix, env_path)


def assert_created_env_json_fields(created_env: EnvRecord, env_name: str, env_path: Path) -> None:
    """Assert stable JSON fields for a newly created environment entry."""
    assert_created_env_listed(created_env, env_name, env_path)
    assert created_env.created
    assert created_env.last_modified
    assert created_env.base is False
    assert created_env.writable
    assert not created_env.frozen
