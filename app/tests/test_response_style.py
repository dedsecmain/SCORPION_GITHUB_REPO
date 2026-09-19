from scorpion.persona import build_persona
from scorpion.response_style import ResponseTone, classify_response_tone, style_guidance


def test_default_conversation_uses_signature_style():
    assert classify_response_tone("Bruder was geht heute?") is ResponseTone.SIGNATURE
    guidance = style_guidance(ResponseTone.SIGNATURE)
    assert "selbstbewusst" in guidance
    assert "locker" in guidance


def test_serious_topics_disable_banter():
    assert classify_response_tone("Ich habe starke Schmerzen und brauche Hilfe") is ResponseTone.SERIOUS
    guidance = style_guidance(ResponseTone.SERIOUS)
    assert "keine Witze" in guidance
    assert "ruhig" in guidance


def test_work_tasks_use_focused_style():
    assert classify_response_tone("Prüfe bitte den GitHub Update Fehler") is ResponseTone.FOCUSED
    guidance = style_guidance(ResponseTone.FOCUSED)
    assert "präzise" in guidance
    assert "wenig Smalltalk" in guidance


def test_persona_embeds_mk74_tone_for_current_message():
    prompt = build_persona("Bruder was geht heute?")
    assert "Scorpion MK74" in prompt
    assert "spielerisch" in prompt
    assert "Aktueller Reaktionsmodus: SIGNATURE" in prompt


def test_persona_switches_to_serious_without_losing_safety_rules():
    prompt = build_persona("Ich habe starke Schmerzen und brauche Hilfe")
    assert "Aktueller Reaktionsmodus: SERIOUS" in prompt
    assert "keine Witze" in prompt
    assert "OpenAI" in prompt
    assert "Truthfulness" in prompt
