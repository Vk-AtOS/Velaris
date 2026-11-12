"""SELF_IDENTITY: who this Velaris installation is, as a recorded, versioned fact sheet.

Keys such as name, organisation, region and owner, each a short string. A
random instance_id is assigned on first use and can never be changed, so logs
and messages from this installation can be told apart from another's. Every
change is recorded with who made it (velaris.agentkit.aicore_b_versioned);
stored owner-only under this agent's state directory; survives restart.
"""
import uuid
from typing import Any, Dict, Optional

from velaris.agentkit.aicore_b_common import health, ident
from velaris.agentkit.aicore_b_versioned import VersionedDoc

NAME = "SELF_IDENTITY"
DEFAULT = {"name": "Velaris", "model": "1.0-core"}


def _check(key: str, value: Any) -> Optional[str]:
    return None if ident(value, 200) is not None else "must be a non-empty string of at most 200 characters"


class SELF_IDENTITYAgent:
    def __init__(self):
        self.name = NAME
        self._doc = VersionedDoc(NAME, "identity.json", DEFAULT, check=_check, frozen=("instance_id",))

    @property
    def identity(self) -> Dict[str, Any]:
        doc = self._doc.current()
        if "instance_id" not in doc:
            self._doc.update({"instance_id": uuid.uuid4().hex}, "SELF_IDENTITY")
            doc = self._doc.current()
        return doc

    def health_check(self):
        return {**health(NAME), "identity": self.identity}

    def get_identity(self) -> Dict[str, Any]:
        return dict(self.identity)

    def set_identity(self, key: str, value: str, by: str = "system") -> bool:
        """True when the value was stored (or already held); False for a bad value or a frozen key."""
        self.identity                                     # make sure instance_id exists before any other change
        return self._doc.update({key: value}, by)["status"] in ("ok", "unchanged")

    def history(self, key: Optional[str] = None):
        return self._doc.history(key)
