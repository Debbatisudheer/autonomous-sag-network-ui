from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


class RealDataAcquisitionError(RuntimeError):
    """Raised when a public real-data acquisition cannot be verified."""


@dataclass(frozen=True)
class PublicDatasetSpec:
    name: str
    version: str
    url: str
    source_page: str
    expected_md5: str
    evidence_class: str = "PUBLIC DATA"


OPS_SAT_AD_V2 = PublicDatasetSpec(
    name="OPSSAT-AD segments.csv",
    version="v2",
    url="https://zenodo.org/records/15108715/files/segments.csv?download=1",
    source_page="https://zenodo.org/records/15108715",
    expected_md5="72f109630abb933a386106897a631188",
)


def fingerprint_file(path: Path) -> tuple[str, str, int]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest(), size


def acquire_public_dataset(
    spec: PublicDatasetSpec,
    destination: Path,
    *,
    timeout_s: float = 60.0,
) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(spec.url, headers={"User-Agent": "autonomous-sag-network/1.0"})
    try:
        with urlopen(request, timeout=timeout_s) as response, destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise RealDataAcquisitionError(
            f"failed to download public dataset: {spec.name}"
        ) from exc

    sha256, md5, size = fingerprint_file(destination)
    if md5 != spec.expected_md5:
        destination.unlink(missing_ok=True)
        raise RealDataAcquisitionError(
            f"checksum mismatch for {spec.name}: expected MD5 {spec.expected_md5}, got {md5}"
        )

    manifest = {
        "dataset": spec.name,
        "version": spec.version,
        "source_uri": spec.url,
        "source_page": spec.source_page,
        "evidence_class": spec.evidence_class,
        "md5": md5,
        "sha256": sha256,
        "bytes": size,
        "verified": True,
        "network_mutation": False,
    }
    manifest_path = destination.with_suffix(destination.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
