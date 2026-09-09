"""
Velaris Backend Engine
Central engine that loads the agent router and exposes platform APIs.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velaris.agents.router import router


class BackendEngine:
    def __init__(self):
        self.router = router

    def list_agents(self):
        return self.router.list_agents()

    def get_agent(self, name):
        return self.router.get_agent(name)

    def status(self):
        return {
            "status": "online",
            "agents_loaded": self.router.count(),
            "agent_list": self.router.list_agents()
        }


backend = BackendEngine()
