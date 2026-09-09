"""
Velaris Agent Router
Dynamically discovers and loads all agents from the agents directory.
"""
import os
import importlib
from pathlib import Path


class AgentRouter:
    def __init__(self):
        self._agents = {}
        self._load_all_agents()

    def _load_all_agents(self):
        agents_dir = Path(__file__).parent
        for agent_folder in agents_dir.iterdir():
            if agent_folder.is_dir() and not agent_folder.name.startswith("_"):
                main_file = agent_folder / "main.py"
                if main_file.exists():
                    try:
                        module_path = f"velaris.agents.{agent_folder.name}.main"
                        module = importlib.import_module(module_path)
                        self._agents[agent_folder.name] = module
                    except Exception as e:
                        # Log silently — broken agents don't crash the router
                        pass

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
                except Exception:
                    pass
        return results


router = AgentRouter()
