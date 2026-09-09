import logging
from typing import Dict, Any, List
from velaris.agents.ENGINE.main import VelarisEngine
logger = logging.getLogger('PRIME')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - PRIME - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class VelarisPrime:
    """
    PRIMARY VELARIS CONTROLLER (Your architecture version)
    
    Responsibilities:
        - Boot and control the engine.
        - Provide system-wide workflows.
        - Run diagnostics.
        - Act as the central intelligence coordination layer.
    """

    def __init__(self, config: Dict[str, Any]=None):
        self.config = config or {}
        self.engine = VelarisEngine()
        logger.debug('PRIME controller initialized.')

    def health_check(self) -> Dict[str, Any]:
        status = {'agent': 'PRIME', 'status': 'ok', 'engine_status': self.engine.health_check()}
        logger.debug('PRIME health: %s', status)
        return status

    def system_status(self) -> Dict[str, Any]:
        """
        Returns full system diagnostics across PRIME + ENGINE + REGISTRY.
        """
        data = {'prime': self.health_check(), 'engine': self.engine.health_check(), 'agents': self.engine.registry.health_all()}
        logger.debug('System status: %s', data)
        return data

    def run_simple_self_test(self):
        """
        Sentinels + Guardians pipeline test.
        """
        pipe = [{'agent': 'VIGILIS', 'method': 'health_check'}, {'agent': 'CUSTOS', 'method': 'health_check'}, {'agent': 'PRAETOR', 'method': 'health_check'}]
        return self.engine.pipeline(pipe)

    def execute(self, agent: str, method: str, params: Dict[str, Any]=None):
        logger.debug('PRIME executing %s.%s', agent, method)
        return self.engine.run(agent, method, params)

class PrimeAgent(VelarisPrime):
    """
    Backward-compatible alias so test_phase4_intel.py and system integration tests work.
    Instructions:
        - DO NOT REMOVE
        - DO NOT CHANGE THE CLASS NAME
    """

    def __init__(self, config: Dict[str, Any]=None):
        super().__init__(config)
        logger.debug('PrimeAgent (compat wrapper) loaded.')
if __name__ == '__main__':
    p = VelarisPrime()
    print(p.system_status())