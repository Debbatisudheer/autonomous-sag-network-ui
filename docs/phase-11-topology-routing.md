# Phase 11 — End-to-End Topology and Routing

Phase 11 adds the network-layer path between the already-modeled radio access resources and a service endpoint.

The phase introduces:

- typed topology nodes for Ground, Air, Space, gateways, core, users, and services;
- directed links with explicit configured capacity, latency, loss rate, and active state;
- a deterministic routing engine;
- user access links derived directly from `UnifiedCandidate` measurements;
- end-to-end latency as the sum of link latency;
- end-to-end capacity as the minimum link capacity on the selected path;
- end-to-end loss using independent-link composition;
- rejection of inactive or unavailable paths.

This phase deliberately does not claim a complete 3GPP 5G Core, IP routing protocol stack, or inter-satellite routing implementation. Those are later concerns. The purpose here is to establish a clean, testable topology and routing abstraction without corrupting the physical Ground/Air/Space models.
