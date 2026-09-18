from __future__ import annotations


def run_selfcheck() -> int:
    from . import __version__
    from .cloud_gate import CloudGate
    from .config import Settings
    from .hud import SystemPanelModel
    from .updater import DEFAULT_PUBLIC_KEY_B64, _version_tuple
    from .voice_state import VoiceSession

    Settings.from_env()
    if __version__ != "23.0.0":
        raise RuntimeError("MK23 version self-check failed")
    if _version_tuple("v23.0.0") != (23, 0, 0):
        raise RuntimeError("Updater version parser self-check failed")
    if len(DEFAULT_PUBLIC_KEY_B64.strip()) < 40:
        raise RuntimeError("Release public key self-check failed")
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
