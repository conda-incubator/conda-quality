# SPDX-License-Identifier: BSD-3-Clause
"""Parser for plain ``conda env create`` output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from conda_e2e.parsers.info import CondaOutputParseError

if TYPE_CHECKING:
    from conda_e2e.result import CommandResult


def environment_location_from_stdout(result: CommandResult) -> Path:
    """Parse the unique environment location from creation or preview output."""
    locations = [
        line.strip().partition(":")[2].strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("environment location:")
    ]
    if len(locations) != 1 or not locations[0]:
        raise CondaOutputParseError(
            f"Expected one non-empty environment location, got {locations!r}"
        )
    return Path(locations[0])


@dataclass(frozen=True, slots=True)
class PlainEnvCreateOutput:
    """Environment location and activation target from creation output."""

    prefix: Path
    activation_target: str

    @classmethod
    def from_stdout(cls, result: CommandResult) -> PlainEnvCreateOutput:
        """Parse the environment location and activation instruction."""
        activations = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and stripped[1:].strip().startswith("$"):
                command = stripped[1:].strip()[1:].strip()
                if command == "conda activate" or command.startswith("conda activate "):
                    activations.append(command.removeprefix("conda activate").strip())

        if len(activations) != 1 or not activations[0]:
            raise CondaOutputParseError(
                f"Expected one non-empty conda activate target, got {activations!r}"
            )
        return cls(
            prefix=environment_location_from_stdout(result), activation_target=activations[0]
        )
