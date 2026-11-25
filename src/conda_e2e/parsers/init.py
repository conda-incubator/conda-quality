# SPDX-License-Identifier: BSD-3-Clause
"""Parse the target statuses reported by ``conda init``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult

STATUSES = ("no change", "modified", "needs sudo")
_STATUS_LINE = re.compile(rf"({'|'.join(re.escape(status) for status in STATUSES)})(?:\s+(.*))?")


@dataclass(frozen=True, slots=True)
class InitResult:
    """Target statuses from the plain ``conda init`` output."""

    targets: tuple[tuple[str, str], ...]

    @classmethod
    def from_stdout(cls, result: CommandResult) -> InitResult:
        """Parse status lines while ignoring informational messages."""
        targets = []
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            match = _STATUS_LINE.fullmatch(line)
            if match:
                targets.append((match.group(1), match.group(2) or ""))
            elif line.startswith(STATUSES):
                raise ValueError(f"Malformed init status line: {raw_line!r}")
        return cls(tuple(targets))
