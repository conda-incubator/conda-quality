# SPDX-License-Identifier: BSD-3-Clause
"""Parsers for ``conda info`` and ``conda info --json`` output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from conda_e2e.result import CommandResult

# The plain-text renderer redacts single-letter user-agent tokens (anonymous
# usage IDs added by the anaconda_anon_usage plugin, e.g. "c/<id>", "s/<id>")
# to "x/." — see anaconda_anon_usage.patch._new_get_main_info_str — while the
# JSON ``user_agent`` field keeps the real values.
_USER_AGENT_TOKEN_RE = re.compile(r" ([a-z])/([^ ]+)")


def redact_user_agent_tokens(user_agent: str) -> str:
    """Apply the plain-text renderer's own token redaction to a user-agent string."""
    return _USER_AGENT_TOKEN_RE.sub(r" \1/.", user_agent)


# conda renders each field as ``f"{key:>N} : {value}"`` (see
# ``conda.cli.main_info.get_main_info_str``); continuation lines for
# multi-value fields repeat only the indent, with no " : " of their own. That
# lets key lines and continuation lines be told apart by the separator's
# presence, without hardcoding the key column's width.
_SEP = " : "


def _parse_fields(output: str) -> dict[str, list[str]]:
    """Split the plain ``conda info`` table into ``{key: [value_lines]}``."""
    fields: dict[str, list[str]] = {}
    current_key: str | None = None
    sep_col: int | None = None
    for line in output.splitlines():
        if not line.strip():
            continue
        sep_idx = line.find(_SEP)
        is_key_line = sep_idx >= 0 and (sep_col is None or sep_idx == sep_col)
        if is_key_line:
            if sep_col is None:
                sep_col = sep_idx
            key = line[:sep_idx]
            value = line[sep_idx + len(_SEP) :]
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
    netrc_file: str | None
    offline: bool

    @classmethod
    def from_stdout(cls, output: str) -> PlainCondaInfo:
        """Build from plain (non-``--json``) ``conda info`` stdout."""
        fields = _parse_fields(output)

        def one(key: str) -> str:
            (value,) = fields[key]
            return value

        def maybe_one(key: str) -> str | None:
            values = fields.get(key)
            if values is None:
                return None
            (value,) = values
            return value

        def maybe_int(value: str | None) -> int | None:
            if value is None:
                return None
            return int(value) if value.isdigit() else None

        solver_name, _, solver_flag = one("solver").partition(" (")
        base_prefix, _, base_flag = one("base environment").partition("  (")
        av_metadata_url_base = one("conda av metadata url")
        netrc_file = one("netrc file")
        uid_gid = maybe_one("UID:GID")
        uid_s, _, gid_s = uid_gid.partition(":") if uid_gid is not None else (None, "", None)

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
            uid=maybe_int(uid_s),
            gid=maybe_int(gid_s),
            netrc_file=None if netrc_file == "None" else netrc_file,
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
            platform=data["platform"],
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
