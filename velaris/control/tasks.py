"""What a task is. Anything not registered here is refused: narrow scripted tasks, not anything.

A task is a Task(...):

  id, title, surface      "files" | "terminal" | "browser"
  validate(params)        -> cleaned params, or ValueError (written for people)
  goal(params)            -> the sentence the model is given
  expected(params, s)     -> JSON computed BY CODE from the starting state (never by the model);
                          the schema's checks and the verification both use it
  actions                 {action kind: ActionSpec(roles, name_re, check, approval)}: the only
                          things the model may propose
  verify(params, exp, s, journal) -> [Check]: reads the system of record back (a fresh listing,
                          a second observation, the document library, the journal of what ran)
                          and compares with `expected`. Success is reported only if all pass.
  hosts(params)           browser tasks: the host allow-list for this run
  max_steps               the step limit of a run

To add a task, write those functions and call register(Task(...)); see velaris/control/library.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from velaris.control.checkpoint import Journal
from velaris.control.core import Surface
from velaris.control.policy import ActionSpec


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail[:300]}


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    surface: str
    validate: Callable[[Dict[str, Any]], Dict[str, Any]]
    goal: Callable[[Dict[str, Any]], str]
    expected: Callable[[Dict[str, Any], Surface], Any]
    actions: Dict[str, ActionSpec]
    verify: Callable[[Dict[str, Any], Any, Surface, Journal], List[Check]]
    hosts: Optional[Callable[[Dict[str, Any]], List[str]]] = None
    max_steps: int = 12
    description: str = ""


_TASKS: Dict[str, Task] = {}


def register(task: Task) -> Task:
    if task.id in _TASKS:
        raise ValueError(f"task {task.id} is already registered")
    _TASKS[task.id] = task
    return task


def get(task_id: Any) -> Task:
    t = _TASKS.get(task_id) if isinstance(task_id, str) else None
    if t is None:
        raise LookupError("unknown task: only the registered, scripted tasks can be run")
    return t


def listing() -> List[Dict[str, Any]]:
    return [{"id": t.id, "title": t.title, "surface": t.surface, "description": t.description,
             "actions": sorted(t.actions), "approval_steps": sorted(k for k, s in t.actions.items() if s.approval),
             "max_steps": t.max_steps} for t in sorted(_TASKS.values(), key=lambda t: t.id)]
