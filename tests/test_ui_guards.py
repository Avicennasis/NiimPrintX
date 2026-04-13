"""Tests for Round 9 UI guards — data/logic layer only, no tkinter required."""

import pytest

from NiimPrintX.nimmy.packet import NiimbotPacket

# ---------------------------------------------------------------------------
# 1. NiimbotPacket.to_int — empty data raises ValueError
# ---------------------------------------------------------------------------


def test_packet_to_int_empty_raises():
    """NiimbotPacket.to_int() must raise ValueError when packet data is empty."""
    pkt = NiimbotPacket(0x00, b"")
    with pytest.raises(ValueError, match="empty"):
        pkt.to_int()
