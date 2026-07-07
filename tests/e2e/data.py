# SPDX-License-Identifier: BSD-3-Clause
"""Shared test data constants for E2E tests."""

from __future__ import annotations

# =============================================================================
# Config test data
# =============================================================================

# Key configuration options that should be present in conda config output
EXPECTED_CONFIG_KEYS = (
    "channels",
    "channel_priority",
    "auto_update_conda",
    "always_yes",
    "changeps1",
    "ssl_verify",
)

# Invalid key for negative test cases
INVALID_CONFIG_KEY = "nonexistent_key_12345"
