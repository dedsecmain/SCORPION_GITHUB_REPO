from __future__ import annotations


def run_selfcheck() -> int:
    from .cloud_gate import CloudGate
    from .config import Settings
    from .hud import SystemPanelModel
    from .voice_state import VoiceSession

    Settings.from_env()
    gate = CloudGate(lambda _reason: False)
    if gate.request_approval("selfcheck") is not None:
        raise RuntimeError("CloudGate self-check failed")
    if SystemPanelModel().cloud_label != "OPENAI LOCKED 🔒":
        raise RuntimeError("HUD cloud lock self-check failed")
    if VoiceSession().state.value != "STANDBY":
        raise RuntimeError("Voice state self-check failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_selfcheck())
