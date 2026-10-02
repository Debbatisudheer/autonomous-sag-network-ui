from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OSMSearchResult:
    """Minimal Nominatim search result retained for site ingestion."""

    osm_type: str
    osm_id: str
    display_name: str
    latitude_deg: float
    longitude_deg: float
    category: str | None
    feature_type: str | None


class NominatimClient:
    """Conservative Nominatim client for explicit, low-rate geocoding requests."""

    def __init__(
        self,
        *,
        base_url: str = "https://nominatim.openstreetmap.org",
        user_agent: str,
        minimum_interval_s: float = 1.0,
        timeout_s: float = 15.0,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("user_agent must be non-empty")
        if minimum_interval_s < 0:
            raise ValueError("minimum_interval_s must be non-negative")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.minimum_interval_s = minimum_interval_s
        self.timeout_s = timeout_s
        self._last_request_monotonic = 0.0

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        country_codes: list[str] | None = None,
    ) -> list[OSMSearchResult]:
        if not query.strip():
            raise ValueError("query must be non-empty")
        if not 1 <= limit <= 40:
            raise ValueError("limit must be between 1 and 40")
        params = {"q": query, "format": "jsonv2", "limit": str(limit)}
        if country_codes:
            params["countrycodes"] = ",".join(sorted(code.lower() for code in country_codes))
        url = f"{self.base_url}/search?{urlencode(params)}"
        self._rate_limit()
        request = Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout_s) as response:
            payload = json.load(response)
        if not isinstance(payload, list):
            raise TypeError("Nominatim search response must be a JSON array")
        results: list[OSMSearchResult] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            results.append(
                OSMSearchResult(
                    osm_type=str(item.get("osm_type", "")),
                    osm_id=str(item.get("osm_id", "")),
                    display_name=str(item.get("display_name", "")),
                    latitude_deg=float(item["lat"]),
                    longitude_deg=float(item["lon"]),
                    category=str(item["class"]) if item.get("class") is not None else None,
                    feature_type=str(item["type"]) if item.get("type") is not None else None,
                )
            )
        return results

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_monotonic
        delay = self.minimum_interval_s - elapsed
        if delay > 0:
            time.sleep(delay)
        self._last_request_monotonic = time.monotonic()
