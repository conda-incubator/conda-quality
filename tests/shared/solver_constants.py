# SPDX-License-Identifier: BSD-3-Clause
"""Shared solver assertion constants for E2E tests."""

SOLVER_UNSATISFIABLE_ERRORS = {
    "classic": "PackagesNotFoundInChannelsError",
    "libmamba": "LibMambaUnsatisfiableError",
    "rattler": "RattlerUnsatisfiableError",
}
