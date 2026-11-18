# ================================================================================

"""Offline runtime packager: bundles a Velaris source folder into a tar archive for offline installs, leaving secrets out.

package(source_dir, out_name="velaris_offline.tar") requires source_dir to hold "agents" and "tests" (ValueError
otherwise), writes an uncompressed tar under the top-level name "velaris" and returns its path. Files and folders
matching EXCLUDE_NAMES (.env files, keys and certificates, databases, .jsonl logs, credentials*, secrets*, .git,
virtualenvs, caches, exports) and anything that is not a plain file or folder (symlinks, devices) are never packed, and
owner ids are zeroed. out_name must be a plain file name ending in .tar (no separators, no ".."), else ValueError.
inspect_package(tar_path) returns {"count", "files": the first ten names} for a package inside this agent's exports
folder only (ValueError for any other path, FileNotFoundError if it is absent).
State: <VELARIS_DATA>/agents/OFFLINE_RUNTIME_PACKAGER/exports/, archives owner-only (0600). Exclusion is by file name, not
by content, and no caller check is made here.
"""
import fnmatch
import os
import tarfile
from typing import Dict, Any, Optional

from velaris.agentkit.secure import safe_join
from velaris.intel.paths import agent_dir

# Never packed, whatever the source folder holds: credentials, keys, local databases, VCS and caches.
EXCLUDE_NAMES = (".env", ".env.*", "*.env", "*.key", "*.pem", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "*.sec", "*.sig",
                 "*.db", "*.sqlite", "*.sqlite3", "*.jsonl", "credentials*", "secrets*", "*.token", ".netrc", ".git", ".gitignore",
                 ".venv", "venv", "node_modules", "__pycache__", "*.pyc", ".DS_Store", "exports")


def _filter(info: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    """Drop secret-bearing files and directories (EXCLUDE_NAMES), and anything that is not a plain file or folder."""
    name = os.path.basename(info.name)
    if any(fnmatch.fnmatch(name.lower(), pat) for pat in EXCLUDE_NAMES) or not (info.isfile() or info.isdir()):
        return None
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info

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

        if not isinstance(out_name, str) or not out_name.endswith(".tar"):
            raise ValueError("out_name must be a plain file name ending in .tar")
        out_path = str(safe_join(self.EXPORT_DIR, out_name))      # no separators, no '..': it stays in exports/

        with tarfile.open(out_path, "w") as tar:
            tar.add(source_dir, arcname="velaris", filter=_filter)

        os.chmod(out_path, 0o600)
        return out_path

    def inspect_package(self, tar_path: str) -> Dict[str, Any]:
        # Only packages this agent made: any other path would let a caller probe the file system.
        if not isinstance(tar_path, str) or os.path.dirname(os.path.realpath(tar_path)) != os.path.realpath(self.EXPORT_DIR):
            raise ValueError("tar_path must be a package inside this agent's exports folder")
        if not os.path.exists(tar_path):
            raise FileNotFoundError("Package not found")

        with tarfile.open(tar_path, "r") as tar:
            names = tar.getnames()

        return {"count": len(names), "files": names[:10]}

# ================================================================================