from __future__ import annotations

import hashlib
import json
import math
import sys
import time
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sag_network.air_segment.engine import default_air_network
from sag_network.cross_domain_sag.engine import CrossDomainSAGIntegrationEngine, default_cross_domain_users
from sag_network.cross_domain_sag.models import CrossDomainSAGEvidence
from sag_network.closed_loop_autonomy.engine import ClosedLoopAutonomyConfig, ClosedLoopAutonomyEngine
from sag_network.domain.unified import NetworkDomain
from sag_network.ephemeris.sgp4 import SGP4EphemerisProvider
from sag_network.ephemeris.models import EphemerisSimulationConfig, EphemerisSourceType, RealSatelliteDefinition
from sag_network.ephemeris.reference import SimulationEphemerisAdapter
from sag_network.ephemeris.tle import parse_tle_text, tle_epoch_utc, tle_to_orbital_elements
from sag_network.ground_segment.engine import default_ground_network
from sag_network.resilience_campaign import ResilienceCampaignConfig, ResilienceCampaignEngine, default_resilience_scenarios
from sag_network.space.orbit import propagate_satellite_state
from sag_network.space.real_connectivity import RealEphemerisConstellation
from sag_network.telemetry.models import TelemetryMetric, TelemetryRecord
from sag_network.domain.unified import NetworkDomain

STATIC = ROOT / "showcase"
WORLD_MAP_PATH = STATIC / "world_map.png"
TLE_PATH = ROOT / "data" / "ephemeris" / "iss-zarya.tle"
GEOJSON_PATH = ROOT / "data" / "geospatial" / "ground-reference-india.geojson"


def synthetic_records(count: int = 16):
    return [
        TelemetryRecord(
            record_id=f"showcase-synthetic-{i}",
            timestamp_s=float(i),
            sequence=i,
            source_id="showcase-synthetic",
            domain=NetworkDomain.GROUND,
            metric=TelemetryMetric.LATENCY_MS,
            value=5.0 + i * 0.1,
            unit="ms",
        )
        for i in range(count)
    ]


def run_phase77(mode: str):
    evidence = CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    use_real_ephemeris = False
    records = synthetic_records()
    if mode == "sgp4":
        evidence = CrossDomainSAGEvidence.PUBLIC_EPHEMERIS
        use_real_ephemeris = True
    elif mode == "udp":
        evidence = CrossDomainSAGEvidence.LOCAL_NETWORK_TEST
    report = ClosedLoopAutonomyEngine().run(
        records,
        config=ClosedLoopAutonomyConfig(
            timestamps_s=[0.0, 15.0, 60.0, 120.0, 300.0, 600.0, 1200.0, 2400.0],
            user_demand_bps={
                "sag-user-01": 10e6,
                "sag-user-02": 10e6,
                "sag-user-03": 10e6,
            },
            use_real_ephemeris=use_real_ephemeris,
            use_udp_loopback=(mode == "udp"),
            timeout_s=1.0,
        ),
        evidence_class=evidence,
    )
    return report.model_dump(mode="json")


def run_phase78(mode: str):
    evidence = CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    use_real_ephemeris = False
    if mode == "sgp4":
        evidence = CrossDomainSAGEvidence.PUBLIC_EPHEMERIS
        use_real_ephemeris = True
    elif mode == "udp":
        evidence = CrossDomainSAGEvidence.LOCAL_NETWORK_TEST
    report = ResilienceCampaignEngine().run(
        synthetic_records(),
        default_resilience_scenarios(),
        config=ResilienceCampaignConfig(
            timestamps_s=[
                0.0, 300.0, 600.0, 900.0, 1200.0, 1500.0,
                1800.0, 2100.0, 2400.0, 2700.0, 3000.0,
            ],
            user_demand_bps={
                "sag-user-01": 10e6,
                "sag-user-02": 10e6,
                "sag-user-03": 10e6,
            },
            use_real_ephemeris=use_real_ephemeris,
            use_udp_loopback=(mode == "udp"),
            timeout_s=1.0,
        ),
        evidence_class=evidence,
    )
    return report.model_dump(mode="json")


def ecef_to_geo(x: float, y: float, z: float):
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(8):
        sin_lat = math.sin(lat)
        n = a / math.sqrt(1 - e2 * sin_lat * sin_lat)
        alt = p / max(math.cos(lat), 1e-12) - n
        lat = math.atan2(z, p * (1 - e2 * n / (n + alt)))
    return math.degrees(lat), math.degrees(lon)


def satellite_geo_from_analytic(timestamp_s: float):
    tle = parse_tle_text(TLE_PATH.read_text(encoding="utf-8"), source="bundled-celestrak-fixture")
    elements = tle_to_orbital_elements(tle)
    state = propagate_satellite_state(elements, timestamp_s)
    lat, lon = ecef_to_geo(
        state.position_ecef.x_m,
        state.position_ecef.y_m,
        state.position_ecef.z_m,
    )
    alt = math.sqrt(
        state.position_ecef.x_m**2 + state.position_ecef.y_m**2 + state.position_ecef.z_m**2
    ) - 6378137.0
    return lat, lon, alt


def satellite_geo_from_sgp4(timestamp_s: float):
    text = TLE_PATH.read_text(encoding="utf-8")
    record = parse_tle_text(
        text,
        source="https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
    )
    epoch = tle_epoch_utc(record)
    provider = SGP4EphemerisProvider.from_tle(record, satellite_id="iss-25544")
    adapter = SimulationEphemerisAdapter(
        provider,
        EphemerisSimulationConfig(simulation_epoch_utc=epoch),
    )
    state = adapter.state_at(timestamp_s)
    lat, lon = ecef_to_geo(
        state.position_ecef_m[0],
        state.position_ecef_m[1],
        state.position_ecef_m[2],
    )
    alt = math.sqrt(sum(v * v for v in state.position_ecef_m)) - 6378137.0
    return lat, lon, alt


def city_reference_points():
    if not GEOJSON_PATH.exists():
        return []
    doc = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    refs = []
    for feature in doc.get("features", []):
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates")
        if geometry.get("type") != "Point" or not coords:
            continue
        props = feature.get("properties", {})
        refs.append(
            {
                "id": props.get("site_id", "reference"),
                "name": props.get("name", props.get("site_id", "reference")),
                "lat": float(coords[1]),
                "lon": float(coords[0]),
            }
        )
    return refs


def topology(timestamp_s: float, mode: str):
    users = default_cross_domain_users()
    ground = default_ground_network()
    air = default_air_network()
    nodes = []
    for cell in ground.cells:
        nodes.append({
            "id": cell.cell_id,
            "domain": "ground",
            "lat": cell.position.latitude_deg,
            "lon": cell.position.longitude_deg,
            "alt_m": cell.position.altitude_m,
        })
    for platform in air.platforms:
        pos = platform.position_at(timestamp_s)
        nodes.append({
            "id": platform.platform_id,
            "domain": "air",
            "lat": pos.latitude_deg,
            "lon": pos.longitude_deg,
            "alt_m": pos.altitude_m,
        })
    for user in users:
        pos = user.position_at(timestamp_s)
        nodes.append({
            "id": user.user_id,
            "domain": "user",
            "lat": pos.latitude_deg,
            "lon": pos.longitude_deg,
            "alt_m": pos.altitude_m,
        })

    use_sgp4 = mode == "sgp4"
    if use_sgp4:
        lat, lon, alt = satellite_geo_from_sgp4(timestamp_s)
        sat_id = "iss-25544"
    else:
        lat, lon, alt = satellite_geo_from_analytic(timestamp_s)
        sat_id = "iss-25544-analytical"
    nodes.append({"id": sat_id, "domain": "space", "lat": lat, "lon": lon, "alt_m": alt})

    orbit = []
    for dt in range(-1800, 1801, 120):
        ts = max(0.0, timestamp_s + float(dt))
        try:
            olat, olon, oalt = satellite_geo_from_sgp4(ts) if use_sgp4 else satellite_geo_from_analytic(ts)
            orbit.append({"timestamp_s": ts, "lat": olat, "lon": olon, "alt_m": oalt})
        except Exception:
            continue

    ground_center = {
        "lat": sum(c.position.latitude_deg for c in ground.cells) / len(ground.cells),
        "lon": sum(c.position.longitude_deg for c in ground.cells) / len(ground.cells),
    }
    return {
        "nodes": nodes,
        "orbit": orbit,
        "reference_cities": city_reference_points(),
        "center": ground_center,
        "timestamp_s": timestamp_s,
    }


def cross_domain_at(timestamp_s: float, mode: str):
    evidence = CrossDomainSAGEvidence.PUBLIC_EPHEMERIS if mode == "sgp4" else CrossDomainSAGEvidence.SYNTHETIC_FIXTURE
    report = CrossDomainSAGIntegrationEngine().run(
        synthetic_records(),
        config=__import__(
            "sag_network.cross_domain_sag", fromlist=["CrossDomainSAGConfig"]
        ).CrossDomainSAGConfig(
            reference_time_s=timestamp_s,
            user_demand_bps={
                "sag-user-01": 10e6,
                "sag-user-02": 10e6,
                "sag-user-03": 10e6,
            },
            use_real_ephemeris=(mode == "sgp4"),
            timeout_s=1.0,
        ),
        evidence_class=evidence,
    )
    return report.model_dump(mode="json")


def event_payload(report, cycle, index, mode):
    return {
        "type": "cycle",
        "index": index,
        "total_cycles": len(report["cycles"]),
        "cycle": cycle,
        "summary": report["summary"],
        "evidence_class": report["evidence_class"],
        "telemetry_loop": report["telemetry_loop"],
        "propagation_model": report["propagation_model"],
        "ephemeris_source": report["ephemeris_source"],
        "network_mutation": report["network_mutation"],
        "hardware_measurement": report["hardware_measurement"],
        "external_network_used": report["external_network_used"],
        "mode": mode,
        "fingerprint": report["integration_fingerprint"],
        "topology": topology(cycle["timestamp_s"], mode),
    }


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, body: bytes, content_type: str = "text/plain; charset=utf-8", status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self.send_bytes((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if parsed.path == "/app.js":
            return self.send_bytes((STATIC / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        if parsed.path == "/styles.css":
            return self.send_bytes((STATIC / "styles.css").read_bytes(), "text/css; charset=utf-8")
        if parsed.path == "/world_map.png":
            return self.send_bytes(WORLD_MAP_PATH.read_bytes(), "image/png")
        if parsed.path == "/api/topology":
            q = parse_qs(parsed.query)
            try:
                ts = float(q.get("time", ["0"])[0])
            except ValueError:
                ts = 0.0
            mode = q.get("mode", ["synthetic"])[0]
            if mode not in {"synthetic", "sgp4", "udp"}:
                mode = "synthetic"
            payload = topology(max(0.0, ts), mode)
            payload["mode"] = mode
            payload["evidence_class"] = (
                CrossDomainSAGEvidence.PUBLIC_EPHEMERIS.value if mode == "sgp4"
                else CrossDomainSAGEvidence.LOCAL_NETWORK_TEST.value if mode == "udp"
                else CrossDomainSAGEvidence.SYNTHETIC_FIXTURE.value
            )
            return self.send_bytes(json.dumps(payload).encode(), "application/json; charset=utf-8")
        if parsed.path == "/api/events":
            mode = parse_qs(parsed.query).get("mode", ["synthetic"])[0]
            if mode not in {"synthetic", "sgp4", "udp"}:
                mode = "synthetic"
            report = run_phase77(mode)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            meta = {
                "type": "start",
                "evidence_class": report["evidence_class"],
                "mode": mode,
                "summary": report["summary"],
                "telemetry_loop": report["telemetry_loop"],
                "propagation_model": report["propagation_model"],
                "ephemeris_source": report["ephemeris_source"],
                "fingerprint": report["integration_fingerprint"],
                "network_mutation": report["network_mutation"],
                "hardware_measurement": report["hardware_measurement"],
                "external_network_used": report["external_network_used"],
                "topology": topology(report["cycles"][0]["timestamp_s"], mode),
            }
            self.wfile.write(("data: " + json.dumps(meta) + "\n\n").encode())
            self.wfile.flush()
            try:
                for index, cycle in enumerate(report["cycles"]):
                    payload = event_payload(report, cycle, index, mode)
                    self.wfile.write(("data: " + json.dumps(payload) + "\n\n").encode())
                    self.wfile.flush()
                    time.sleep(0.65)
                self.wfile.write(("data: " + json.dumps({"type": "complete", "summary": report["summary"], "fingerprint": report["integration_fingerprint"]}) + "\n\n").encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if parsed.path == "/api/candidates":
            q = parse_qs(parsed.query)
            ts = float(q.get("time", ["2400"])[0])
            user_id = q.get("user", ["sag-user-01"])[0]
            mode = q.get("mode", ["synthetic"])[0]
            if mode not in {"synthetic", "sgp4"}:
                mode = "synthetic"
            report = cross_domain_at(ts, mode)
            user_snapshot = next((u for u in report["unified_snapshot"]["associations"] if u["user_id"] == user_id), None)
            if user_snapshot is None:
                return self.send_bytes(b"{\"error\":\"unknown user\"}", "application/json; charset=utf-8", 404)
            return self.send_bytes(json.dumps(user_snapshot).encode(), "application/json; charset=utf-8")
        if parsed.path == "/api/resilience":
            mode = parse_qs(parsed.query).get("mode", ["synthetic"])[0]
            if mode not in {"synthetic", "sgp4", "udp"}:
                mode = "synthetic"
            report = run_phase78(mode)
            return self.send_bytes(json.dumps(report).encode(), "application/json; charset=utf-8")
        self.send_bytes(b"Not found", status=404)


if __name__ == "__main__":
    port = int(os.environ.get("SAG_SHOWCASE_PORT", "8765"))
    print(f"SAG Live Showcase v1.3: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
