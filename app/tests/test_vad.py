import struct

import pytest

from scorpion.vad import VADSegmenter


class FakeVad:
    def __init__(self, speech=True):
        self.speech = speech
        self.calls = []

    def is_speech(self, frame, sample_rate):
        self.calls.append((frame, sample_rate))
        return self.speech


def test_vad_accepts_valid_30ms_16khz_frame():
    fake = FakeVad(True)
    segmenter = VADSegmenter(vad_engine=fake)
    frame = b"\x01\x00" * 480
    assert segmenter.is_speech(frame) is True
    assert fake.calls[-1][1] == 16000


def test_vad_rejects_wrong_frame_size():
    segmenter = VADSegmenter(vad_engine=FakeVad())
    with pytest.raises(ValueError, match="frame"):
        segmenter.is_speech(b"\x00\x00" * 10)


def test_rms_level_is_normalized():
    segmenter = VADSegmenter(vad_engine=FakeVad(False))
    frame = b"".join(struct.pack("<h", 16384) for _ in range(480))
    level = segmenter.rms_level(frame)
    assert 0.49 < level < 0.51
