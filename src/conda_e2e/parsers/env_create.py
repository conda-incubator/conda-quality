# SPDX-License-Identifier: BSD-3-Clause
"""Parser for plain ``conda env create`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from conda_e2e.parsers.info import CondaOutputParseError

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


@dataclass(frozen=True, slots=True)
class PlainEnvCreateOutput:
    """Environment location and activation target from creation output."""

    prefix: Path
    activation_target: str

    @classmethod
    def from_stdout(cls, result: CommandResult) -> PlainEnvCreateOutput:
        """Parse the environment location and activation instruction."""
        locations = []
        activations = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("environment location:"):
                locations.append(stripped.partition(":")[2].strip())
            if stripped.startswith("#") and stripped[1:].strip().startswith("$"):
                command = stripped[1:].strip()[1:].strip()
                if command == "conda activate" or command.startswith("conda activate "):
                    activations.append(command.removeprefix("conda activate").strip())

        if len(locations) != 1 or not locations[0]:
            raise CondaOutputParseError(
                f"Expected one non-empty environment location, got {locations!r}"
            )
        if len(activations) != 1 or not activations[0]:
            raise CondaOutputParseError(
                f"Expected one non-empty conda activate target, got {activations!r}"
            )
        return cls(prefix=Path(locations[0]), activation_target=activations[0])
