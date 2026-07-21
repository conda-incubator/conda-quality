# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures shared by ``conda info`` E2E tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def token_channel(condarc: Path) -> str:
    """Configure and return a synthetic token-bearing channel URL."""
    # Conda recognizes tokens in the ``/t/<token>/`` URL segment; ``info`` only renders it.
    channel = "https://conda.anaconda.org/t/e2e-token/conda-forge"
    condarc.write_text(f"channels:\n  - {channel}\n")
    return channel
