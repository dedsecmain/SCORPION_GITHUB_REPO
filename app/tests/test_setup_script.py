from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_setup_is_fail_fast_and_does_not_require_api_key():
    text = (ROOT / "setup_scorpion.bat").read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()

    assert "-m venv .venv || goto :error" in lower
    assert "pip install -r requirements.txt || goto :error" in lower
    assert "if not exist .env copy .env.example .env" in lower
    assert "c:\\scorpion" in lower
    assert ":error" in lower
    assert "goto :done" in lower
    assert "openai_api_key" in lower
    assert "optional" in lower or "optionaler" in lower or "optional" in text


def test_base_requirements_do_not_include_scipy_or_realtime_extra():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "scipy" not in requirements
    assert "openai[realtime]" not in requirements
    assert "faster-whisper" in requirements
    assert "pyttsx3" in requirements


def test_env_example_defaults_to_local_and_api_key_is_blank():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "SCORPION_MODE=LOCAL" in text
    assert "SCORPION_LOCAL_MODEL=" in text
    assert "SCORPION_WAKE_WAIT_SECONDS=20" in text
    assert "SCORPION_WHISPER_MODEL=base" in text
    assert "OPENAI_API_KEY=" in text


def test_requirements_include_natural_voice_with_offline_fallback():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").lower()
    assert "edge-tts" in requirements
    assert "pyttsx3" in requirements
