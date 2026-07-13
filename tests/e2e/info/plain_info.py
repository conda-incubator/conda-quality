# SPDX-License-Identifier: BSD-3-Clause
"""Parser for the plain-text ``conda info`` output (no ``--json``).

conda renders this table with a fixed-width right-justified key column
(``f"{key:>23} : {value}"``, see ``conda.cli.main_info.get_main_info_str``);
continuation lines for multi-value fields are indented 26 spaces with no
separator. Kept local to the ``info`` test package since these fields only
matter for cross-checking the plain renderer against ``conda info --json``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conda_e2e.parsers.info import CondaInfo

_KEY_WIDTH = 23
_SEP = " : "

# The plain-text renderer redacts single-letter user-agent tokens (anonymous
# usage IDs added by the anaconda_anon_usage plugin, e.g. "c/<id>", "s/<id>")
# to "x/." — see anaconda_anon_usage.patch._new_get_main_info_str — while the
# JSON ``user_agent`` field keeps the real values. Apply the same redaction to
# both sides before comparing.
_USER_AGENT_TOKEN_RE = re.compile(r" ([a-z])/([^ ]+)")


def _redact_user_agent_tokens(user_agent: str) -> str:
    """Apply the plain-text renderer's own token redaction to a user-agent string."""
    return _USER_AGENT_TOKEN_RE.sub(r" \1/.", user_agent)


def _parse_fields(output: str) -> dict[str, list[str]]:
    """Split the plain ``conda info`` table into ``{key: [value_lines]}``."""
    fields: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in output.splitlines():
        if not line.strip():
            continue
        if line[_KEY_WIDTH : _KEY_WIDTH + len(_SEP)] == _SEP:
            current_key = line[:_KEY_WIDTH].strip()
            fields[current_key] = [line[_KEY_WIDTH + len(_SEP) :]]
        else:
            assert current_key is not None, f"continuation line before any key: {line!r}"
            fields[current_key].append(line.strip())
    return fields


@dataclass(frozen=True, slots=True)
class PlainCondaInfo:
    """Selected fields parsed from plain-text ``conda info`` output."""

    active_env_name: str
    active_env_location: Path
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
    def from_text(cls, output: str) -> PlainCondaInfo:
        """Build from plain (non-``--json``) ``conda info`` output."""
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

        return cls(
            active_env_name=one("active environment"),
            active_env_location=Path(one("active env location")),
            shell_level=int(one("shell level")),
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


def assert_matches_json(plain: PlainCondaInfo, info: CondaInfo) -> None:
    """Assert every field the plain renderer shows agrees with ``conda info --json``.

    The JSON-derived fields are already proven correct (sandboxing, host
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
