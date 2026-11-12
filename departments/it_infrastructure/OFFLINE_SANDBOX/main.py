"""OFFLINE_SANDBOX: run a small allow-list of read-only commands, contained as a process.

THIS IS PROCESS ISOLATION, NOT A SECURITY SANDBOX. There is no namespace,
seccomp, chroot or resource limit: a command here runs as the current user. What
this agent does guarantee is narrower and exact:

  - only the commands in allowed() run, resolved to a binary in /usr/bin or /bin
  - no shell: arguments are passed as a list, so nothing is expanded or chained
  - an argument may not contain "/" or "..", start with "~" or hold a NUL, so a
    file operand can only name a file in the working directory
  - an argument starting with "-" must be one of that command's _FLAGS, exactly
    (no bundling, no long options, no "--"); a flag that takes a value is followed
    by a count. This shuts out option-driven escapes such as GNU
    `wc --files0-from=FILE` or `tail --follow=name`. The allowed flags were checked
    against GNU coreutils and the macOS (BSD) tools: none of them reads a file other
    than its operands, writes anything, or runs another program
  - the working directory is a fresh temporary directory holding only the files
    the caller passed in, and it is deleted afterwards
  - the environment is replaced (PATH, LANG, HOME, TMPDIR only): no secrets leak in
  - a timeout kills the process group this agent started; output is capped

Everything else is refused. safe() answers whether a command would be allowed
without running it.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import tempfile
import time

from velaris.agentkit import infra_store

_NAME = "OFFLINE_SANDBOX"
# command -> {flag: takes a numeric value}. A command not listed takes no flags at all.
_FLAGS = {
    "cat": {"-n": False, "-b": False, "-s": False},
    "echo": {"-n": False},
    "head": {"-n": True, "-c": True},
    "tail": {"-n": True, "-c": True, "-f": False},       # -f only waits for the timeout
    "uname": {f: False for f in ("-a", "-s", "-r", "-m", "-n", "-p", "-v")},
    "wc": {"-l": False, "-w": False, "-c": False, "-m": False},
}
_COMMANDS = ("cat", "echo", "false", "head", "tail", "true", "uname", "wc")
_COUNT = re.compile(r"\+?[0-9]{1,9}")
_SEARCH_PATH = "/usr/bin:/bin"
_MAX_TIMEOUT_S = 30.0
_MAX_OUTPUT = 64 * 1024
_MAX_ARGS = 64
_MAX_INPUT = 1024 * 1024


def _refusal(argv):
    """Why argv may not run ("" when it may)."""
    if not isinstance(argv, list) or not argv or len(argv) > _MAX_ARGS or not all(isinstance(a, str) for a in argv):
        return f"argv must be a list of 1 to {_MAX_ARGS} strings"
    if argv[0] not in _COMMANDS:
        return f"command '{argv[0][:40]}' is not on the allow-list"
    flags, needs_count = _FLAGS.get(argv[0], {}), False
    for arg in argv[1:]:
        if len(arg) > 4096 or "\x00" in arg or "/" in arg or ".." in arg or arg.startswith("~"):
            return "arguments may not contain '/', '..', NUL or start with '~'"
        if needs_count:
            if not _COUNT.fullmatch(arg):
                return f"a count must follow the flag before '{arg[:40]}'"
            needs_count = False
        elif arg.startswith("-"):
            if arg not in flags:
                return f"{argv[0]} takes only the flags {sorted(flags) or 'none'}; '{arg[:40]}' is refused"
            needs_count = flags[arg]
    return "a flag is missing its count" if needs_count else ""


def _files_problem(files):
    if not isinstance(files, dict):
        return "files must be an object of {name: text}"
    for name, text in files.items():
        if not infra_store.is_name(name, 100) or name.startswith((".", "-")) or ".." in name or not isinstance(text, str):
            return "file names must be plain names and contents text"
    if sum(len(t) for t in files.values()) > _MAX_INPUT:
        return "files are larger than 1 MB in total"
    return ""


class OfflineSandbox:
    def __init__(self, name=_NAME):
        self.name = name

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def allowed(self):
        return list(_COMMANDS)

    def safe(self, payload):
        """Would this command be allowed? `payload` is an argv list or {"argv": [...]}. Runs nothing."""
        argv = payload.get("argv") if isinstance(payload, dict) else payload
        reason = _refusal(argv)
        return {"safe": not reason, "status": "refused" if reason else "ok", "reason": reason or "on the allow-list"}

    def run(self, argv, timeout_s=5.0, files=None, stdin=""):
        """Run an allow-listed command. `files` ({name: text}) are placed in its working directory."""
        files = {} if files is None else files
        reason = _refusal(argv) or _files_problem(files)
        if not reason and (not infra_store.is_number(timeout_s, 0.01, _MAX_TIMEOUT_S)):
            reason = f"timeout_s must be between 0.01 and {_MAX_TIMEOUT_S}"
        if not reason and (not isinstance(stdin, str) or len(stdin) > _MAX_INPUT):
            reason = "stdin must be text of at most 1 MB"
        if reason:
            infra_store.audit(_NAME, "refused", {"reason": reason})
            return infra_store.fail("refused", reason, ran=False)
        binary = shutil.which(argv[0], path=_SEARCH_PATH)
        if binary is None:
            return infra_store.fail("unavailable", f"{argv[0]} is not installed in {_SEARCH_PATH}", ran=False)
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="velaris-sbx-") as work, \
                tempfile.TemporaryDirectory(prefix="velaris-out-") as out_dir:
            for name, text in files.items():
                with open(os.path.join(work, name), "w", encoding="utf-8") as f:
                    f.write(text)
            env = {"PATH": _SEARCH_PATH, "LANG": "C", "HOME": work, "TMPDIR": work}
            out_path, err_path = os.path.join(out_dir, "stdout"), os.path.join(out_dir, "stderr")
            timed_out = False
            try:
                with open(out_path, "wb") as out, open(err_path, "wb") as err:
                    proc = subprocess.Popen([binary] + argv[1:], cwd=work, env=env, stdin=subprocess.PIPE,
                                            stdout=out, stderr=err, shell=False, start_new_session=True)
                    try:
                        proc.communicate(stdin.encode(), timeout=timeout_s)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        os.killpg(proc.pid, signal.SIGKILL)     # the group this call created, nothing else
                        proc.communicate()
            except OSError as e:
                return infra_store.fail("error", f"could not start the command: {e}", ran=False)
            captured = {}
            for label, path in (("stdout", out_path), ("stderr", err_path)):
                with open(path, "rb") as f:
                    captured[label] = f.read(_MAX_OUTPUT).decode("utf-8", "replace")
                captured[label + "_truncated"] = os.path.getsize(path) > _MAX_OUTPUT
        infra_store.audit(_NAME, "run", {"command": argv[0], "args": len(argv) - 1, "exit_code": proc.returncode,
                                         "timed_out": timed_out})
        return {"status": "timeout" if timed_out else "ok", "ran": True, "exit_code": proc.returncode,
                "seconds": round(time.monotonic() - start, 4), **captured}
