# SPDX-License-Identifier: BSD-3-Clause
"""Byte-for-byte equivalence of the public short and long help flags."""

import pytest

# =============================================================================
# Positive test cases
# =============================================================================


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("clean", marks=pytest.mark.covers(26)),
        pytest.param("config", marks=pytest.mark.covers(52)),
        pytest.param("env", marks=pytest.mark.covers(225)),
        pytest.param("info", marks=pytest.mark.covers(342)),
        pytest.param("install", marks=pytest.mark.covers(379)),
        pytest.param("list", marks=pytest.mark.covers(438)),
        pytest.param("package", marks=pytest.mark.covers(483)),
    ],
)
def test_help_short_flag_matches_long_form(conda, command):
    """``-h`` and ``--help`` render identical, nonempty command help."""
    long_form = conda(command, "--help").assert_ok().stdout
    short_form = conda(command, "-h").assert_ok().stdout
    assert long_form.startswith(f"usage: conda {command}"), long_form
    assert short_form == long_form, "-h should match --help output byte-for-byte"
