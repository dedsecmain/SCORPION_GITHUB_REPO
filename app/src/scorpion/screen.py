from __future__ import annotations

from io import BytesIO

from PIL import Image


def image_to_jpeg_bytes(image: Image.Image, quality: int = 88) -> bytes:
    rgb = image.convert("RGB")
    buffer = BytesIO()
    rgb.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


class ScreenService:
    def capture_jpeg(self) -> bytes:
        from PIL import ImageGrab

        image = ImageGrab.grab(all_screens=True)
        return image_to_jpeg_bytes(image)
