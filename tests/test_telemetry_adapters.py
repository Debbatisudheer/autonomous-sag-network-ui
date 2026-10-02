from __future__ import annotations

import json
from datetime import datetime, UTC

import pytest

from sag_network.domain.unified import NetworkDomain
from sag_network.telemetry import (
    CCSDSParseError,
    CSVTelemetryAdapter,
    iter_space_packets,
    OPSSATSegmentsAdapter,
    parse_space_packet,
    SatNOGSDecodedTelemetryAdapter,
    TelemetryAdapterError,
    TelemetryMetric,
    TelemetrySchema,
    TelemetryStateStore,
    TelemetryTimeMapper,
)


def mapper() -> TelemetryTimeMapper:
    return TelemetryTimeMapper(
        epoch_utc=datetime(2026, 1, 1, tzinfo=UTC),
        simulation_epoch_s=10.0,
    )


def test_absolute_utc_maps_deterministically() -> None:
    value = mapper().to_simulation_time(datetime(2026, 1, 1, 12, tzinfo=UTC))
    assert value == 43210.0


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        mapper().to_simulation_time(datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None))


def test_epoch_timestamp_is_supported() -> None:
    parsed = mapper().parse_timestamp("1767225600")
    assert parsed == datetime(2026, 1, 1, tzinfo=UTC)


def test_csv_adapter_uses_explicit_schema() -> None:
    content = (
        "ts,node,reading,metric,domain,unit,seq\n"
        "2026-01-01T00:00:02Z,sat-1,-71.5,received_power_dbm,space,dBm,4\n"
    )
    adapter = CSVTelemetryAdapter(
        schema=TelemetrySchema(
            timestamp="ts",
            value="reading",
            source_id="node",
            metric="metric",
            domain="domain",
            unit="unit",
            sequence="seq",
        ),
        time_mapper=mapper(),
    )
    records = list(adapter.iter_records(__import__("io").StringIO(content)))
    assert len(records) == 1
    assert records[0].timestamp_s == 12.0
    assert records[0].sequence == 4
    assert records[0].metric is TelemetryMetric.RECEIVED_POWER_DBM
    assert records[0].metadata["provenance_schema"] == "csv"


def test_csv_missing_required_column_is_rejected() -> None:
    adapter = CSVTelemetryAdapter(
        schema=TelemetrySchema(timestamp="ts", value="value", source_id="source"),
        time_mapper=mapper(),
    )
    with pytest.raises(TelemetryAdapterError, match="missing required"):
        list(adapter.iter_records(__import__("io").StringIO("ts,value\n2026-01-01T00:00:00Z,1\n")))


def test_csv_row_error_is_rejected() -> None:
    adapter = CSVTelemetryAdapter(
        schema=TelemetrySchema(timestamp="ts", value="value", source_id="source"),
        time_mapper=mapper(),
    )
    with pytest.raises(TelemetryAdapterError, match="invalid telemetry row"):
        list(
            adapter.iter_records(
                __import__("io").StringIO(
                    "ts,value,source\n2026-01-01T00:00:00Z,nope,sat-1\n"
                )
            )
        )


def test_csv_default_metric_and_domain_are_preserved() -> None:
    adapter = CSVTelemetryAdapter(
        schema=TelemetrySchema(timestamp="ts", value="value", source_id="source"),
        time_mapper=mapper(),
        default_domain=NetworkDomain.AIR,
        default_metric=TelemetryMetric.SINR_DB,
        default_unit="dB",
    )
    records = list(
        adapter.iter_records(
            __import__("io").StringIO(
                "ts,value,source\n2026-01-01T00:00:01Z,12.5,uav-1\n"
            )
        )
    )
    assert records[0].domain is NetworkDomain.AIR
    assert records[0].metric is TelemetryMetric.SINR_DB
    assert records[0].unit == "dB"


def test_opssat_adapter_preserves_published_fields() -> None:
    content = (
        "timestamp,channel,value,label,segment,sampling,train,test\n"
        "2026-01-01T00:00:03Z,temp,23.2,temperature,seg-a,1Hz,true,false\n"
    )
    records = list(
        OPSSATSegmentsAdapter(time_mapper=mapper()).iter_records(__import__("io").StringIO(content))
    )
    assert records[0].source_id == "temp"
    assert records[0].domain is NetworkDomain.SPACE
    assert records[0].metadata["opssat_label"] == "temperature"
    assert records[0].metadata["opssat_segment"] == "seg-a"


def test_opssat_numeric_timestamp_is_supported() -> None:
    content = "timestamp,channel,value\n1767225601,temp,1\n"
    records = list(
        OPSSATSegmentsAdapter(time_mapper=mapper()).iter_records(__import__("io").StringIO(content))
    )
    assert records[0].timestamp_s == 11.0


def test_satnogs_list_payload_is_normalized() -> None:
    payload = [
        {
            "timestamp": "2026-01-01T00:00:04Z",
            "source_id": "satnogs-25544",
            "metric": "sinr_db",
            "value": 8.5,
            "unit": "dB",
            "sequence": 7,
            "doppler": "-1200",
        }
    ]
    records = SatNOGSDecodedTelemetryAdapter(time_mapper=mapper()).records_from_payload(payload)
    assert records[0].timestamp_s == 14.0
    assert records[0].sequence == 7
    assert records[0].metadata["satnogs_doppler"] == "-1200"


def test_satnogs_results_payload_is_supported() -> None:
    payload = {"results": [{"time": "2026-01-01T00:00:05Z", "label": "sinr_db", "value": 4.0}]}
    records = SatNOGSDecodedTelemetryAdapter(time_mapper=mapper()).records_from_payload(payload)
    assert records[0].source_id == "satnogs"
    assert records[0].metric is TelemetryMetric.SINR_DB


def test_satnogs_unsupported_metric_is_rejected() -> None:
    with pytest.raises(TelemetryAdapterError, match="unsupported metric"):
        SatNOGSDecodedTelemetryAdapter(time_mapper=mapper()).records_from_payload(
            [{"timestamp": "2026-01-01T00:00:01Z", "metric": "not_a_metric", "value": 1}]
        )


def test_satnogs_missing_observation_field_is_rejected() -> None:
    with pytest.raises(TelemetryAdapterError, match="requires"):
        SatNOGSDecodedTelemetryAdapter(time_mapper=mapper()).records_from_payload(
            [{"timestamp": "2026-01-01T00:00:01Z", "value": 1}]
        )


def _ccsds_packet(packet_type: int, apid: int, sequence: int, payload: bytes) -> bytes:
    first = (packet_type << 12) | apid
    second = (3 << 14) | sequence
    length = len(payload) - 1
    return (
        first.to_bytes(2, "big")
        + second.to_bytes(2, "big")
        + length.to_bytes(2, "big")
        + payload
    )


def test_ccsds_telemetry_header_and_payload() -> None:
    packet = parse_space_packet(_ccsds_packet(0, 0x321, 17, b"abc"))
    assert packet.header.apid == 0x321
    assert packet.header.sequence_count == 17
    assert packet.header.is_telemetry
    assert packet.data == b"abc"


def test_ccsds_telecommand_identification() -> None:
    packet = parse_space_packet(_ccsds_packet(1, 0x12, 2, b"x"))
    assert packet.header.is_telecommand
    assert not packet.header.is_telemetry


def test_ccsds_contiguous_stream_parsing() -> None:
    stream = _ccsds_packet(0, 1, 1, b"a") + _ccsds_packet(0, 2, 2, b"bc")
    packets = list(iter_space_packets(stream))
    assert [p.header.apid for p in packets] == [1, 2]


def test_ccsds_malformed_and_truncated_packets_fail() -> None:
    with pytest.raises(CCSDSParseError, match="at least"):
        parse_space_packet(b"\x00")
    packet = _ccsds_packet(0, 1, 1, b"abc")
    with pytest.raises(CCSDSParseError, match="truncated"):
        list(iter_space_packets(packet[:-1]))


def test_adapter_records_feed_existing_state_store() -> None:
    content = (
        "timestamp,source,value,metric,domain,unit,sequence\n"
        "2026-01-01T00:00:01Z,sat-1,10,sinr_db,space,dB,1\n"
    )
    adapter = CSVTelemetryAdapter(
        schema=TelemetrySchema(
            timestamp="timestamp",
            value="value",
            source_id="source",
            metric="metric",
            domain="domain",
            unit="unit",
            sequence="sequence",
        ),
        time_mapper=mapper(),
    )
    records = list(adapter.iter_records(__import__("io").StringIO(content)))
    store = TelemetryStateStore()
    result = store.ingest(records[0], reference_time_s=11.0)
    assert result.accepted_count == 1
    assert store.latest_for(source_id="sat-1", metric="sinr_db") == records[0]


def test_provenance_fingerprint_is_stable() -> None:
    from sag_network.telemetry import TelemetryProvenance
    a = TelemetryProvenance.from_bytes(b"abc", source_name="x", schema="csv")
    b = TelemetryProvenance.from_bytes(b"abc", source_name="x", schema="csv")
    assert a.content_sha256 == b.content_sha256
    assert len(a.content_sha256) == 64


def test_records_to_json_is_deterministic() -> None:
    from sag_network.telemetry import records_to_json
    adapter = CSVTelemetryAdapter(
        schema=TelemetrySchema(
            timestamp="timestamp", value="value", source_id="source",
            metric="metric", domain="domain", unit="unit",
        ),
        time_mapper=mapper(),
    )
    records = list(adapter.iter_records(__import__("io").StringIO(
        "timestamp,source,value,metric,domain,unit\n"
        "2026-01-01T00:00:01Z,sat-1,5,sinr_db,space,dB\n"
    )))
    first = records_to_json(records)
    second = records_to_json(records)
    assert json.loads(first) == json.loads(second)
