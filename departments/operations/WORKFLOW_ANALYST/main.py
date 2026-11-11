"""Workflow analyst agent: understand a company's existing automation and how work really flows.

Thin wrapper over velaris.intel.workflow and velaris.intel.process_mining,
where the logic and its tests live. Deterministic: no model, no network,
and it never runs the workflow it reads.
"""
from typing import Any, Dict, List, Union

from velaris.intel import process_mining, workflow


class WorkflowAnalyst:
    def health_check(self) -> Dict[str, Any]:
        return {"agent": "WORKFLOW_ANALYST", "status": "ok"}

    def analyse(self, export: Union[dict, str]) -> Dict[str, Any]:
        """An n8n workflow export -> structure, plain-language plan, and the permissions a person must approve."""
        wf = workflow.load(export)
        return {"analysis": workflow.analyse(wf), "plan": workflow.to_plan(wf),
                "permissions_to_approve": workflow.required_permissions(wf)}

    def discover(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Events {case, activity, ts} -> paths taken, variants, rework and bottlenecks."""
        return process_mining.discover(events)

    def compare(self, export: Union[dict, str], events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Designed workflow vs what happened: steps taken that were never designed, and designed steps never taken."""
        return process_mining.conformance(process_mining.discover(events), workflow.load(export).main_edges())
