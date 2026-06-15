# SPDX-License-Identifier: BSD-3-Clause
"""The single result type returned by every CLI invocation."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result of a single CLI command run as a subprocess.

    Holds the command's exit code and captured ``stdout``/``stderr``, with
    helpers for inspecting them.
    """

    # The full argv that was executed, e.g. ``("conda", "create", "-n", "x")``.
    cmd: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def command(self) -> str:
        """The executed command rendered as a copy-pasteable shell string."""
        return shlex.join(self.cmd)

    @property
    def ok(self) -> bool:
        """True when the command exited successfully (code 0)."""
        return self.returncode == 0

    def json(self) -> Any:
        """Parse ``stdout`` as JSON (only meaningful when run with ``--json``).

        Returns:
            The decoded JSON value.

        Raises:
            ValueError: If ``stdout`` is not valid JSON.

        """
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"stdout is not valid JSON. Was the command run with '--json' flag?\n"
                f"  cmd: {self.command}\n"
                f"  stdout[:200]: {self.stdout[:200]!r}"
            ) from exc

    def assert_ok(self) -> CommandResult:
        """Assert the command succeeded; return self for chaining."""
        if not self.ok:
            raise AssertionError(
                f"command failed with exit code {self.returncode}\n"
                f"  cmd: {self.command}\n"
                f"  stdout:\n{self.stdout}\n"
                f"  stderr:\n{self.stderr}"
            )
        return self

    def assert_error(
        self,
        *,
        code: int | None = None,
        contains: str | None = None,
    ) -> CommandResult:
        """Assert the command failed; return self for chaining.

        Args:
            code: If given, require this exact non-zero exit code.
            contains: If given, require this substring in stdout or stderr.

        """
        if self.ok:
            raise AssertionError(
                f"expected command to fail, but it succeeded\n  cmd: {self.command}"
            )
        if code is not None and self.returncode != code:
            raise AssertionError(
                f"expected exit code {code}, got {self.returncode}\n"
                f"  cmd: {self.command}\n  stderr:\n{self.stderr}"
            )
        if contains is not None:
            output = f"{self.stdout}\n{self.stderr}"
            if contains not in output:
                raise AssertionError(
                    f"expected {contains!r} in output, not found\n"
                    f"  cmd: {self.command}\n  stdout:\n{self.stdout}\n  stderr:\n{self.stderr}"
                )
        return self
