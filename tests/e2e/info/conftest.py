# SPDX-License-Identifier: BSD-3-Clause
"""Fixtures shared by ``conda info`` E2E tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from assert_helpers import TokenChannel

if TYPE_CHECKING:
    from collections.abc import Mapping


@pytest.fixture(scope="session")
def install_root(conda_exe: str) -> Path:
    """Return the root prefix containing the conda executable under test."""
    return Path(conda_exe).resolve().parent.parent


@pytest.fixture
def token_channel(condarc: Path) -> TokenChannel:
    """Configure and return a synthetic token-bearing channel URL."""
    token = "e2e-token"
    # Conda recognizes tokens in the ``/t/<token>/`` URL segment; ``info`` only renders it.
    channel = TokenChannel(
        url=f"https://conda.anaconda.org/t/{token}/conda-forge",
        token=token,
    )
    condarc.write_text(f"channels:\n  - {channel.url}\n")
    return channel


@pytest.fixture
def info_env_vars() -> dict[str, str]:
    """Return controlled values displayed by ``conda info --system``."""
    # These values make the system/all renderers observably differ from bare ``conda info``.
    return {
        "CIO_TEST": "conda-e2e-system",
        "CONDA_OFFLINE": "false",
        "CURL_CA_BUNDLE": "e2e-curl-ca.pem",
        "REQUESTS_CA_BUNDLE": "e2e-requests-ca.pem",
        "SSL_CERT_FILE": "e2e-ssl-ca.pem",
    }


@pytest.fixture
def expected_info_env_vars(
    info_env_vars: dict[str, str], non_interactive_env_vars: Mapping[str, str]
) -> dict[str, str]:
    """Return controlled and fixture-owned values expected in ``info --json``."""
    # Assert only values established by this test setup, not the host's ambient environment.
    return {
        **info_env_vars,
        **{
            name: non_interactive_env_vars[name]
            for name in (
                "CONDARC",
                "CONDA_ALWAYS_YES",
                "CONDA_ENVS_DIRS",
                "CONDA_NOTICES",
                "CONDA_PKGS_DIRS",
                "CONDA_PLUGINS_AUTO_ACCEPT_TOS",
            )
        },
    }
