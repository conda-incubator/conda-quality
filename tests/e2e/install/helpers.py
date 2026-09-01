# SPDX-License-Identifier: BSD-3-Clause
"""Shared helper functions for conda install E2E tests."""

from __future__ import annotations

import bz2
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest
from packaging.version import Version

from conda_e2e.parsers.list import PackageList

PACKAGE_NAME = "flask"
DEPENDENCY_PACKAGE_NAME = "werkzeug"
SECONDARY_PACKAGE_NAME = "click"
SINGLE_FILE_PACKAGE_NAME = "six"

# Static test data files
DATA_DIR = Path(__file__).parent.parent.parent / "data"
REQUIREMENTS_FILE = DATA_DIR / "requirements.txt"
ENVIRONMENT_YML_FILE = DATA_DIR / "environment.yml"

# (name, version, depends) pairs packed into the local channel by
# build_local_channel(). dependent=2.0 strictly requires dependency=2.0, which is
# what makes ``conda install --update-specs`` observable (see build_local_channel).
_LOCAL_CHANNEL_PACKAGES = (
    ("dependency", "1.0", ["python"]),
    ("dependency", "2.0", ["python"]),
    ("dependent", "1.0", ["python", "dependency >=1.0,<2.0"]),
    ("dependent", "2.0", ["python", "dependency >=2.0,<3.0"]),
)


def list_installed_packages(conda, flag: str, target: str) -> PackageList:
    """Return parsed JSON ``conda list`` output for a target env name/path."""
    list_result = conda("list", flag, target, "--json").assert_ok()
    return PackageList.from_json(list_result)


def search_versions(conda, package_name: str) -> list[str]:
    """Return all available versions for ``package_name``, sorted ascending."""
    search_result = conda("search", package_name, "--json").assert_ok()
    return sorted(
        {p["version"] for p in search_result.json().get(package_name, [])},
        key=Version,
    )


def pick_second_newest_and_latest(conda, package_name: str) -> tuple[str, str]:
    """Return ``(old_version, latest_version)`` for ``package_name``, picked dynamically.

    ``old_version`` is the second-newest available version, so it's guaranteed to
    be older than ``latest_version`` (validated below) without hardcoding a version
    that could age out.
    """
    versions = search_versions(conda, package_name)
    if len(versions) < 2:
        pytest.fail(f"need at least 2 {package_name} versions to pick from")
    old_version, latest_version = versions[-2], versions[-1]
    if Version(old_version) >= Version(latest_version):
        pytest.fail(
            f"{package_name}: expected old_version ({old_version}) to be older than "
            f"latest_version ({latest_version})"
        )
    return old_version, latest_version


def download_table_rows(stdout: str) -> list[str]:
    """Extract download table rows from conda install output.

    Returns lines from the "packages will be downloaded" section that contain
    the ``|`` separator and are actual package data rows (excludes header and separator).
    """
    lines = stdout.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if "will be downloaded" in line)
    except StopIteration:
        return []
    rows = []
    for line in lines[start:]:
        if not (line.startswith("  ") and "|" in line):
            continue
        # Skip header row (contains "package" or "build" as column names)
        if "package" in line.lower() and "build" in line.lower():
            continue
        # Skip separator row (only dashes after the pipe)
        after_pipe = line.split("|")[-1].strip()
        if after_pipe.replace("-", "") == "":
            continue
        rows.append(line)
    return rows


def build_local_channel(channel_dir: Path) -> Path:
    """Build a minimal local ``noarch`` channel into ``channel_dir`` and return its path.

     Creates a small local conda channel with four hand-built packages, so no
    conda-build is needed:

    - ``dependency`` 1.0 and 2.0
    - ``dependent`` 1.0 and 2.0, where ``dependent=2.0`` needs ``dependency`` 2.0

    With 1.0 of both installed, a normal install keeps them at 1.0.
    ``--update-specs`` upgrades both to 2.0, which is what the test checks.
    """
    noarch = channel_dir / "noarch"
    noarch.mkdir(parents=True, exist_ok=True)
    packages: dict[str, dict] = {}
    for name, version, depends in _LOCAL_CHANNEL_PACKAGES:
        filename, data, entry = _build_local_package(name, version, depends)
        (noarch / filename).write_bytes(data)
        packages[filename] = entry

    repodata = {
        "info": {"subdir": "noarch"},
        "packages": packages,
        "packages.conda": {},
        "removed": [],
        "repodata_version": 1,
    }
    repodata_bytes = json.dumps(repodata, indent=2).encode() + b"\n"
    (noarch / "repodata.json").write_bytes(repodata_bytes)
    (noarch / "repodata.json.bz2").write_bytes(bz2.compress(repodata_bytes))
    return channel_dir


def _build_local_package(name: str, version: str, depends: list[str]) -> tuple[str, bytes, dict]:
    """Return ``(filename, tar.bz2 bytes, repodata entry)`` for one local package."""
    init_py = f'__version__ = "{version}"\n'.encode()
    files = {f"site-packages/{name}/__init__.py": init_py}
    archive_files = {
        **files,
        "info/index.json": _local_index_json(name, version, depends),
        "info/files": ("\n".join(files) + "\n").encode(),
        "info/paths.json": _local_paths_json(files),
        "info/about.json": b'{"license": "BSD-3-Clause"}\n',
    }
    data = _tar_bz2(archive_files)
    entry = {
        "name": name,
        "version": version,
        "build": "0",
        "build_number": 0,
        "subdir": "noarch",
        "noarch": "python",
        "depends": depends,
        "license": "BSD-3-Clause",
        "md5": hashlib.md5(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }
    return f"{name}-{version}-0.tar.bz2", data, entry


def _tar_bz2(files: dict[str, bytes]) -> bytes:
    """Pack ``{archive_path: content}`` into a tar.bz2 archive in memory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:bz2") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _local_index_json(name: str, version: str, depends: list[str]) -> bytes:
    """Return ``info/index.json`` for one local package."""
    index = {
        "name": name,
        "version": version,
        "build": "0",
        "build_number": 0,
        "subdir": "noarch",
        "noarch": "python",
        "depends": depends,
        "license": "BSD-3-Clause",
    }
    return json.dumps(index, indent=2).encode() + b"\n"


def _local_paths_json(files: dict[str, bytes]) -> bytes:
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
    return json.dumps({"paths": paths, "paths_version": 1}, indent=2).encode() + b"\n"
