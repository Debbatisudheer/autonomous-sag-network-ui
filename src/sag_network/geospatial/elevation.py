from __future__ import annotations

import json
import math
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ElevationResult:
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    source_uri: str


class USGSElevationClient:
    """USGS 3DEP point-elevation client.

    The service is US-focused. The provider is intentionally explicit so callers do not
    silently treat USGS values as globally available elevation coverage.
    """

    def __init__(
        self,
        *,
        endpoint: str = "https://epqs.nationalmap.gov/v1/json",
        timeout_s: float = 15.0,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    def elevation(self, *, latitude_deg: float, longitude_deg: float) -> ElevationResult:
        params = urlencode(
            {
                "x": longitude_deg,
                "y": latitude_deg,
                "units": "Meters",
                "output": "json",
                "wkid": 4326,
            }
        )
        url = f"{self.endpoint}?{params}"
        request = Request(url, headers={"User-Agent": "autonomous-sag-network/1.0"})
        with urlopen(request, timeout=self.timeout_s) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or "value" not in payload:
            raise ValueError("USGS EPQS response does not contain an elevation value")
        elevation = float(payload["value"])
        if math.isnan(elevation):
            raise ValueError("USGS EPQS returned NaN elevation")
        return ElevationResult(
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            elevation_m=elevation,
            source_uri=url,
        )
