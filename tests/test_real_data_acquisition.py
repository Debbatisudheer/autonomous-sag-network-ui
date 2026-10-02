from __future__ import annotations

import hashlib
from pathlib import Path

from sag_network.real_data import fingerprint_file, OPS_SAT_AD_V2


def test_opssat_public_dataset_spec_is_explicit() -> None:
    assert OPS_SAT_AD_V2.name == "OPSSAT-AD segments.csv"
    assert OPS_SAT_AD_V2.version == "v2"
    assert OPS_SAT_AD_V2.expected_md5 == "72f109630abb933a386106897a631188"
    assert OPS_SAT_AD_V2.evidence_class == "PUBLIC DATA"
    assert "zenodo.org/records/15108715" in OPS_SAT_AD_V2.url


def test_fingerprint_file_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "fixture.csv"
    path.write_bytes(b"timestamp,channel,value\n1,sat,2\n")

    first = fingerprint_file(path)
    second = fingerprint_file(path)

    assert first == second
    assert first[2] == path.stat().st_size
    assert first[0] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert first[1] == hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
