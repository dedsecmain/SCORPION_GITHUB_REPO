from __future__ import annotations


class CameraService:
    def capture_jpeg(self, camera_index: int = 0) -> bytes:
        import cv2

        camera = cv2.VideoCapture(camera_index)
        try:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Kein Kamerabild erhalten.")
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if not ok:
                raise RuntimeError("Kamerabild konnte nicht codiert werden.")
            return encoded.tobytes()
        finally:
            camera.release()
