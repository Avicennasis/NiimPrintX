"""Tests for Round 9 UI guards — data/logic layer only, no tkinter required."""

import pytest

from NiimPrintX.nimmy.packet import NiimbotPacket, packet_to_int

# ---------------------------------------------------------------------------
# 1. packet_to_int — empty data raises ValueError
# ---------------------------------------------------------------------------


def test_packet_to_int_empty_raises():
    """packet_to_int must raise ValueError when packet data is empty."""
    pkt = NiimbotPacket(0x00, b"")
    with pytest.raises(ValueError, match="empty"):
        packet_to_int(pkt)
