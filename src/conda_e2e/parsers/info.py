# SPDX-License-Identifier: BSD-3-Clause
"""Parser for ``conda info --json`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class CondaInfo:
    """Selected fields from ``conda info --json``.

    Prefixes are :class:`~pathlib.Path`. ``active_prefix`` is ``None`` when no
    environment is active. ``env_vars`` is a read-only mapping, so ``frozen=True``
    holds through it too (callers can't mutate it in place).
    """

    # NOTE: Add more fields if we need to test additional cases in the future.
    conda_version: str
    root_prefix: Path
    active_prefix: Path | None
    active_prefix_name: str | None
    env_vars: Mapping[str, str]
    conda_shlvl: int
    conda_prefix: Path
    conda_location: str
    conda_env_version: str
    default_prefix: Path
    pkgs_dirs: tuple[Path, ...]
    envs_dirs: tuple[Path, ...]
    envs: tuple[Path, ...]
    config_files: tuple[Path, ...]
    rc_path: Path
    user_rc_path: Path
    sys_rc_path: Path
    platform: str
    root_writable: bool
    offline: bool
    conda_build_version: str
    python_version: str
    solver_name: str
    solver_default: bool
    solver_user_agent: str
    virtual_pkgs: tuple[tuple[str, str, str], ...]
    channels: tuple[str, ...]
    user_agent: str
    uid: int | None
    gid: int | None
    av_data_dir: Path
    av_metadata_url_base: str | None
    netrc_file: str | None
    requests_version: str
    site_dirs: tuple[str, ...]
    sys_executable: str
    sys_prefix: str
    sys_version: str

    @classmethod
    def from_json(cls, result: CommandResult) -> CondaInfo:
        """Build from ``conda info --json`` output."""
        data = result.json()
        active_prefix = data.get("active_prefix")

        def maybe_int(value: object) -> int | None:
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        uid = data.get("UID")
        gid = data.get("GID")
        return cls(
            conda_version=data["conda_version"],
            root_prefix=Path(data["root_prefix"]),
            active_prefix=Path(active_prefix) if active_prefix is not None else None,
            active_prefix_name=data.get("active_prefix_name"),
            # Read-only so env_vars can't be edited in place, matching frozen=True.
            env_vars=MappingProxyType(dict(data.get("env_vars") or {})),
            conda_shlvl=data["conda_shlvl"],
            conda_prefix=Path(data["conda_prefix"]),
            conda_location=data["conda_location"],
            conda_env_version=data["conda_env_version"],
            default_prefix=Path(data["default_prefix"]),
            pkgs_dirs=tuple(Path(p) for p in data.get("pkgs_dirs") or ()),
            envs_dirs=tuple(Path(p) for p in data.get("envs_dirs") or ()),
            envs=tuple(Path(p) for p in data.get("envs") or ()),
            config_files=tuple(Path(p) for p in data.get("config_files") or ()),
            rc_path=Path(data["rc_path"]),
            user_rc_path=Path(data["user_rc_path"]),
            sys_rc_path=Path(data["sys_rc_path"]),
            platform=data["platform"],
            root_writable=data["root_writable"],
            offline=data["offline"],
            conda_build_version=data["conda_build_version"],
            python_version=data["python_version"],
            solver_name=data["solver"]["name"],
            solver_default=data["solver"]["default"],
            solver_user_agent=data["solver"]["user_agent"],
            virtual_pkgs=tuple(tuple(pkg) for pkg in data.get("virtual_pkgs") or ()),
            channels=tuple(data.get("channels") or ()),
            user_agent=data["user_agent"],
            uid=maybe_int(uid),
            gid=maybe_int(gid),
            av_data_dir=Path(data["av_data_dir"]),
            av_metadata_url_base=data.get("av_metadata_url_base"),
            netrc_file=data.get("netrc_file"),
            requests_version=data["requests_version"],
            site_dirs=tuple(data.get("site_dirs") or ()),
            sys_executable=data["sys.executable"],
            sys_prefix=data["sys.prefix"],
            sys_version=data["sys.version"],
        )
