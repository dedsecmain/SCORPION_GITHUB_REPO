from scorpion.hud import SystemPanelModel, VoiceVisualState


def test_waiting_state_shows_twenty_second_countdown():
    model = SystemPanelModel.from_voice_state("WAITING_COMMAND", remaining=20.0)
    assert model.voice_label == "WAITING 20s"
    assert model.countdown_visible is True
    assert model.core_state is VoiceVisualState.WAITING


def test_openai_locked_is_default():
    assert SystemPanelModel().cloud_label == "OPENAI LOCKED 🔒"


def test_speaking_and_thinking_have_distinct_core_states():
    assert SystemPanelModel.from_voice_state("THINKING").core_state is VoiceVisualState.THINKING
    assert SystemPanelModel.from_voice_state("SPEAKING").core_state is VoiceVisualState.SPEAKING


def test_system_model_carries_hardware_and_model_labels():
    model = SystemPanelModel(text_model="qwen3:8b", vision_model="gemma3:12b", hardware_label="24 GB RAM · 8 GB VRAM")
    assert "qwen3:8b" in model.text_model
    assert "gemma3:12b" in model.vision_model
