"""Terminal surface: allow-listed commands, no shell.

A command is a CommandSpec: a program name, the flags it may carry, and whether its positional
arguments are jail-relative paths or not allowed at all. The model names a command element and
gives the argument text; code splits it (shlex, no expansion, no shell), validates every token
and only then hands argv to a Runner. Anything outside the list is refused. The default list is
read-only; a deployment may add commands with read_only=False, which are classed irreversible
and need a named approver.

The Runner protocol is the seam for the platform sandbox runner: it receives only validated
argv, a scrubbed environment, a timeout and an output cap. SubprocessRunner is the plain local
one (no shell, fixed PATH, stdin closed, output and time capped, the process group killed).
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Protocol, Sequence, Tuple

from velaris.control.checkpoint import Journal
from velaris.control.core import IRREVERSIBLE, READ, Action, ActResult, Element, Observation, Refused, Surface, sha
from velaris.control.files import resolve_in

SAFE_PATH = "/usr/bin:/bin"
_TOKEN = re.compile(r"[A-Za-z0-9_./=-]{1,200}\Z")


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str = ""
    truncated: bool = False
    timed_out: bool = False


class Runner(Protocol):
    def run(self, argv: Sequence[str], *, cwd: str, env: Mapping[str, str], timeout: float,
            max_output: int) -> RunResult: ...


class SubprocessRunner:
    """Runs validated argv on this host. Only the terminal surface calls it, after the allow-list."""

    def run(self, argv: Sequence[str], *, cwd: str, env: Mapping[str, str], timeout: float,
            max_output: int) -> RunResult:
        if "/" in argv[0]:
            raise Refused("bad_program", "programs are named, not given as paths")
        exe = shutil.which(argv[0], path=SAFE_PATH)
        if exe is None:
            raise Refused("command_unavailable", "not installed in the standard locations")
        proc = subprocess.Popen([exe, *argv[1:]], shell=False, cwd=cwd, env=dict(env), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            out, err = proc.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
            timed_out = True
        cut = len(out) > max_output or len(err) > max_output
        return RunResult(proc.returncode, out[:max_output].decode("utf-8", "replace"),
                         err[:max_output].decode("utf-8", "replace"), cut, timed_out)


@dataclass(frozen=True)
class CommandSpec:
    name: str
    flags: FrozenSet[str] = frozenset()
    paths: bool = False                 # positional arguments are jail-relative paths
    max_args: int = 4
    read_only: bool = True


def _spec(name: str, flags: str = "", paths: bool = False, **kw: Any) -> CommandSpec:
    return CommandSpec(name, frozenset(flags.split()), paths, **kw)


DEFAULT_ALLOW: Tuple[CommandSpec, ...] = (
    _spec("uname", "-a -s -r -m"), _spec("df", "-h -k"), _spec("uptime"), _spec("date"), _spec("whoami"),
    _spec("hostname"), _spec("ls", "-l -a -la -h -1", paths=True), _spec("wc", "-l -c -w", paths=True),
    _spec("du", "-s -h -sh -k", paths=True),
)


def argv_for(spec: CommandSpec, text: Optional[str], cwd: Path) -> List[str]:
    """Validate the argument text for `spec`. Raises Refused; never expands or interprets anything."""
    try:
        tokens = shlex.split(text or "", posix=True)
    except ValueError:
        raise Refused("bad_arguments", "unbalanced quotes") from None
    if len(tokens) > spec.max_args:
        raise Refused("bad_arguments", "too many arguments")
    for t in tokens:
        if not _TOKEN.match(t):
            raise Refused("bad_arguments", "characters outside the safe set")
        if t.startswith("-"):
            if t not in spec.flags:
                raise Refused("bad_arguments", f"flag {t} is not allowed for {spec.name}")
        elif not spec.paths:
            raise Refused("bad_arguments", f"{spec.name} takes no positional arguments")
        else:
            resolve_in(cwd.resolve(), t)           # inside the jail, no symlinks
    return [spec.name, *tokens]


class TerminalSurface(Surface):
    kind = "terminal"

    def __init__(self, cwd: Any, *, allow: Sequence[CommandSpec] = DEFAULT_ALLOW, runner: Optional[Runner] = None,
                 journal: Optional[Journal] = None, timeout: float = 10.0, max_output: int = 8000) -> None:
        self.cwd = Path(cwd).resolve()
        if not self.cwd.is_dir():
            raise Refused("no_such_dir", "the working directory does not exist")
        self.allow = {s.name: s for s in allow}
        self.runner, self.journal = runner or SubprocessRunner(), journal
        self.timeout, self.max_output = timeout, max_output

    def _raw(self) -> Tuple[List[Dict[str, Any]], str, str]:
        els = [{"role": "command", "name": s.name, "value": ("read-only; " if s.read_only else "CHANGES THINGS; ")
                + "flags " + (" ".join(sorted(s.flags)) or "none") + ("; paths" if s.paths else "")}
               for s in sorted(self.allow.values(), key=lambda s: s.name)]
        return els, "allow-listed commands", f"terminal:{self.cwd.name}"

    def _spec(self, el: Element) -> CommandSpec:
        spec = self.allow.get(el.name)
        if el.role != "command" or spec is None:
            raise Refused("not_allow_listed", "not an allow-listed command")
        return spec

    def classify(self, action: Action, el: Element) -> str:
        if action.kind != "run":
            raise Refused("unsupported_action", action.kind)
        spec = self._spec(el)
        argv_for(spec, action.value, self.cwd)                       # arguments must validate to be classified at all
        return READ if spec.read_only else IRREVERSIBLE

    def _do(self, action: Action, el: Element, obs: Observation) -> ActResult:
        spec = self._spec(el)
        argv = argv_for(spec, action.value, self.cwd)
        env = {"PATH": SAFE_PATH, "LANG": "C", "LC_ALL": "C", "HOME": str(self.cwd)}
        if self.journal is None:
            raise Refused("no_checkpoint_store", "commands are not run without a journal")
        op = self.journal.append("terminal.run", READ if spec.read_only else IRREVERSIBLE,
                                 {"argv": argv, "rc": None})
        res = self.runner.run(argv, cwd=str(self.cwd), env=env, timeout=self.timeout, max_output=self.max_output)
        self.journal.update(op, {"argv": argv, "rc": res.returncode, "out_sha": sha(res.stdout.encode()),
                                 "timed_out": res.timed_out})
        out = res.stdout + (f"\n[stderr] {res.stderr}" if res.stderr else "")
        if res.timed_out:
            out += "\n[timed out]"
        return ActResult(res.returncode == 0 and not res.timed_out, out[:self.max_output],
                         data={"returncode": res.returncode})
