# SPDX-License-Identifier: BSD-3-Clause
"""Helpers shared across the conda E2E suites (currently install and create)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from conda_e2e.parsers.list import PackageList

if TYPE_CHECKING:
    from collections.abc import Callable


def list_installed_packages(conda: Callable, *target: str) -> PackageList:
    """Return parsed JSON ``conda list`` output for a target env name/path.

    Args:
        conda: The conda runner fixture.
        target: The environment selector conda expects, e.g. ``("-n", name)``
            or ``("-p", str(prefix))``.
    """
    return PackageList.from_json(conda("list", *target, "--json").assert_ok())
