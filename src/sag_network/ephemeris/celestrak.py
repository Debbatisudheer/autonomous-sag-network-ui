from __future__ import annotations

from datetime import datetime, UTC
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sag_network.ephemeris.models import OMMRecord, TLERecord
from sag_network.ephemeris.omm import parse_omm_json
from sag_network.ephemeris.tle import parse_tle_text


class CelesTrakClient:
    """Standard-library client for current CelesTrak GP element queries."""

    BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"

    def __init__(
        self,
        *,
        timeout_s: float = 15.0,
        user_agent: str = "autonomous-sag-network/0.13",
    ) -> None:
        self.timeout_s = timeout_s
        self.user_agent = user_agent

    def build_url(self, *, catalog_number: int | str, format_name: str = "TLE") -> str:
        query = urlencode({"CATNR": str(catalog_number), "FORMAT": format_name.upper()})
        return f"{self.BASE_URL}?{query}"

    def _get(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=self.timeout_s) as response:
            payload = response.read()
            if not isinstance(payload, bytes):
                raise TypeError("CelesTrak HTTP response must be bytes")
            return payload.decode("utf-8")

    def fetch_tle(self, *, catalog_number: int | str) -> TLERecord:
        """Fetch one current GP TLE from CelesTrak."""
        url = self.build_url(catalog_number=catalog_number, format_name="TLE")
        payload = self._get(url)
        lines = [line.strip() for line in payload.splitlines() if line.strip()]
        if len(lines) != 3:
            raise ValueError("CelesTrak TLE response did not contain one 3-line element set")
        record = parse_tle_text(payload, source=url, satellite_name=lines[0])
        return record.model_copy(update={"retrieved_at_utc": datetime.now(UTC)})

    def fetch_omm_json(self, *, catalog_number: int | str) -> list[OMMRecord]:
        """Fetch current GP JSON/OMM records from CelesTrak."""
        url = self.build_url(catalog_number=catalog_number, format_name="JSON")
        return parse_omm_json(self._get(url))
