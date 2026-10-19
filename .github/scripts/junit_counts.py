# SPDX-License-Identifier: BSD-3-Clause
"""Print the test counts from a pytest JUnit XML file, for the CI run summary."""

from __future__ import annotations

import sys
from xml.etree import ElementTree


def main(path: str) -> None:
    """Print ``<n> passed, <n> failed, <n> skipped`` for the JUnit file at ``path``."""
    suite = ElementTree.parse(path).getroot().find("testsuite")
    tests, failures, errors, skipped = (
        int(suite.get(name, 0)) for name in ("tests", "failures", "errors", "skipped")
    )
    passed = tests - failures - errors - skipped
    print(f"{passed} passed, {failures + errors} failed, {skipped} skipped")


if __name__ == "__main__":
    main(sys.argv[1])
