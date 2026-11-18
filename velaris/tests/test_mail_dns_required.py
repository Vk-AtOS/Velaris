"""KAN-108: DMARC/SPF enforcement does not depend on an optional package: dnspython is a pinned runtime requirement and the
resolver is the real one, never the stub that answers temperror to everything."""
import re
from pathlib import Path

from velaris.mail.dnsauth import UnavailableResolver
from velaris.mail.inbound import dnspython_resolver

ROOT = Path(__file__).resolve().parents[2]


def test_dnspython_is_a_pinned_runtime_dependency_and_the_default_resolver_is_real():
    assert not isinstance(dnspython_resolver(), UnavailableResolver)
    assert re.search(r"^dnspython>=", (ROOT / "requirements.txt").read_text(), re.M)
    assert re.search(r"^dnspython==\d", (ROOT / "deploy" / "constraints.txt").read_text(), re.M)
