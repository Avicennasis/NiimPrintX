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
        NiimbotPacket.from_bytes(b"\xde\xad\x40\x01\x01\x40\xaa\xaa")


def test_packet_from_bytes_bad_checksum():
    """Packets with wrong checksum must raise ValueError."""
    pkt = NiimbotPacket(0x01, b"\x02\x03")
    raw = bytearray(pkt.to_bytes())
    raw[-3] ^= 0xFF
    with pytest.raises(ValueError, match="Checksum mismatch"):
        NiimbotPacket.from_bytes(bytes(raw))


def test_packet_from_bytes_length_exceeds_buffer():
    """Length field claiming more data than buffer holds must raise ValueError."""
    raw = b"\x55\x55\x40\x64\x01\x25\xaa\xaa"  # len=0x64=100, but only 1 data byte
    with pytest.raises(ValueError, match=r"mismatch|exceeds"):
        NiimbotPacket.from_bytes(raw)


def test_packet_to_bytes_too_long():
    """Data longer than 255 bytes must raise ValueError."""
    with pytest.raises(ValueError, match="too long"):
        NiimbotPacket(0x01, bytes(256)).to_bytes()


def test_packet_type_out_of_range():
    """Packet type outside 0-255 must raise ValueError."""
    with pytest.raises(ValueError, match="type"):
        NiimbotPacket(256, b"").to_bytes()


def test_packet_repr():
    """repr() should produce a useful string containing type and data."""
    pkt = NiimbotPacket(0x40, b"\x01\x02")
    r = repr(pkt)
    assert "NiimbotPacket" in r
    assert "64" in r or "0x40" in r or "40" in r  # type value present
    assert "data" in r.lower() or "\\x01\\x02" in r  # data shown


def test_packet_from_bytes_non_bytes_type():
    """Passing a non-bytes type to from_bytes must raise TypeError."""
    with pytest.raises(TypeError, match="bytes-like"):
        NiimbotPacket.from_bytes("not bytes")


def test_packet_from_bytes_bad_footer():
    """Valid header but wrong footer bytes must raise ValueError."""
    pkt = NiimbotPacket(0x01, b"\x02")
    raw = bytearray(pkt.to_bytes())
    raw[-2:] = b"\xbb\xbb"  # corrupt footer
    with pytest.raises(ValueError, match="footer"):
        NiimbotPacket.from_bytes(bytes(raw))


def test_packet_trailing_bytes_accepted():
    """Extra trailing bytes after a valid packet should not prevent parsing (BLE hardware compat)."""
    pkt = NiimbotPacket(0x40, b"\x01")
    raw = pkt.to_bytes() + b"\xff\xff\xff"
    parsed = NiimbotPacket.from_bytes(raw)
    assert parsed.type == 0x40
    assert parsed.data == b"\x01"


def test_packet_to_int_single_byte():
    """packet_to_int on single-byte data should return that byte value."""
    from NiimPrintX.nimmy.packet import packet_to_int

    pkt = NiimbotPacket(0x01, b"\x42")
    assert packet_to_int(pkt) == 0x42


def test_packet_to_int_multi_byte():
    """packet_to_int on multi-byte data should return big-endian integer (0x0100 = 256)."""
    from NiimPrintX.nimmy.packet import packet_to_int

    pkt = NiimbotPacket(0x01, b"\x01\x00")
    assert packet_to_int(pkt) == 256
