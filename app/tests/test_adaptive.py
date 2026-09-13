import json

import pytest

from scorpion.adaptive import AdaptiveStore


def test_adaptive_store_rejects_disallowed_keys_and_bytes(tmp_path):
    store = AdaptiveStore(tmp_path / "adaptive.json")
    with pytest.raises(KeyError):
        store.set("arbitrary_code", "x")
    with pytest.raises(TypeError):
        store.set("voice", b"raw-audio")


def test_new_wake_alias_needs_three_distinct_sessions_and_confirmation(tmp_path):
    store = AdaptiveStore(tmp_path / "adaptive.json")
    alias = "skorpiun"
    for session in ("a", "b"):
        store.observe_wake_alias(alias, session_id=session, successful=True)
    assert store.alias_ready(alias) is False
    store.observe_wake_alias(alias, session_id="c", successful=True)
    assert store.alias_ready(alias) is True
    assert store.activate_alias(alias, confirmed=False) is False
    assert store.activate_alias(alias, confirmed=True) is True
    assert alias in store.get("accepted_wake_aliases")


def test_adaptive_store_persists_json_only(tmp_path):
    path = tmp_path / "adaptive.json"
    store = AdaptiveStore(path)
    store.set("voice_rate", "-5%")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["voice_rate"] == "-5%"
