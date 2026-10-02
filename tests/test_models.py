import pytest
from pydantic import ValidationError

from sag_network.domain.models import GeoPoint, NetworkNode, NodeType


def test_node_validation():
    node = NetworkNode(
        node_id="tower-a",
        node_type=NodeType.GROUND_STATION,
        position=GeoPoint(latitude_deg=17.4, longitude_deg=78.5, altitude_m=500),
        available_capacity_bps=100_000_000,
        tx_power_dbm=30,
    )
    assert node.node_id == "tower-a"


def test_invalid_latitude_rejected():
    with pytest.raises(ValidationError):
        GeoPoint(latitude_deg=100, longitude_deg=78.5, altitude_m=500)
