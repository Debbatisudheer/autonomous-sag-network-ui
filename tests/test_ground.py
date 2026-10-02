from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.domain.mobility import MobileUser
from sag_network.domain.models import GeoPoint
from sag_network.ground.association import evaluate_ground_network
from sag_network.ground.link import ground_user_link_state


def make_cell(
    cell_id: str,
    latitude_deg: float = 17.3850,
    longitude_deg: float = 78.4867,
    active: bool = True,
) -> GroundCell:
    return GroundCell(
        cell_id=cell_id,
        position=GeoPoint(latitude_deg=latitude_deg, longitude_deg=longitude_deg, altitude_m=540),
        carrier_frequency_hz=3.5e9,
        bandwidth_hz=20e6,
        tx_power_dbm=43,
        tx_gain_dbi=14,
        rx_gain_dbi=0,
        noise_figure_db=5,
        required_sinr_db=8,
        maximum_service_distance_m=6_000,
        propagation_losses=PropagationLosses(
            atmospheric_db=1,
            rain_db=2,
            polarization_db=1,
            implementation_db=2,
        ),
        active=active,
    )


def make_user(user_id: str = "u1", north_mps: float = 0, east_mps: float = 0) -> MobileUser:
    from sag_network.domain.mobility import MobilityProfile

    return MobileUser(
        user_id=user_id,
        initial_position=GeoPoint(latitude_deg=17.3850, longitude_deg=78.4867, altitude_m=540),
        mobility=MobilityProfile(north_velocity_mps=north_mps, east_velocity_mps=east_mps),
    )


def test_ground_link_is_available_at_cell_origin():
    candidate = ground_user_link_state(cell=make_cell("c1"), user=make_user(), timestamp_s=0)
    assert candidate.available
    assert candidate.distance_m > 0
    assert candidate.link_margin_db >= 0
    assert candidate.estimated_capacity_bps > 0


def test_ground_link_becomes_unavailable_beyond_service_radius():
    user = MobileUser(
        user_id="u1",
        initial_position=GeoPoint(latitude_deg=17.3850, longitude_deg=78.6000, altitude_m=540),
    )
    candidate = ground_user_link_state(cell=make_cell("c1"), user=user, timestamp_s=0)
    assert not candidate.available
    assert candidate.distance_m > 6_000


def test_inactive_cell_is_unavailable():
    candidate = ground_user_link_state(cell=make_cell("c1", active=False), user=make_user(), timestamp_s=0)
    assert not candidate.available


def test_ground_network_rejects_duplicate_cell_ids():
    try:
        GroundNetwork(name="n", cells=[make_cell("c1"), make_cell("c1")])
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("Expected duplicate cell IDs to fail validation")


def test_single_user_associates_to_available_cell():
    network = GroundNetwork(name="n", cells=[make_cell("c1"), make_cell("c2", 17.45, 78.55)])
    snapshot = evaluate_ground_network(
        network=network,
        users=[make_user()],
        demands_bps={"u1": 5e6},
        timestamp_s=0,
    )
    association = snapshot.associations[0]
    assert association.selected_cell_id == "c1"
    assert association.allocated_capacity_bps == 5e6


def test_two_users_share_selected_cell_capacity():
    network = GroundNetwork(name="n", cells=[make_cell("c1")])
    users = [make_user("u1"), make_user("u2")]
    snapshot = evaluate_ground_network(
        network=network,
        users=users,
        demands_bps={"u1": 20e6, "u2": 20e6},
        timestamp_s=0,
    )
    allocations = [association.allocated_capacity_bps for association in snapshot.associations]
    assert len(allocations) == 2
    assert all(allocation > 0 for allocation in allocations)
    assert allocations[0] == allocations[1]


def test_greedy_association_can_balance_load_between_cells():
    network = GroundNetwork(
        name="n",
        cells=[
            make_cell("c1"),
            make_cell("c2", latitude_deg=17.3950, longitude_deg=78.4867),
        ],
    )
    users = [
        make_user("u1"),
        MobileUser(
            user_id="u2",
            initial_position=GeoPoint(latitude_deg=17.3950, longitude_deg=78.4867, altitude_m=540),
        ),
    ]
    snapshot = evaluate_ground_network(
        network=network,
        users=users,
        demands_bps={"u1": 20e6, "u2": 20e6},
        timestamp_s=0,
    )
    selected = [association.selected_cell_id for association in snapshot.associations]
    assert selected == ["c1", "c2"]


def test_user_mobility_changes_terrestrial_distance():
    user = make_user(north_mps=10)
    at_zero = ground_user_link_state(cell=make_cell("c1"), user=user, timestamp_s=0)
    at_60 = ground_user_link_state(cell=make_cell("c1"), user=user, timestamp_s=60)
    assert at_60.distance_m > at_zero.distance_m
