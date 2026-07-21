# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures shared by ``conda info`` E2E tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def install_root(conda_exe: str) -> Path:
    """Return the root prefix containing the conda executable under test."""
    return Path(conda_exe).resolve().parent.parent


@pytest.fixture
def token_channel(condarc: Path) -> str:
    """Configure and return a synthetic token-bearing channel URL."""
    # Conda recognizes tokens in the ``/t/<token>/`` URL segment; ``info`` only renders it.
    channel = "https://conda.anaconda.org/t/e2e-token/conda-forge"
    condarc.write_text(f"channels:\n  - {channel}\n")
    return channel
