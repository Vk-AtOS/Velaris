"""tools/check_structure.py passes on the repository: no bare/silent broad except, no file over 600 lines, imports resolve, no import cycle."""
import importlib.util
from pathlib import Path


def test_repository_passes_the_structure_gate(capsys):
    spec = importlib.util.spec_from_file_location("check_structure", Path(__file__).resolve().parents[2] / "tools" / "check_structure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0, capsys.readouterr().out
