import logging
logger = logging.getLogger("EPISODIC_MEMORY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - EPISODIC_MEMORY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class EPISODIC_MEMORYAgent:
    def __init__(self):
        self.name = "EPISODIC_MEMORY"
        self.episodes = []
        logger.debug("EPISODIC_MEMORY initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def record(self, episode: dict):
        self.episodes.append(episode)
        logger.debug("Episode recorded")

    def list_episodes(self):
        return list(self.episodes)
