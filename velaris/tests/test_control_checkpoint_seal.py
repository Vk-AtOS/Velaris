"""KAN-69 SV2-04: checkpoint copies of user files are sealed at rest and bound to their hash."""
import pytest

from velaris.control.checkpoint import CheckpointStore
from velaris.control.core import ControlError
from velaris.core import vault


def test_checkpoint_blobs_are_sealed_and_a_moved_blob_is_refused(tmp_path):
    st = CheckpointStore(tmp_path / "control")
    a, b = st.put(b"payroll draft"), st.put(b"lunch menu")
    path_a = st._blobs / a[:2] / a
    assert b"payroll" not in path_a.read_bytes() and vault.is_bound(path_a.read_bytes())
    assert st.get(a) == b"payroll draft"
    path_a.write_bytes((st._blobs / b[:2] / b).read_bytes())       # another sealed copy moved over it
    with pytest.raises(ControlError):
        st.get(a)
