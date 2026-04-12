from __future__ import annotations


def packet_to_int(x: NiimbotPacket) -> int:
    if not x.data:
        raise ValueError("Cannot convert empty packet data to integer")
    return int.from_bytes(x.data, "big")


class NiimbotPacket:
    def __init__(self, type_: int, data: bytes) -> None:
        self.type = type_
        self.data = data

    @classmethod
    def from_bytes(cls, pkt: bytes | bytearray | memoryview) -> NiimbotPacket:
        if not isinstance(pkt, (bytes, bytearray, memoryview)):
            raise TypeError(f"from_bytes requires bytes-like object, got {type(pkt).__name__}")
        if len(pkt) < 7:
            raise ValueError(
                f"Packet too short: {len(pkt)} bytes (minimum 7: header=2 + type=1 + len=1 + checksum=1 + footer=2)"
            )
        if pkt[:2] != b"\x55\x55":
            raise ValueError(f"Invalid packet header: {pkt[:2].hex()}")
        type_ = pkt[2]
        len_ = pkt[3]
        expected_end = 4 + len_ + 3  # header(4) + data(len_) + checksum(1) + footer(2)
        if expected_end > len(pkt):
            raise ValueError(f"Packet length mismatch: expected {expected_end}, got {len(pkt)}")
        if pkt[expected_end - 2 : expected_end] != b"\xaa\xaa":
            raise ValueError(f"Invalid packet footer: {pkt[expected_end - 2 : expected_end].hex()}")
        data = bytes(pkt[4 : 4 + len_])

        checksum = type_ ^ len_
        for i in data:
            checksum ^= i
        if checksum != pkt[expected_end - 3]:
            raise ValueError(f"Checksum mismatch: expected {checksum:#x}, got {pkt[expected_end - 3]:#x}")

        return cls(type_, data)

    def to_bytes(self) -> bytes:
        if not 0 <= self.type <= 255:
            raise ValueError(f"Packet type must be 0-255, got {self.type}")
        if len(self.data) > 255:
            raise ValueError(f"Packet data too long: {len(self.data)} bytes (max 255)")
        checksum = self.type ^ len(self.data)
        for i in self.data:
            checksum ^= i
        return bytes((0x55, 0x55, self.type, len(self.data), *self.data, checksum, 0xAA, 0xAA))

    def __repr__(self) -> str:
        return f"<NiimbotPacket type={self.type} data={self.data!r}>"
