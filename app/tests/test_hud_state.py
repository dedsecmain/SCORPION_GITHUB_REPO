from scorpion.hud import RED_HOLO_STATE_PALETTE, THEME, SystemPanelModel, VoiceVisualState


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


def test_system_model_carries_local_screen_context_status():
    model = SystemPanelModel(
        active_app_label="notepad.exe",
        screen_context_label="LOCAL CONTEXT ACTIVE",
    )
    assert model.active_app_label == "notepad.exe"
    assert model.screen_context_label == "LOCAL CONTEXT ACTIVE"



def test_red_holo_theme_is_red_first():
    assert THEME["bg"] == "#030304"
    assert THEME["accent"].startswith("#FF")
    assert THEME["cyan"] == "#FF1F2D"
    assert THEME["border_hot"] == "#B5121B"


def test_all_voice_states_have_red_holo_palette_entries():
    assert set(RED_HOLO_STATE_PALETTE) == set(VoiceVisualState)
    for outer, fill, accent in RED_HOLO_STATE_PALETTE.values():
        assert outer.startswith("#")
        assert fill.startswith("#")
        assert accent.startswith("#")
