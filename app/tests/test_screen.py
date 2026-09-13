from io import BytesIO

from PIL import Image

from scorpion.screen import image_to_jpeg_bytes


def test_image_to_jpeg_bytes_returns_jpeg():
    image = Image.new("RGB", (4, 3), "white")
    data = image_to_jpeg_bytes(image)
    assert data[:2] == b"\xff\xd8"
    decoded = Image.open(BytesIO(data))
    assert decoded.size == (4, 3)
