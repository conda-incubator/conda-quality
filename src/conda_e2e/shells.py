# SPDX-License-Identifier: BSD-3-Clause
"""Drive conda through a specific shell, for shell-dependent behaviour only."""

from __future__ import annotations

import shlex
import shutil
from enum import Enum
from typing import TYPE_CHECKING

from .runner import DEFAULT_TIMEOUT, CliRunner

if TYPE_CHECKING:
    import os
    from collections.abc import Mapping

    from .result import CommandResult


class Shell(Enum):
    """A shell conda can be driven through.

    The value is the executable name (resolved on ``PATH``).
    """

    BASH = "bash"
    ZSH = "zsh"
    SH = "sh"
    POWERSHELL = "pwsh"  # cross-platform PowerShell 7+
    WINDOWS_POWERSHELL = "powershell"  # Windows built-in PowerShell 5.x
    CMD = "cmd"

    @property
    def command_flags(self) -> tuple[str, ...]:
        """The flags that make this shell run a command string and exit."""
        if self in (Shell.BASH, Shell.ZSH, Shell.SH):
            return ("-c",)
        if self in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL):
            return ("-NoProfile", "-Command")
        if self is Shell.CMD:
            # /s lets cmd strip only the outer quotes and run the rest verbatim,
            # so a quoted path inside the script survives.
            return ("/d", "/s", "/c")
        raise AssertionError(f"unhandled shell: {self}")

    def is_available(self) -> bool:
        """Return whether this shell's executable is resolvable on ``PATH``."""
        return shutil.which(self.value) is not None


class CondaShellRunner:
    """Drive conda through a specific :class:`Shell`.

    Returns the same :class:`~conda_e2e.result.CommandResult` as the other
    runners, so assertions stay identical regardless of shell. :meth:`run`
    executes an arbitrary command string. :meth:`run_in_activated_env` activates an
    environment first, which the plain ``conda`` runner cannot do. To run a
    non-conda program directly (no shell), use
    :class:`~conda_e2e.runner.CliRunner` instead.

    Args:
        shell: Which shell to invoke.
        environ: Environment for the child process (e.g. the sandboxed
            ``CONDA_*`` dict). If None, ``os.environ`` is inherited.
        cwd: Working directory for the child process.
        conda_exe: The conda executable used to emit the activation hook in
            :meth:`run_in_activated_env`. Defaults to ``conda`` on ``PATH``.

    """

    def __init__(
        self,
        shell: Shell,
        environ: Mapping[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
        conda_exe: str = "conda",
    ) -> None:
        self.shell = shell
        self._conda_exe = conda_exe
        self._runner = CliRunner(executable=shell.value, environ=environ, cwd=cwd)

    def run(
        self,
        script: str,
        *,
        extra_env: Mapping[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
        stdin: str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Run ``script`` in the shell and return the captured result.

        Args:
            script: The command string the shell will run.
            extra_env: Environment overrides merged onto ``environ``.
            cwd: Per-call working directory override.
            stdin: Optional text piped to the shell's standard input.
            timeout: Seconds before the process is killed (None = no limit).

        Returns:
            CommandResult: The exit code and captured stdout/stderr.

        """
        if self.shell is Shell.CMD:
            # On cmd, passing the command as an argument list mangles the quoted
            # path inside the script, so build and run it as one raw string.
            exe = self._runner.resolved_path
            flags = " ".join(self.shell.command_flags)
            cmdline = f'"{exe}" {flags} "{script}"'
            return self._runner.run_raw(
                cmdline, extra_env=extra_env, cwd=cwd, stdin=stdin, timeout=timeout
            )
        return self._runner.run(
            *self.shell.command_flags,
            script,
            extra_env=extra_env,
            cwd=cwd,
            stdin=stdin,
            timeout=timeout,
        )

    def run_in_activated_env(
        self,
        env: str,
        *commands: str,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Activate conda env ``env`` in this shell, then run ``commands`` in it.

        The activated-shell counterpart of the ``conda`` runner. Activation lasts
        only for one shell invocation, so pass each step as a separate command.
        Commands run in order and stop at the first failure, so a single
        ``assert_ok()`` confirms every command succeeded. Example:
        ``run_in_activated_env(name, "conda install -y numpy", "conda list")``.

        Args:
            env: Name of the conda environment to activate.
            commands: Commands to run, in order, after activation.
            timeout: Seconds before the process is killed (None = no limit).

        Returns:
            CommandResult: The exit code and captured stdout/stderr.

        """
        script = _build_activate_script(self.shell, env, *commands, conda_exe=self._conda_exe)
        return self.run(script, timeout=timeout)

    # convenience alias so call sites read like `shell("conda --version")`
    __call__ = run


def _build_activate_script(
    shell: Shell,
    env: str,
    *commands: str,
    conda_exe: str = "conda",
) -> str:
    """Build the script that activates ``env`` in ``shell`` and runs ``commands``.

    Internal builder behind :meth:`CondaShellRunner.run_in_activated_env`. On the
    POSIX branch ``env`` is shell-quoted and ``commands`` are interpolated
    verbatim. Steps are chained to stop at the first failure, so the exit code
    reflects whether all of them succeeded.

    Args:
        shell: The shell the script targets.
        env: Name of the conda environment to activate.
        commands: Commands to run, in order, after activation.
        conda_exe: The conda executable used to emit the activation hook.

    Returns:
        str: A command string ready to pass to :meth:`CondaShellRunner.run`.

    """
    if shell in (Shell.BASH, Shell.ZSH, Shell.SH):
        exe = shlex.quote(conda_exe)
        hook_name = {Shell.BASH: "bash", Shell.ZSH: "zsh", Shell.SH: "posix"}[shell]
        activate = f'eval "$({exe} shell.{hook_name} hook)" && conda activate {shlex.quote(env)}'
        return " && ".join([activate, *commands])
    if shell in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL):
        # PowerShell's ';' doesn't stop on failure, so exit after any step that
        # sets a non-zero native exit code.
        guard = "if ($LASTEXITCODE) { exit $LASTEXITCODE }"
        hook = f'(& "{conda_exe}" shell.powershell hook) | Out-String | Invoke-Expression'
        steps = (hook, f"conda activate {env}", *commands)
        return "; ".join(f"{step}; {guard}" for step in steps)
    if shell is Shell.CMD:
        activate = f'"{conda_exe}" activate {env}'
        return " && ".join([activate, *commands])
    raise AssertionError(f"unhandled shell: {shell}")
