# SPDX-License-Identifier: BSD-3-Clause
"""Black-box subprocess runner for the conda CLI."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import TYPE_CHECKING

from .result import CommandResult

if TYPE_CHECKING:
    from collections.abc import Mapping

# Default timeout, in seconds, for a single command.
DEFAULT_TIMEOUT = 60

logger = logging.getLogger(__name__)


class CliRunner:
    """Run an executable as a subprocess and capture its output.

    Args:
        executable: Program to run (name on PATH or absolute path).
        environ: Environment for the child process. If None, the current
            ``os.environ`` is inherited; pass an explicit dict (e.g. the
            ``isolated_env_vars`` fixture) for hermetic runs.
        cwd: Working directory for the child process.

    Raises:
        FileNotFoundError: If ``executable`` is not on PATH or not executable.

    """

    def __init__(
        self,
        executable: str,
        environ: Mapping[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
    ) -> None:
        self.executable = executable
        self.environ = environ
        self.cwd = cwd

        resolved = shutil.which(executable)
        if resolved is None:
            raise FileNotFoundError(
                f"executable {executable!r} not found on PATH or not executable"
            )
        self._resolved = resolved

    @property
    def resolved_path(self) -> str:
        """The resolved absolute path of the executable."""
        return self._resolved

    def run(
        self,
        *argv: str | os.PathLike[str],
        extra_env: Mapping[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
        stdin: str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run the executable with ``argv`` and return the captured result.

        Args:
            argv: Arguments passed to the executable.
            extra_env: Environment overrides merged onto ``environ``.
            cwd: Per-call working directory override.
            stdin: Optional text piped to the process's standard input.
            timeout: Seconds before the process is killed (None = no limit).

        Returns:
            CommandResult: The exit code and captured stdout/stderr.

        """
        cmd = (self._resolved, *(str(arg) for arg in argv))
        return self._execute(cmd, extra_env=extra_env, cwd=cwd, stdin=stdin, timeout=timeout)

    def run_raw(
        self,
        cmdline: str,
        *,
        extra_env: Mapping[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
        stdin: str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run a full command line given as a single string.

        Use instead of :meth:`run` when the command contains quoted paths that
        must stay intact: passing them as an argument list mangles the quotes on
        Windows. The string is run exactly as given.

        Args:
            cmdline: The full command line, already quoted for the target shell.
            extra_env: Environment overrides merged onto ``environ``.
            cwd: Per-call working directory override.
            stdin: Optional text piped to the process's standard input.
            timeout: Seconds before the process is killed (None = no limit).

        Returns:
            CommandResult: The exit code and captured stdout/stderr.

        """
        return self._execute(cmdline, extra_env=extra_env, cwd=cwd, stdin=stdin, timeout=timeout)

    def _execute(
        self,
        popen_args: tuple[str, ...] | str,
        *,
        extra_env: Mapping[str, str] | None,
        cwd: str | os.PathLike[str] | None,
        stdin: str | None,
        timeout: float | None,
    ) -> CommandResult:
        """Run ``popen_args`` (an argv tuple or a raw command line) and capture the result."""
        run_env: dict[str, str] | None
        if self.environ is None and extra_env is None:
            run_env = None  # inherit os.environ
        else:
            run_env = dict(self.environ if self.environ is not None else os.environ)
            if extra_env:
                run_env.update(extra_env)

        cmd = popen_args if isinstance(popen_args, tuple) else (popen_args,)
        try:
            logger.info("Executing command '%s'", popen_args)
            proc = subprocess.run(
                popen_args,
                capture_output=True,
                text=True,
                env=run_env,
                cwd=cwd if cwd is not None else self.cwd,
                input=stdin,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            logger.warning("Timeout exceeded for command: %s", popen_args)
            stdout = exc.stdout or ""
            stderr = (exc.stderr or "") + f"\n[timed out after {timeout}s]"
            return CommandResult(
                cmd=cmd,
                returncode=-1,
                stdout=stdout if isinstance(stdout, str) else stdout.decode(errors="replace"),
                stderr=stderr if isinstance(stderr, str) else stderr.decode(errors="replace"),
            )

        return CommandResult(
            cmd=cmd,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    # convenience alias so call sites read like `runner("create", ...)`
    __call__ = run
