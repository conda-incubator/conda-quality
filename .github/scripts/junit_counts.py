# SPDX-License-Identifier: BSD-3-Clause
"""Print the test counts from a pytest JUnit XML file, for the CI run summary."""

from __future__ import annotations

import sys
from xml.etree import ElementTree


def main(path: str) -> None:
    """Print ``<n> passed, <n> failed, <n> skipped, <n> rerun`` for the JUnit file at ``path``.

    A rerun test has one ``<testcase>`` per attempt, so each repeat of a test is a rerun.
    """
    suite = ElementTree.parse(path).getroot().find("testsuite")
    tests, failures, errors, skipped = (
        int(suite.get(name, 0)) for name in ("tests", "failures", "errors", "skipped")
    )
    passed = tests - failures - errors - skipped
    cases = [(case.get("classname"), case.get("name")) for case in suite.iter("testcase")]
    reruns = len(cases) - len(set(cases))
    print(f"{passed} passed, {failures + errors} failed, {skipped} skipped, {reruns} rerun")


if __name__ == "__main__":
    main(sys.argv[1])
