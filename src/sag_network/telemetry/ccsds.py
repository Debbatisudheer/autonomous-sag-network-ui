from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


class CCSDSParseError(ValueError):
    """Raised when a CCSDS space-packet stream is malformed."""


@dataclass(frozen=True)
class CCSDSPrimaryHeader:
    version: int
    packet_type: int
    secondary_header_flag: bool
    apid: int
    sequence_flags: int
    sequence_count: int
    packet_length_field: int
    total_packet_length: int

    @property
    def is_telecommand(self) -> bool:
        return self.packet_type == 1

    @property
    def is_telemetry(self) -> bool:
        return self.packet_type == 0


@dataclass(frozen=True)
class CCSDSpacePacket:
    header: CCSDSPrimaryHeader
    raw: bytes
    data: bytes


def parse_space_packet(packet: bytes) -> CCSDSpacePacket:
    if len(packet) < 6:
        raise CCSDSParseError("CCSDS packet must contain at least the 6-byte primary header")
    first = int.from_bytes(packet[0:2], "big")
    second = int.from_bytes(packet[2:4], "big")
    packet_length_field = int.from_bytes(packet[4:6], "big")
    version = (first >> 13) & 0x07
    packet_type = (first >> 12) & 0x01
    secondary_header_flag = bool((first >> 11) & 0x01)
    apid = first & 0x07FF
    sequence_flags = (second >> 14) & 0x03
    sequence_count = second & 0x3FFF
    total_length = packet_length_field + 7
    if version != 0:
        raise CCSDSParseError(f"unsupported CCSDS packet version: {version}")
    if total_length < 7:
        raise CCSDSParseError("invalid CCSDS packet length")
    if len(packet) != total_length:
        raise CCSDSParseError(
            f"packet length mismatch: header requires {total_length} bytes, received {len(packet)}"
        )
    return CCSDSpacePacket(
        header=CCSDSPrimaryHeader(
            version=version,
            packet_type=packet_type,
            secondary_header_flag=secondary_header_flag,
            apid=apid,
            sequence_flags=sequence_flags,
            sequence_count=sequence_count,
            packet_length_field=packet_length_field,
            total_packet_length=total_length,
        ),
        raw=bytes(packet),
        data=bytes(packet[6:]),
    )


def iter_space_packets(stream: bytes) -> Iterator[CCSDSpacePacket]:
    """Parse a contiguous CCSDS packet stream without silently dropping malformed data."""
    offset = 0
    while offset < len(stream):
        if len(stream) - offset < 6:
            raise CCSDSParseError("trailing bytes shorter than a CCSDS primary header")
        length_field = int.from_bytes(stream[offset + 4 : offset + 6], "big")
        total_length = length_field + 7
        if total_length < 7:
            raise CCSDSParseError("invalid CCSDS packet length in stream")
        end = offset + total_length
        if end > len(stream):
            raise CCSDSParseError(
                f"truncated CCSDS packet at offset {offset}: "
                f"requires {total_length} bytes, {len(stream) - offset} available"
            )
        yield parse_space_packet(stream[offset:end])
        offset = end
