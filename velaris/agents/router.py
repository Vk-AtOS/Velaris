"""
Velaris Agent Router
Discovers and loads every agent under departments/<department>/<AGENT>/main.py.
Agents are imported as velaris.agents.<AGENT>.main (see velaris/agents/__init__.py).
"""
import importlib
import logging

from velaris.agents import department_dirs

logger = logging.getLogger("velaris.router")


class AgentRouter:
    def __init__(self):
        self._agents = {}
        self.departments = {}   # agent name -> department name
        self.failed = {}        # agent name -> import error text
        self._load_all_agents()

    def _load_all_agents(self):
        for dept in department_dirs():
            for agent_folder in sorted(dept.iterdir()):
                if not (agent_folder / "main.py").exists():
                    continue
                name = agent_folder.name
                try:
                    self._agents[name] = importlib.import_module(f"velaris.agents.{name}.main")
                    self.departments[name] = dept.name
                except Exception as e:
                    # A broken agent must not crash the router, but it must be visible.
                    self.failed[name] = f"{type(e).__name__}: {e}"
                    logger.warning("Agent %s/%s failed to import: %s", dept.name, name, e)

    def list_agents(self):
        return list(self._agents.keys())

    def get_agent(self, name):
        return self._agents.get(name)

    def count(self):
        return len(self._agents)

    def publish(self, event_name: str, data: dict = None):
        """Publish an event to all registered agents."""
        results = {}
        for name, agent in self._agents.items():
            if hasattr(agent, 'on_event'):
                try:
                    results[name] = agent.on_event(event_name, data or {})
                except Exception as e:
                    logger.warning("Agent %s on_event(%s) failed: %s", name, event_name, e)
        return results


router = AgentRouter()
