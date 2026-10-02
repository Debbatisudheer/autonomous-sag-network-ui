from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping

from sag_network.ephemeris.models import OMMRecord


def parse_omm_json(text: str) -> list[OMMRecord]:
    """Parse CelesTrak/CCSDS-style OMM JSON into validated records."""
    payload = json.loads(text)
    if isinstance(payload, Mapping):
        records: list[Mapping[str, object]] = [payload]
    elif isinstance(payload, list):
        records = [item for item in payload if isinstance(item, Mapping)]
    else:
        raise TypeError("OMM JSON must contain an object or list of objects")
    if len(records) == 0:
        raise ValueError("OMM JSON contains no records")
    return [OMMRecord.model_validate(record) for record in records]


def parse_omm_csv(text: str) -> list[OMMRecord]:
    """Parse OMM CSV with standard field-name headers."""
    reader = csv.DictReader(io.StringIO(text))
    rows = [row for row in reader]
    if not rows:
        raise ValueError("OMM CSV contains no records")
    return [OMMRecord.model_validate(row) for row in rows]
