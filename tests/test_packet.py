from NiimPrintX.nimmy.packet import NiimbotPacket


def test_packet_roundtrip():
    """Packet should survive encode/decode roundtrip."""
    packet = NiimbotPacket(0x01, b"\x02\x03")
    raw = packet.to_bytes()
    parsed = NiimbotPacket.from_bytes(raw)
    assert parsed.type == 0x01
    assert parsed.data == b"\x02\x03"


def test_packet_header_footer():
    """Packets must start with 0x5555 and end with 0xAAAA."""
    packet = NiimbotPacket(0x40, b"\x01")
    raw = packet.to_bytes()
    assert raw[:2] == b"\x55\x55"
    assert raw[-2:] == b"\xaa\xaa"


def test_packet_empty_data():
    """Packet with empty data should still encode/decode."""
    packet = NiimbotPacket(0x10, b"")
    raw = packet.to_bytes()
    parsed = NiimbotPacket.from_bytes(raw)
    assert parsed.type == 0x10
    assert parsed.data == b""


def test_packet_large_data():
    """Packet with max-size data payload (255 bytes — length field is one byte)."""
    data = bytes(range(255))
    packet = NiimbotPacket(0x85, data)
    raw = packet.to_bytes()
    parsed = NiimbotPacket.from_bytes(raw)
    assert parsed.data == data
