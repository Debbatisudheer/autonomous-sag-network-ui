from __future__ import annotations

import math

from sag_network.domain.models import GeoPoint, NetworkNode, NodeType
from sag_network.simulation.engine import simulate_links


def surface_distance_m(a: NetworkNode, b: NetworkNode) -> float:
    """Approximate great-circle surface distance plus altitude separation."""
    radius_m = 6_371_000.0
    lat1, lon1 = math.radians(a.position.latitude_deg), math.radians(a.position.longitude_deg)
    lat2, lon2 = math.radians(b.position.latitude_deg), math.radians(b.position.longitude_deg)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    surface = 2 * radius_m * math.asin(math.sqrt(hav))
    vertical = abs(a.position.altitude_m - b.position.altitude_m)
    return math.hypot(surface, vertical)


user = NetworkNode(
    node_id="user-001",
    node_type=NodeType.USER,
    position=GeoPoint(latitude_deg=17.385, longitude_deg=78.486, altitude_m=500),
    available_capacity_bps=0,
    tx_power_dbm=23,
    tx_gain_dbi=0,
)

tower = NetworkNode(
    node_id="tower-001",
    node_type=NodeType.GROUND_STATION,
    position=GeoPoint(latitude_deg=17.405, longitude_deg=78.480, altitude_m=520),
    available_capacity_bps=100_000_000,
    tx_power_dbm=43,
    tx_gain_dbi=15,
)

for observation in simulate_links(
    timestamp_s=0,
    source=tower,
    targets=[user],
    distance_fn=surface_distance_m,
    frequency_hz=3.5e9,
    bandwidth_hz=20e6,
    noise_figure_db=5,
):
    print(observation.model_dump_json(indent=2))
