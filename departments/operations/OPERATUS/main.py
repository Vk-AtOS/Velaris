import logging
from typing import Dict, Any, List

logger = logging.getLogger("OPERATUS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - OPERATUS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class OperatusAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")
        self.handlers: Dict[str, Any] = {}

    def health_check(self):
        status = {"agent": "OPERATUS", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def register(self, step: str, handler) -> None:
        """The code that runs a step of this name."""
        if not isinstance(step, str) or not callable(handler):
            raise ValueError("register(step_name, callable)")
        self.handlers[step] = handler

    def execute_workflow(self, steps: List[str]) -> Dict[str, Any]:
        """
        Run workflow steps in order with their registered handlers. A step is "done" only if its handler ran
        and returned; a step with no handler is "not_run" and the report is "incomplete"; a handler that
        raises stops the workflow ("failed").
        """
        logger.debug("Executing workflow: %s", steps)
        report = {"steps": [], "status": "ok"}
        for s in steps:
            handler = self.handlers.get(s) if isinstance(s, str) else None
            if handler is None:
                report["steps"].append({"step": s, "result": "not_run", "reason": "no handler registered"})
                report["status"] = "incomplete"
                continue
            try:
                output = handler()
            except Exception as e:      # a handler is caller code: report it and stop, do not claim later steps ran
                logger.warning("workflow step %s failed: %s", s, e)
                report["steps"].append({"step": s, "result": "failed", "reason": f"{type(e).__name__}: {e}"})
                report["status"] = "failed"
                break
            report["steps"].append({"step": s, "result": "done", "output": output})
        logger.debug("Workflow finished: %s", report)
        return report

    def validate_inputs(self, inputs: Dict[str, Any], required: List[str]) -> bool:
        """
        Validate that required keys exist in input dictionary.
        """
        logger.debug("Validating inputs=%s required=%s", inputs, required)
        for key in required:
            if key not in inputs:
                logger.debug("Missing required key=%s", key)
                return False
        return True
