# ================================================================================

import os
import tarfile
from typing import Dict, Any

from velaris.intel.paths import agent_dir

class OfflineRuntimePackager:
    """
    Offline Runtime Packager
    - Bundles Velaris modules into a tar archive
    - Ensures offline execution compatibility
    - Validates package contents before export
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("OFFLINE_RUNTIME_PACKAGER"))
        self.EXPORT_DIR = os.path.join(self.AGENT_DIR, "exports")
        os.makedirs(self.EXPORT_DIR, exist_ok=True)

    def _validate_structure(self, source_dir: str) -> bool:
        if not os.path.isdir(source_dir):
            return False
        required = ["agents", "tests"]
        for r in required:
            if not os.path.exists(os.path.join(source_dir, r)):
                return False
        return True

    def package(self, source_dir: str, out_name: str = "velaris_offline.tar") -> str:
        if not self._validate_structure(source_dir):
            raise ValueError("Invalid Velaris directory structure")

        out_path = os.path.join(self.EXPORT_DIR, out_name)

        with tarfile.open(out_path, "w") as tar:
            tar.add(source_dir, arcname="velaris")

        return out_path

    def inspect_package(self, tar_path: str) -> Dict[str, Any]:
        if not os.path.exists(tar_path):
            raise FileNotFoundError("Package not found")

        with tarfile.open(tar_path, "r") as tar:
            names = tar.getnames()

        return {"count": len(names), "files": names[:10]}

# ================================================================================