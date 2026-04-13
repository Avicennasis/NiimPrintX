"""Shared test helpers (non-fixture) for NiimPrintX tests."""


def make_fake_write(client, response_pkt):
    """Return an async side_effect that sets notification_data from response_pkt."""

    async def fake_write(data, char_uuid):
        client.notification_data = response_pkt.to_bytes()
        client.notification_event.set()

    return fake_write
