# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures for ``conda config`` tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from conda_e2e.channel import Package, build_local_channel
from conda_e2e.https_channel import SelfSignedChannel, serve_self_signed_channel

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

CHANNEL_PACKAGE = "conda-e2e-ssl-probe"


@pytest.fixture
def self_signed_channel(tmp_path: Path) -> Iterator[SelfSignedChannel]:
    """Serve a local channel over HTTPS with a self-signed certificate.

    The certificate is generated per test, so no private key lives in the
    repository. Any client that verifies certificates must reject the channel,
    so a command can only succeed against it once verification is disabled.
    """
    package = Package(CHANNEL_PACKAGE, "1.0")
    channel_dir = build_local_channel(tmp_path / "channel", [package])
    with serve_self_signed_channel(channel_dir, tmp_path / "tls") as url:
        yield SelfSignedChannel(url, package)
