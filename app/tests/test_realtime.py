from scorpion.realtime import build_realtime_session


def test_realtime_session_uses_audio_and_server_vad():
    session = build_realtime_session("cedar", "Be Scorpion")
    assert session["type"] == "realtime"
    assert session["audio"]["input"]["turn_detection"]["type"] == "server_vad"
    assert session["audio"]["output"]["voice"] == "cedar"
