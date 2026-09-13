from scorpion.wake import extract_after_wake_phrase


def test_extracts_command_after_scorpion():
    assert extract_after_wake_phrase("Scorpion, öffne den Rechner") == "öffne den Rechner"


def test_accepts_hey_scorpion():
    assert extract_after_wake_phrase("Hey Scorpion öffne Browser") == "öffne Browser"


def test_returns_none_without_wake_phrase():
    assert extract_after_wake_phrase("öffne Browser") is None


def test_extracts_wake_phrase_when_it_appears_mid_transcript():
    from scorpion.wake import extract_after_wake_phrase_anywhere

    assert extract_after_wake_phrase_anywhere("ähm Scorpion, öffne Browser") == "öffne Browser"
