from scorpion.autonomy import AutonomyPolicy, AutonomyKind
from scorpion.context_engine import analyze_context
from scorpion.proactive_engine import ProactiveEngine
from scorpion.persona import build_persona


def test_local_read_and_compute_are_allowed_without_confirmation():
    policy = AutonomyPolicy()
    for kind in (AutonomyKind.LOCAL_READ, AutonomyKind.LOCAL_COMPUTE):
        decision = policy.decide(kind)
        assert decision.allowed is True
        assert decision.requires_confirmation is False


def test_cloud_never_runs_without_fresh_approval():
    policy = AutonomyPolicy()
    decision = policy.decide(AutonomyKind.CLOUD)
    assert decision.allowed is False
    assert decision.requires_confirmation is True
    approved = policy.decide(AutonomyKind.CLOUD, approved=True)
    assert approved.allowed is True
    assert approved.requires_confirmation is False


def test_update_application_never_auto_applies():
    policy = AutonomyPolicy()
    blocked = policy.decide(AutonomyKind.APPLY_UPDATE)
    assert blocked.allowed is False
    assert blocked.requires_confirmation is True
    approved = policy.decide(AutonomyKind.APPLY_UPDATE, approved=True)
    assert approved.allowed is True


def test_proactive_engine_suggests_but_never_executes():
    engine = ProactiveEngine()
    context = analyze_context("Prüfe bitte den Scorpion GitHub Update Fehler")
    suggestion = engine.suggest(
        context=context,
        memory_hits=0,
        local_failures=2,
        pending_improvements=1,
    )
    assert suggestion is not None
    assert suggestion.auto_execute is False
    assert suggestion.requires_confirmation is True


def test_proactive_engine_stays_quiet_for_simple_casual_chat():
    engine = ProactiveEngine()
    context = analyze_context("Hallo Bruder")
    assert engine.suggest(
        context=context,
        memory_hits=1,
        local_failures=0,
        pending_improvements=0,
    ) is None


def test_mk74_persona_encodes_proactive_but_permissioned_behavior():
    context = analyze_context("Prüfe bitte das Scorpion Update")
    prompt = build_persona("Prüfe bitte das Scorpion Update", context=context)
    assert "Scorpion MK74" in prompt
    assert "proaktiv" in prompt.lower()
    assert "Freigabe" in prompt
    assert "Cloud" in prompt
