from PIL import Image


def test_encode_image_produces_packets(make_client, small_image):
    """Image encoding should produce one packet per row."""
    client = make_client()
    packets = list(client._encode_image(small_image))
    assert len(packets) == small_image.height


def test_encode_image_with_vertical_offset(make_client, small_image):
    """Vertical offset should produce additional packets."""
    client = make_client()
    packets_no_offset = list(client._encode_image(small_image, vertical_offset=0))
    packets_with_offset = list(client._encode_image(small_image, vertical_offset=10))
    assert len(packets_with_offset) == len(packets_no_offset) + 10


def test_encode_image_wide(make_client, wide_image):
    """Wide images (B-series) should also encode correctly."""
    client = make_client()
    packets = list(client._encode_image(wide_image))
    assert len(packets) == wide_image.height


def test_encode_image_packet_content_all_black(make_client):
    """All-black image should produce packets with all 1-bits."""
    client = make_client()
    img = Image.new("L", (16, 4), color=0)  # all black
    packets = list(client._encode_image(img))
    assert len(packets) == 4
    for pkt in packets:
        # Header is 6 bytes, then line data
        line_data = pkt.data[6:]
        assert line_data == b'\xff\xff'  # 16 bits all set


def test_encode_image_packet_content_all_white(make_client):
    """All-white image should produce packets with all 0-bits."""
    client = make_client()
    img = Image.new("L", (16, 4), color=255)  # all white
    packets = list(client._encode_image(img))
    assert len(packets) == 4
    for pkt in packets:
        line_data = pkt.data[6:]
        assert line_data == b'\x00\x00'  # 16 bits all clear


def test_encode_image_packet_content_checkerboard(make_client):
    """Alternating black/white pixels should produce correct bit pattern."""
    client = make_client()
    img = Image.new("L", (8, 1), color=255)  # start white
    # Set alternating pixels to black: 0,2,4,6 are black; 1,3,5,7 are white
    for x in range(0, 8, 2):
        img.putpixel((x, 0), 0)
    packets = list(client._encode_image(img))
    assert len(packets) == 1
    line_data = packets[0].data[6:]
    # Black pixels (0) → inverted → 255 → bit 1
    # White pixels (255) → inverted → 0 → bit 0
    # Pattern: 1,0,1,0,1,0,1,0 = 0xAA
    assert line_data == bytes([0xAA])


def test_encode_image_non_byte_aligned_width(make_client):
    """Image width not divisible by 8 should pad correctly."""
    client = make_client()
    img = Image.new("L", (10, 1), color=0)  # 10px wide, all black
    packets = list(client._encode_image(img))
    assert len(packets) == 1
    line_data = packets[0].data[6:]
    # 10 bits → 2 bytes, first 10 bits are 1 (black→inverted→1), last 6 bits padded
    assert len(line_data) == 2
    # 0xFF 0xC0 = 11111111 11000000
    assert line_data == bytes([0xFF, 0xC0])


def test_encode_image_negative_offset_crops(make_client):
    """Negative vertical offset should crop from top."""
    client = make_client()
    img = Image.new("1", (8, 10), color=0)
    packets_normal = list(client._encode_image(img))
    packets_cropped = list(client._encode_image(img, vertical_offset=-3))
    assert len(packets_cropped) == len(packets_normal) - 3
