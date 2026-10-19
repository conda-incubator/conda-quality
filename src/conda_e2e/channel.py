# SPDX-License-Identifier: BSD-3-Clause
"""Build local conda channels for tests.

Hand-rolls ``noarch`` tar.bz2 packages and a ``repodata.json`` so tests can
install from a local channel without conda-build or network access.
"""

from __future__ import annotations

import bz2
import hashlib
import io
import json
import tarfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_BUILD = "0"
_SUBDIR = "noarch"
_LICENSE = "BSD-3-Clause"


@dataclass(frozen=True)
class Package:
    """One ``noarch: python`` package to place in a local channel."""

    name: str
    version: str
    depends: tuple[str, ...] = ()

    @property
    def filename(self) -> str:
        """The tar.bz2 filename for this package in the channel."""
        return f"{self.name}-{self.version}-{_BUILD}.tar.bz2"

    @property
    def metadata(self) -> dict:
        """Metadata shared by ``info/index.json`` and the repodata entry."""
        return {
            "name": self.name,
            "version": self.version,
            "build": _BUILD,
            "build_number": 0,
            "subdir": _SUBDIR,
            "noarch": "python",
            "depends": list(self.depends),
            "license": _LICENSE,
        }


def build_local_channel(channel_dir: Path, packages: list[Package]) -> Path:
    """Build a local ``noarch`` channel from ``packages`` and return its path."""
    noarch = channel_dir / _SUBDIR
    noarch.mkdir(parents=True, exist_ok=True)
    repodata_packages: dict[str, dict] = {}
    for package in packages:
        data = _package_archive(package)
        (noarch / package.filename).write_bytes(data)
        repodata_packages[package.filename] = {
            **package.metadata,
            "md5": hashlib.md5(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }

    repodata = {
        "info": {"subdir": _SUBDIR},
        "packages": repodata_packages,
        "packages.conda": {},
        "removed": [],
        "repodata_version": 1,
    }
    repodata_bytes = _json_bytes(repodata)
    (noarch / "repodata.json").write_bytes(repodata_bytes)
    (noarch / "repodata.json.bz2").write_bytes(bz2.compress(repodata_bytes))
    return channel_dir


def _package_archive(package: Package) -> bytes:
    """Return the tar.bz2 archive bytes for ``package``."""
    init_py = f'__version__ = "{package.version}"\n'.encode()
    files = {f"site-packages/{package.name}/__init__.py": init_py}
    archive_files = {
        **files,
        "info/index.json": _json_bytes(package.metadata),
        "info/files": ("\n".join(files) + "\n").encode(),
        "info/paths.json": _paths_json(files),
        "info/about.json": _json_bytes({"license": _LICENSE}),
    }
    return _tar_bz2(archive_files)


def _json_bytes(data: dict) -> bytes:
    """Serialize ``data`` as indented JSON with a trailing newline."""
    return json.dumps(data, indent=2).encode() + b"\n"


def _paths_json(files: dict[str, bytes]) -> bytes:
    """Return ``info/paths.json`` with real checksums/sizes for ``files``."""
    paths = [
        {
            "_path": path,
            "path_type": "hardlink",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_in_bytes": len(content),
        }
        for path, content in files.items()
    ]
    return _json_bytes({"paths": paths, "paths_version": 1})


def _tar_bz2(files: dict[str, bytes]) -> bytes:
    """Pack ``{archive_path: content}`` into a tar.bz2 archive in memory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:bz2") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()
