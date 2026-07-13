# SPDX-License-Identifier: BSD-3-Clause
"""Update the conda under test: install a chosen version into the ``base`` env."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .result import CommandResult
    from .runner import CliRunner

logger = logging.getLogger(__name__)

# Default channel to get new conda version
CANARY_DEV_CHANNEL = "conda-canary/label/dev"


class CondaE2EUpdateError(RuntimeError):
    """Updating the base conda to the requested version/channel failed.

    Carries conda's own message, so callers can report it without inspecting
    conda internals — the failure is detected purely from the command's exit
    code and stderr (the black-box contract).
    """


def build_conda_spec(version: str, channel: str = CANARY_DEV_CHANNEL) -> str:
    """Build a conda install spec from ``channel`` for ``version``.

    Args:
        version: ``"latest"`` for the newest build, or a version to pin
            (e.g. ``"26.3.1"``).
        channel: Channel/label to install from.

    Returns:
        A conda match spec: ``"<channel>::conda"`` for ``"latest"``, otherwise
        ``"<channel>::conda=<version>"``.
    """
    if version == "latest":
        return f"{channel}::conda"
    return f"{channel}::conda={version}"


def _version_satisfies_request(installed: str, requested: str) -> bool:
    """Return whether ``installed`` matches requested conda version prefix.

    Accept an exact match or a prefix continued by ``.`` (dev build, e.g.
    ``26.5.2`` -> ``26.5.2.46``) or ``+`` (local metadata, e.g. ``+gabc123``).
    This avoids false matches like ``26.5.3`` vs ``26.5.30``.
    """
    return installed == requested or installed.startswith((requested + ".", requested + "+"))


def update_base_conda(
    runner: CliRunner,
    version: str,
    channel: str = CANARY_DEV_CHANNEL,
) -> CommandResult:
    """Update ``base`` conda to ``version`` from ``channel`` and verify it.

    Args:
        runner: Runner for the conda under test.
        version: ``"latest"`` or a pinned version (e.g. ``"26.3.1"``).
        channel: Channel/label to install from.

    Returns:
        The successful ``conda install`` result.

    Raises:
        CondaE2EUpdateError: If the install fails or the installed version
            doesn't match ``version``.
    """

    def conda_version() -> str:
        """Return ``conda --version`` output; raise CondaE2EUpdateError on failure."""
        result = runner.run("--version")
        if not result.ok:
            raise CondaE2EUpdateError(
                f"'conda --version' failed (exit {result.returncode})\n{result.stderr.strip()}"
            )
        return result.stdout.strip()

    before = conda_version()
    result = runner.run("install", "-n", "base", build_conda_spec(version, channel))
    if not result.ok:
        raise CondaE2EUpdateError(
            f"could not install conda {version!r} from channel {channel!r} "
            f"(exit {result.returncode}) — the version or channel may not exist.\n"
            f"{result.stderr.strip()}"
        )
    after = conda_version()
    logger.info("conda has been updated: %s -> %s", before, after)

    after_version = after.removeprefix("conda ").strip()
    satisfied = _version_satisfies_request(after_version, version)
    if version != "latest" and not satisfied:
        raise CondaE2EUpdateError(
            f"requested conda {version!r} but 'conda --version' reports {after_version!r} "
            f"(was {before!r} before install)"
        )
    return result
