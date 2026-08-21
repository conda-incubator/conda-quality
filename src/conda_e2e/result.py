# SPDX-License-Identifier: BSD-3-Clause
"""The single result type returned by every CLI invocation."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Any, Literal


def _clip(text: str, max_chars: int | None) -> str:
    """Return ``text`` shortened to ``max_chars``, keeping its head and its tail."""
    if max_chars is None or len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(text) - max_chars
    return f"{text[:head]}\n[... {omitted} characters omitted ...]\n{text[len(text) - tail :]}"


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

    def describe(self, max_stream_chars: int | None = None) -> str:
        """Render the command, its exit code and both streams as one block.

        For callers that display a result rather than assert on it, such as the
        HTML test report.

        Args:
            max_stream_chars: If given, clip each stream to this many
                characters, keeping both ends — conda states its diagnosis last,
                so a head-only clip would lose it.

        Returns:
            str: The formatted block.

        """
        return (
            f"$ {self.command}\n"
            f"exit code: {self.returncode}\n"
            f"--- stdout ---\n{_clip(self.stdout, max_stream_chars)}\n"
            f"--- stderr ---\n{_clip(self.stderr, max_stream_chars)}"
        )

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
        stream: Literal["stdout", "stderr"] | None = "stderr",
    ) -> CommandResult:
        """Assert the command failed; return self for chaining.

        Args:
            code: If given, require this exact non-zero exit code.
            contains: If given, require this substring in the searched output.
            stream: Which stream ``contains`` is searched in: ``"stdout"``,
                ``"stderr"`` (default, where conda's error messages normally
                land), or ``None`` to search both combined when the stream
                isn't guaranteed.

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
            if stream is None:
                output = f"{self.stdout}\n{self.stderr}"
            elif stream == "stdout":
                output = self.stdout
            elif stream == "stderr":
                output = self.stderr
            else:
                raise ValueError(f"stream must be 'stdout', 'stderr', or None; got {stream!r}")
            if contains not in output:
                raise AssertionError(
                    f"expected {contains!r} in {stream or 'combined'} output, not found\n"
                    f"  cmd: {self.command}\n  stdout:\n{self.stdout}\n  stderr:\n{self.stderr}"
                )
        return self
