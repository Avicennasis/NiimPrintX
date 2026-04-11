def packet_to_int(x):
    return int.from_bytes(x.data, "big")


class NiimbotPacket:
    def __init__(self, type_, data):
        self.type = type_
        self.data = data

    @classmethod
    def from_bytes(cls, pkt):
        if pkt is None or len(pkt) < 7:
            raise ValueError(f"Packet too short: {len(pkt) if pkt else 0} bytes")
        if pkt[:2] != b"\x55\x55":
            raise ValueError(f"Invalid packet header: {pkt[:2].hex()}")
        if pkt[-2:] != b"\xaa\xaa":
            raise ValueError(f"Invalid packet footer: {pkt[-2:].hex()}")
        type_ = pkt[2]
        len_ = pkt[3]
        if 4 + len_ + 3 > len(pkt):
            raise ValueError(f"Packet length field {len_} exceeds actual data: buffer is {len(pkt)} bytes")
        data = pkt[4 : 4 + len_]

        checksum = type_ ^ len_
        for i in data:
            checksum ^= i
        if checksum != pkt[-3]:
            raise ValueError(f"Checksum mismatch: expected {checksum:#x}, got {pkt[-3]:#x}")

        return cls(type_, data)

    def to_bytes(self):
        if len(self.data) > 255:
            raise ValueError(f"Packet data too long: {len(self.data)} bytes (max 255)")
        checksum = self.type ^ len(self.data)
        for i in self.data:
            checksum ^= i
        return bytes(
            (0x55, 0x55, self.type, len(self.data), *self.data, checksum, 0xAA, 0xAA)
        )

    def __repr__(self):
        return f"<NiimbotPacket type={self.type} data={self.data}>"
