# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda info`` and ``conda info --json`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from conda_e2e.result import CommandResult


def _parse_fields(output: str) -> dict[str, list[str]]:
    """Split the plain ``conda info`` table into ``{key: [value_lines]}``."""
    # conda renders each field as ``f"{key:>N} : {value}"`` (see
    # ``conda.cli.main_info.get_main_info_str``); continuation lines for
    # multi-value fields repeat only the indent, with no " : " of their own.
    sep = " : "
    fields: dict[str, list[str]] = {}
    current_key: str | None = None
    sep_col: int | None = None
    for line in output.splitlines():
        if not line.strip():
            continue
        sep_idx = line.find(sep)
        is_key_line = sep_idx >= 0 and (sep_col is None or sep_idx == sep_col)
        if is_key_line:
            if sep_col is None:
                sep_col = sep_idx
            key = line[:sep_idx]
            value = line[sep_idx + len(sep) :]
            current_key = key.strip()
            # A multi-value field with no entries (e.g. no populated config
            # files) prints as "key : " with nothing after the separator;
            # start it empty rather than with one bogus blank value.
            fields[current_key] = [value] if value else []
        else:
            assert current_key is not None, f"continuation line before any key: {line!r}"
            fields[current_key].append(line.strip())
    return fields


@dataclass(frozen=True, slots=True)
class PlainCondaInfo:
    """Selected fields parsed from plain-text ``conda info`` output."""

    active_env_name: str | None
    active_env_location: Path | None
    shell_level: int
    user_rc_path: Path
    config_files: tuple[Path, ...]
    conda_version: str
    conda_build_version: str
    python_version: str
    solver_name: str
    solver_default: bool
    virtual_pkgs: tuple[tuple[str, str, str], ...]
    root_prefix: Path
    root_writable: bool
    av_data_dir: Path
    av_metadata_url_base: str | None
    channels: tuple[str, ...]
    pkgs_dirs: tuple[Path, ...]
    envs_dirs: tuple[Path, ...]
    platform: str
    user_agent: str
    uid: int | None
    gid: int | None
    netrc_file: Path | None
    offline: bool

    @classmethod
    def from_stdout(cls, result: CommandResult) -> PlainCondaInfo:
        """Build from plain (non-``--json``) ``conda info`` stdout."""
        fields = _parse_fields(result.stdout)

        def one(key: str) -> str:
            (value,) = fields[key]
            return value

        def maybe_one(key: str) -> str | None:
            values = fields.get(key)
            if values is None:
                return None
            (value,) = values
            return value

        solver_name, _, solver_flag = one("solver").partition(" (")
        base_prefix, _, base_flag = one("base environment").partition("  (")
        av_metadata_url_base = one("conda av metadata url")
        netrc_file = one("netrc file")
        uid = gid = None
        uid_gid = maybe_one("UID:GID")
        if uid_gid is not None:
            uid, gid = map(int, uid_gid.split(":"))

        active_env_location = maybe_one("active env location")
        active_env_name = one("active environment") if active_env_location is not None else None

        # conda only prints "shell level" when context.shlvl >= 0; it's -1
        # (and the line omitted) when CONDA_SHLVL isn't set, e.g. a bare
        # invocation with no shell hook sourced.
        shell_level = maybe_one("shell level")

        return cls(
            active_env_name=active_env_name,
            active_env_location=(
                Path(active_env_location) if active_env_location is not None else None
            ),
            shell_level=int(shell_level) if shell_level is not None else -1,
            user_rc_path=Path(one("user config file")),
            config_files=tuple(Path(p) for p in fields["populated config files"]),
            conda_version=one("conda version"),
            conda_build_version=one("conda-build version"),
            python_version=one("python version"),
            solver_name=solver_name,
            solver_default=solver_flag == "default)",
            virtual_pkgs=tuple(tuple(pkg.split("=", 2)) for pkg in fields["virtual packages"]),
            root_prefix=Path(base_prefix),
            root_writable=base_flag == "writable)",
            av_data_dir=Path(one("conda av data dir")),
            av_metadata_url_base=None if av_metadata_url_base == "None" else av_metadata_url_base,
            channels=tuple(fields["channel URLs"]),
            pkgs_dirs=tuple(Path(p) for p in fields["package cache"]),
            envs_dirs=tuple(Path(p) for p in fields["envs directories"]),
            platform=one("platform"),
            user_agent=one("user-agent"),
            uid=uid,
            gid=gid,
            netrc_file=Path(netrc_file) if netrc_file != "None" else None,
            offline=one("offline mode") == "True",
        )


@dataclass(frozen=True, slots=True)
class CondaInfo:
    """Selected fields from ``conda info --json``.

    Prefixes are :class:`~pathlib.Path`. ``active_prefix`` is ``None`` when no
    environment is active. ``env_vars`` is a read-only mapping, so ``frozen=True``
    holds through it too (callers can't mutate it in place).
    """

    conda_version: str
    root_prefix: Path
    active_prefix: Path | None
    active_prefix_name: str | None
    platform: str
    env_vars: Mapping[str, str]
    conda_shlvl: int
    conda_prefix: Path
    conda_location: Path
    conda_env_version: str
    default_prefix: Path
    pkgs_dirs: tuple[Path, ...]
    envs_dirs: tuple[Path, ...]
    envs: tuple[Path, ...]
    config_files: tuple[Path, ...]
    rc_path: Path
    user_rc_path: Path
    sys_rc_path: Path
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
    netrc_file: Path | None
    requests_version: str
    site_dirs: tuple[Path, ...]
    sys_executable: Path
    sys_prefix: Path
    sys_version: str

    @classmethod
    def from_json(cls, result: CommandResult) -> CondaInfo:
        """Build from ``conda info --json`` output."""
        data = result.json()
        active_prefix = data.get("active_prefix")
        return cls(
            conda_version=data["conda_version"],
            root_prefix=Path(data["root_prefix"]),
            active_prefix=Path(active_prefix) if active_prefix is not None else None,
            active_prefix_name=data.get("active_prefix_name"),
            platform=data["platform"],
            # Read-only so env_vars can't be edited in place, matching frozen=True.
            env_vars=MappingProxyType(dict(data.get("env_vars") or {})),
            conda_shlvl=data["conda_shlvl"],
            conda_prefix=Path(data["conda_prefix"]),
            conda_location=Path(data["conda_location"]),
            conda_env_version=data["conda_env_version"],
            default_prefix=Path(data["default_prefix"]),
            pkgs_dirs=tuple(Path(p) for p in data.get("pkgs_dirs") or ()),
            envs_dirs=tuple(Path(p) for p in data.get("envs_dirs") or ()),
            envs=tuple(Path(p) for p in data.get("envs") or ()),
            config_files=tuple(Path(p) for p in data.get("config_files") or ()),
            rc_path=Path(data["rc_path"]),
            user_rc_path=Path(data["user_rc_path"]),
            sys_rc_path=Path(data["sys_rc_path"]),
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
            uid=data.get("UID"),
            gid=data.get("GID"),
            av_data_dir=Path(data["av_data_dir"]),
            av_metadata_url_base=data.get("av_metadata_url_base"),
            netrc_file=(
                Path(netrc_file) if (netrc_file := data.get("netrc_file")) is not None else None
            ),
            requests_version=data["requests_version"],
            site_dirs=tuple(Path(site_dir) for site_dir in data.get("site_dirs") or ()),
            sys_executable=Path(data["sys.executable"]),
            sys_prefix=Path(data["sys.prefix"]),
            sys_version=data["sys.version"],
        )
