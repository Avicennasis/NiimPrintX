import pytest
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


def test_packet_from_bytes_too_short():
    """Packets shorter than 7 bytes must raise ValueError."""
    with pytest.raises(ValueError, match="too short"):
        NiimbotPacket.from_bytes(b"\x55\x55\x40")


def test_packet_from_bytes_bad_header():
    """Packets with wrong header must raise ValueError."""
    with pytest.raises(ValueError, match="Invalid packet header"):
        NiimbotPacket.from_bytes(b"\xDE\xAD\x40\x01\x01\x40\xAA\xAA")


def test_packet_from_bytes_bad_checksum():
    """Packets with wrong checksum must raise ValueError."""
    pkt = NiimbotPacket(0x01, b"\x02\x03")
    raw = bytearray(pkt.to_bytes())
    raw[-3] ^= 0xFF
    with pytest.raises(ValueError, match="Checksum mismatch"):
        NiimbotPacket.from_bytes(bytes(raw))


def test_packet_from_bytes_length_exceeds_buffer():
    """Length field claiming more data than buffer holds must raise ValueError."""
    raw = b"\x55\x55\x40\x64\x01\x25\xAA\xAA"  # len=0x64=100, but only 1 data byte
    with pytest.raises(ValueError, match="exceeds"):
        NiimbotPacket.from_bytes(raw)


def test_packet_to_bytes_too_long():
    """Data longer than 255 bytes must raise ValueError."""
    with pytest.raises(ValueError, match="too long"):
        NiimbotPacket(0x01, bytes(256)).to_bytes()
