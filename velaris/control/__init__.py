"""The control layer: a person types a prompt, the system does narrow, scripted work in an
interface (files, terminal, browser) with every step logged and as much as possible reversible.

  core        Surface interface, observations with snapshot ids, actions, action classes
  checkpoint  content-addressed copies of what was touched + an operation journal + undo
  files / terminal / browser / desktop   the surfaces (jailed files; allow-listed commands;
              a Playwright browser behind an optional import; a documented desktop stub)
  fake        a scripted browser driver for tests
  policy      per-task action schema and the allow / approve / deny decision
  tasks, library   what a task is, and the seeded tasks (anything else is refused)
  planner     the model-proposes loop on velaris.intel.flow
  replay      record a run, replay it without a model; fail closed on drift
  report      the run report; service: runs, approvals, undo, kill; api: HTTP endpoints

A model proposes; code decides. Observed content is data: screened, fenced, never obeyed.
"""
