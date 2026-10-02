from __future__ import annotations

from sag_network.domain.ground import GroundCell, GroundNetwork
from sag_network.domain.link import PropagationLosses
from sag_network.geospatial.models import GroundRadioProfile, GroundSiteDataset


def build_ground_network_from_sites(
    dataset: GroundSiteDataset,
    *,
    radio_profile: GroundRadioProfile,
    propagation_losses: PropagationLosses,
    network_name: str,
) -> GroundNetwork:
    """Convert validated geospatial sites into the existing GroundNetwork contract."""
    cells = [
        GroundCell(
            cell_id=site.site_id,
            position=site.position,
            carrier_frequency_hz=radio_profile.carrier_frequency_hz,
            bandwidth_hz=radio_profile.bandwidth_hz,
            tx_power_dbm=radio_profile.tx_power_dbm,
            tx_gain_dbi=radio_profile.tx_gain_dbi,
            rx_gain_dbi=radio_profile.rx_gain_dbi,
            noise_figure_db=radio_profile.noise_figure_db,
            required_sinr_db=radio_profile.required_sinr_db,
            maximum_service_distance_m=radio_profile.maximum_service_distance_m,
            propagation_losses=propagation_losses,
            scheduler_efficiency=radio_profile.scheduler_efficiency,
            active=True,
        )
        for site in sorted(dataset.sites, key=lambda item: item.site_id)
    ]
    return GroundNetwork(name=network_name, cells=cells)
