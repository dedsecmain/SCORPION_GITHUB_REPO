"""No-audio Windows TTS adapter tests."""
import os
import subprocess
from types import SimpleNamespace

import pytest

from scorpion.windows_tts import WindowsSpeechError, speak_with_windows


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows subprocess platform")
def test_local_windows_tts_passes_text_only_on_stdin():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    speak_with_windows("Hallo, Herr Rodriguez.", runner=runner)
    args, kwargs = calls[0]
    assert args[0] == "powershell.exe"
    assert "-NoProfile" in args
    assert "-EncodedCommand" in args
    assert "Herr Rodriguez" not in repr(args)
    assert kwargs["input"] == "Hallo, Herr Rodriguez."
    assert kwargs["capture_output"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["timeout"] > 15


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows subprocess platform")
def test_failed_native_speech_returns_helpful_diagnostic():
    def runner(args, **kwargs):
        return SimpleNamespace(returncode=1, stderr="private text", stdout="")

    with pytest.raises(WindowsSpeechError, match="Standardlautsprecher"):
        speak_with_windows("secret example", runner=runner)


@pytest.mark.skipif(os.name != "nt", reason="Requires Windows subprocess platform")
def test_native_speech_timeout_is_bounded():
    def runner(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=20)

    with pytest.raises(WindowsSpeechError, match="reagiert nicht"):
        speak_with_windows("Hallo", runner=runner, timeout=20)
