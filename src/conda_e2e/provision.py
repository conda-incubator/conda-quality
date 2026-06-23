# SPDX-License-Identifier: BSD-3-Clause
"""Provision the conda under test: update the ``base`` env to a chosen version."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .result import CommandResult
    from .runner import CliRunner

logger = logging.getLogger(__name__)

# Default channel to get new conda version
CANARY_DEV_CHANNEL = "conda-canary/label/dev"


class CondaE2EProvisionError(RuntimeError):
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


def update_base_conda(
    runner: CliRunner,
    version: str,
    channel: str = CANARY_DEV_CHANNEL,
) -> CommandResult:
    """Install ``conda`` ``version`` from ``channel`` into ``base`` and confirm it.

    Args:
        runner: Runner bound to the conda under test (host env, auto-confirm).
        version: ``"latest"`` or a specific version to pin (e.g. ``"26.3.1"``).
        channel: Channel/label to install conda from.

    Returns:
        The ``CommandResult`` of the successful ``conda install``.

    Raises:
        CondaE2EProvisionError: If the install fails (e.g. the version/channel
            does not exist) or a pinned ``version`` is not reflected afterwards.
    """

    def conda_version() -> str:
        """Return the ``conda --version`` text, as a domain error if it fails."""
        result = runner.run("--version")
        if not result.ok:
            raise CondaE2EProvisionError(
                f"'conda --version' failed (exit {result.returncode})\n{result.stderr.strip()}"
            )
        return result.stdout.strip()

    before = conda_version()
    result = runner.run("install", "-n", "base", build_conda_spec(version, channel))
    if not result.ok:
        raise CondaE2EProvisionError(
            f"could not install conda {version!r} from channel {channel!r} "
            f"(exit {result.returncode}) — the version or channel may not exist.\n"
            f"{result.stderr.strip()}"
        )
    after = conda_version()
    logger.info("conda has been updated: %s -> %s", before, after)
    if version != "latest" and version not in after.split():
        raise CondaE2EProvisionError(
            f"requested conda {version!r} but 'conda --version' reports {after!r}"
        )
    return result
