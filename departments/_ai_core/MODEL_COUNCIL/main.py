"""Model council agent: several models answer, review each other blind, one answer comes back.

Thin wrapper over velaris.intel.council, where the pipeline and its tests live.
"""
import os
from typing import Any, Dict, List, Optional

from velaris.intel.council import council


class ModelCouncil:
    def __init__(self, models: Optional[List[str]] = None):
        # VELARIS_COUNCIL="anthropic:claude-sonnet-4-6,ollama:llama3.1:8b,..."
        self.models = models or [m.strip() for m in os.environ.get("VELARIS_COUNCIL", "").split(",") if m.strip()]

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "MODEL_COUNCIL", "status": "ok" if self.models else "no_models_configured",
                "models": self.models}

    def deliberate(self, question: str, context: str = "") -> Dict[str, Any]:
        """Returns the answer plus rankings, agreement (0..1) and `contested`.

        A contested answer is one the reviewers disagreed on: route it to a person.
        """
        if not self.models:
            return {"status": "not_configured", "answer": "", "reason": "set VELARIS_COUNCIL or pass models"}
        return council(question, models=self.models, context=context).to_dict()
