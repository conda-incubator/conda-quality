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

    @property
    def activation_error_code(self) -> int:
        """Exit code this shell surfaces when ``conda activate`` fails.

        Specific to activation through the conda hook:
        POSIX shells and PowerShell propagate conda's own exit 1, while ``cmd``'s
        activation wrapper maps any activation failure to errorlevel 2. This is
        *not* a general conda error code — e.g. argparse/usage errors exit 2 and
        ordinary ``CondaError``s exit 1, regardless of the shell.
        """
        return 2 if self is Shell.CMD else 1

    @property
    def hook_name(self) -> str:
        """The name conda uses in ``conda shell.<name> hook``.

        Matches :attr:`value` except where conda's name differs from the
        executable's: ``sh`` uses the ``posix`` hook and ``pwsh`` uses the
        ``powershell`` hook. ``cmd`` has no hook and raises.
        """
        if self in (Shell.BASH, Shell.ZSH):
            return self.value
        if self is Shell.SH:
            return "posix"
        if self in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL):
            return "powershell"
        raise AssertionError(f"{self} has no conda shell hook")

    def wrap_with_hook(self, script: str, *, conda_exe: str = "conda") -> str:
        """Prefix ``script`` with conda's shell hook so ``conda`` is the function.

        Mirrors an initialised interactive shell, so ``activate``/``deactivate``
        behave as users see them. ``cmd`` has no hook (conda runs via
        ``conda.bat`` on ``PATH``) and is returned unchanged. On PowerShell,
        ``exit $LASTEXITCODE`` is appended because ``pwsh -Command`` can
        otherwise return 0 even when a command failed, hiding the failure.

        Args:
            script: Command string to run once the hook is sourced.
            conda_exe: The conda executable used to emit the hook.

        Returns:
            str: The wrapped command string.

        """
        if self in (Shell.BASH, Shell.ZSH, Shell.SH):
            exe = shlex.quote(conda_exe)
            return f'eval "$({exe} shell.{self.hook_name} hook)" && {script}'
        if self in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL):
            guard = "if ($LASTEXITCODE) { exit $LASTEXITCODE }"
            hook = f'(& "{conda_exe}" shell.{self.hook_name} hook) | Out-String | Invoke-Expression'
            # Work around Conda.psm1 on some pwsh builds where the module's
            # alias forwards $Env:_CE_M/$Env:_CE_CONDA as empty positional
            # args, making conda see an invalid empty COMMAND. Rebind conda to
            # a local wrapper that omits those args while preserving activate/
            # deactivate behavior via shell.powershell activate/deactivate.
            set_other_args = (
                " if ($Args.Count -ge 2) { $OtherArgs = $Args[1..($Args.Count - 1)] }"
                " else { $OtherArgs = @() };"
            )
            activate_cmd = (
                f' "activate" {{ $activateCommand = (& "{conda_exe}" '
                "shell.powershell activate @OtherArgs | Out-String); "
                "Invoke-Expression -Command $activateCommand }}"
            )
            deactivate_cmd = (
                f' "deactivate" {{ $deactivateCommand = (& "{conda_exe}" '
                "shell.powershell deactivate | Out-String); "
                "if ($deactivateCommand.Trim().Length -gt 0) "
                "{ Invoke-Expression -Command $deactivateCommand } }}"
            )
            fix_alias = "".join(
                [
                    "function global:Invoke-CondaFixed {",
                    f' if ($Args.Count -eq 0) {{ & "{conda_exe}"; return }};',
                    " $Command = $Args[0];",
                    set_other_args,
                    " switch ($Command) {",
                    activate_cmd,
                    deactivate_cmd,
                    f' default {{ & "{conda_exe}" $Command @OtherArgs }}',
                    " }",
                    "}; Set-Alias conda Invoke-CondaFixed -Force",
                ]
            )
            return f"{hook}; {fix_alias}; {guard}; {script}; exit $LASTEXITCODE"
        if self is Shell.CMD:
            return script
        raise AssertionError(f"unhandled shell: {self}")

    def activate_script(self, env: str, *commands: str, conda_exe: str = "conda") -> str:
        """Build a script that activates ``env`` then runs ``commands`` in it.

        Steps are chained to stop at the first failure, so one ``assert_ok()``
        confirms them all. The hook is added separately by
        :meth:`wrap_with_hook` (``cmd`` has none, so the bare binary is used).

        Args:
            env: Name of the conda environment to activate.
            commands: Commands to run, in order, after activation.
            conda_exe: The conda executable (used only on ``cmd``, which has no hook).

        Returns:
            str: A command string for :meth:`CondaShellRunner.run`.

        """
        if self in (Shell.BASH, Shell.ZSH, Shell.SH):
            activate = f"conda activate {shlex.quote(env)}"
            return " && ".join([activate, *commands])
        if self in (Shell.POWERSHELL, Shell.WINDOWS_POWERSHELL):
            # ';' doesn't stop on failure, so exit after any step with a non-zero code.
            guard = "if ($LASTEXITCODE) { exit $LASTEXITCODE }"
            steps = (f"conda activate {env}", *commands)
            return "; ".join(f"{step}; {guard}" for step in steps)
        if self is Shell.CMD:
            activate = f'"{conda_exe}" activate {env}'
            return " && ".join([activate, *commands])
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
        conda_exe: The conda executable used to emit the shell hook in
            :meth:`run`. Defaults to ``conda`` on ``PATH``.

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
        """Source conda's shell hook, then run ``script`` in the shell.

        The hook makes ``conda`` resolve to the shell *function* (as in an
        initialised interactive shell), so ``activate``/``deactivate`` behave as
        users see them. For the bare binary use the ``conda`` fixture
        (:class:`~conda_e2e.runner.CliRunner`).

        Args:
            script: The command string the shell will run.
            extra_env: Environment overrides merged onto ``environ``.
            cwd: Per-call working directory override.
            stdin: Optional text piped to the shell's standard input.
            timeout: Seconds before the process is killed (None = no limit).

        Returns:
            CommandResult: The exit code and captured stdout/stderr.

        """
        command = self.shell.wrap_with_hook(script, conda_exe=self._conda_exe)
        if self.shell is Shell.CMD:
            # On cmd, passing the command as an argument list mangles the quoted
            # path inside the script, so build and run it as one raw string.
            exe = self._runner.resolved_path
            flags = " ".join(self.shell.command_flags)
            cmdline = f'"{exe}" {flags} "{command}"'
            return self._runner.run_raw(
                cmdline, extra_env=extra_env, cwd=cwd, stdin=stdin, timeout=timeout
            )
        return self._runner.run(
            *self.shell.command_flags,
            command,
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
        """Activate ``env`` in this shell, then run ``commands`` in it.

        The activated-shell counterpart of the ``conda`` runner. Activation lasts
        one shell invocation, so pass each step separately; steps stop at the
        first failure, so one ``assert_ok()`` confirms them all. Example:
        ``run_in_activated_env(name, "conda install -y numpy", "conda list")``.

        Args:
            env: Name of the conda environment to activate.
            commands: Commands to run, in order, after activation.
            timeout: Seconds before the process is killed (None = no limit).

        Returns:
            CommandResult: The exit code and captured stdout/stderr.

        """
        script = self.shell.activate_script(env, *commands, conda_exe=self._conda_exe)
        return self.run(script, timeout=timeout)

    # convenience alias so call sites read like `conda_shell("conda --version")`
    __call__ = run
