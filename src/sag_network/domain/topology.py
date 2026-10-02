from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TopologyNodeType(str, Enum):
    USER = "user"
    GROUND_CELL = "ground_cell"
    UAV = "uav"
    HAPS = "haps"
    LEO_SATELLITE = "leo_satellite"
    GROUND_GATEWAY = "ground_gateway"
    AIR_GATEWAY = "air_gateway"
    SPACE_GATEWAY = "space_gateway"
    CORE = "core"
    SERVICE = "service"


class TopologyNode(BaseModel):
    """A routable node in the end-to-end network topology."""

    node_id: str = Field(min_length=1)
    node_type: TopologyNodeType
    domain: str = Field(min_length=1)
    active: bool = True


class TopologyLink(BaseModel):
    """A directed configured network link with explicit engineering properties."""

    link_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    capacity_bps: float = Field(gt=0)
    latency_ms: float = Field(ge=0)
    loss_rate: float = Field(ge=0, lt=1)
    active: bool = True


class NetworkTopology(BaseModel):
    """Directed end-to-end topology used by the routing layer."""

    name: str = Field(min_length=1)
    nodes: list[TopologyNode] = Field(min_length=2)
    links: list[TopologyLink] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_topology(self) -> NetworkTopology:
        node_ids = {node.node_id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("node_id values must be unique within a topology")
        link_ids = {link.link_id for link in self.links}
        if len(link_ids) != len(self.links):
            raise ValueError("link_id values must be unique within a topology")
        for link in self.links:
            if link.source_id not in node_ids or link.target_id not in node_ids:
                raise ValueError("every link endpoint must reference a topology node")
            if link.source_id == link.target_id:
                raise ValueError("self-loop links are not supported")
        return self
