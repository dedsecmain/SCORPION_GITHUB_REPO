from __future__ import annotations


def run_selfcheck() -> int:
    from . import __version__
    from .autonomy import AutonomyKind, AutonomyPolicy
    from .build_mode import BuildGesture, BuildGestureEvent, BuildModeSession
    from .cloud_gate import CloudGate
    from .context_engine import analyze_context
    from .config import Settings
    from .hud import SystemPanelModel
    from .proactive_engine import ProactiveEngine
    from .updater import DEFAULT_PUBLIC_KEY_B64, _version_tuple
    from .voice_state import VoiceSession

    settings = Settings.from_env()
    if __version__ != "74.0.1":
        raise RuntimeError("MK74 version self-check failed")
    if _version_tuple("v74.0.1") != (74, 0, 1):
        raise RuntimeError("Updater version parser self-check failed")
    if len(DEFAULT_PUBLIC_KEY_B64.strip()) < 40:
        raise RuntimeError("Release public key self-check failed")
    gate = CloudGate(lambda _reason: False)
    if gate.request_approval("selfcheck") is not None:
        raise RuntimeError("CloudGate self-check failed")
    if SystemPanelModel().cloud_label != "OPENAI LOCKED 🔒":
        raise RuntimeError("HUD cloud lock self-check failed")
    if SystemPanelModel().intelligence_label != "GENERAL · AUTO":
        raise RuntimeError("MK74 HUD intelligence self-check failed")
    policy = AutonomyPolicy()
    if not policy.decide(AutonomyKind.LOCAL_COMPUTE).allowed:
        raise RuntimeError("MK74 local autonomy self-check failed")
    if policy.decide(AutonomyKind.CLOUD).allowed:
        raise RuntimeError("MK74 cloud permission self-check failed")
    context = analyze_context("Prüfe den Scorpion GitHub Update Fehler")
    suggestion = ProactiveEngine().suggest(
        context=context,
        memory_hits=0,
        local_failures=2,
        pending_improvements=1,
    )
    if suggestion is None or suggestion.auto_execute:
        raise RuntimeError("MK74 proactive engine self-check failed")
    if context.response_language != "de-DE" or context.priority != "quality":
        raise RuntimeError("MK74 context engine self-check failed")
    if VoiceSession().state.value != "STANDBY":
        raise RuntimeError("Voice state self-check failed")
    # User preferences are intentionally not release-health requirements.
    # A preserved .env may disable wake listening or autostart by choice.
    # The self-check validates that settings load successfully, not that
    # personal boolean preferences match fresh-install defaults.
    session = BuildModeSession()
    cube = session.add_object("cube", x=0.5, y=0.5)
    session.activate()
    session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=0.5, y=0.5))
    session.apply(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=0.7, y=0.3))
    if session.get(cube.id).x != 0.7 or session.get(cube.id).y != 0.3:
        raise RuntimeError("MK74 Build Mode self-check failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_selfcheck())
