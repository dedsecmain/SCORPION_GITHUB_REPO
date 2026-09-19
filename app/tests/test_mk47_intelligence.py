from scorpion.context_engine import analyze_context
from scorpion.improvement_advisor import ImprovementAdvisor
from scorpion.long_term_memory import LongTermMemoryStore
from scorpion.persona import build_persona


def test_context_defaults_to_high_german_and_detects_technical_work():
    context = analyze_context("Prüfe bitte den GitHub Fehler im Scorpion Update")
    assert context.response_language == "de-DE"
    assert context.domain == "technical"
    assert context.project == "scorpion"
    assert context.priority == "quality"


def test_context_allows_explicit_language_override():
    context = analyze_context("Erklär mir das bitte auf Englisch")
    assert context.response_language == "en"


def test_context_marks_sensitive_topics_serious():
    context = analyze_context("Ich habe starke Schmerzen und brauche Hilfe")
    assert context.serious is True
    assert context.domain == "sensitive"


def test_relevant_memory_prefers_matching_project_and_terms(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    store.add(
        category="projects",
        title="Scorpion Update",
        content="MK50 behebt Ollama Stabilität und Wakeword Probleme",
        importance=5,
        source="test",
        project="scorpion",
    )
    store.add(
        category="preferences",
        title="Getränk",
        content="Nescau",
        importance=5,
        source="test",
    )
    matches = store.relevant("Was ist beim Scorpion Ollama Update geplant?", limit=2, project="scorpion")
    assert matches
    assert matches[0].project == "scorpion"
    assert "Ollama" in matches[0].content


def test_persona_uses_context_and_memory_without_leaving_german():
    context = analyze_context("Was war beim Scorpion Update geplant?")
    prompt = build_persona(
        "Was war beim Scorpion Update geplant?",
        context=context,
        memory_context="MK50: Ollama Stabilität verbessern.",
    )
    assert "Scorpion MK50" in prompt
    assert "Hochdeutsch" in prompt
    assert "de-DE" in prompt
    assert "MK50: Ollama Stabilität verbessern." in prompt


def test_improvement_advisor_only_proposes_and_never_auto_applies(tmp_path):
    advisor = ImprovementAdvisor(tmp_path / "improvements.json")
    proposal = advisor.propose(
        area="voice",
        title="Deutsch-Konsistenz verbessern",
        detail="Mehrere Antworten wechselten unerwartet auf Englisch.",
        evidence="language_mismatch_count=3",
    )
    assert proposal.status == "proposed"
    assert proposal.auto_apply is False
    assert advisor.pending()[0].title == "Deutsch-Konsistenz verbessern"
