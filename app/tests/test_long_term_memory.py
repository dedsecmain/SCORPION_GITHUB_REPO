import json

import pytest

from scorpion.long_term_memory import LongTermMemoryStore


def test_memory_entry_round_trips(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    entry = store.add(
        category="projects",
        title="Scorpion MK22",
        content="Google Drive sync is approval-gated",
        importance=5,
        source="conversation",
        project="scorpion",
    )
    reloaded = LongTermMemoryStore(tmp_path / "memory.json")
    saved = reloaded.get(entry.id)
    assert saved is not None
    assert saved.project == "scorpion"
    assert saved.cloud_sync_state == "local_only"


def test_memory_filters_by_category_and_project(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    store.add(category="projects", title="A", content="one", importance=3, source="test", project="scorpion")
    store.add(category="preferences", title="B", content="two", importance=2, source="test", project=None)
    assert [item.title for item in store.list(category="projects")] == ["A"]
    assert [item.title for item in store.list(project="scorpion")] == ["A"]


def test_memory_update_changes_timestamp_and_delete_persists(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    entry = store.add(category="decisions", title="Voice", content="Swiss", importance=4, source="test")
    updated = store.update(entry.id, content="High German")
    assert updated.content == "High German"
    assert updated.updated_at >= entry.updated_at
    assert store.delete(entry.id) is True
    assert LongTermMemoryStore(tmp_path / "memory.json").get(entry.id) is None


def test_malformed_json_recovers_as_empty_store(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{not json", encoding="utf-8")
    store = LongTermMemoryStore(path)
    assert store.list() == []


@pytest.mark.parametrize("category", ["password", "token", "api_key", "cookie", "private_key"])
def test_secret_shaped_categories_are_rejected(tmp_path, category):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    with pytest.raises(ValueError):
        store.add(category=category, title="secret", content="x", importance=5, source="test")


def test_persistence_is_valid_json(tmp_path):
    path = tmp_path / "memory.json"
    store = LongTermMemoryStore(path)
    store.add(category="open_tasks", title="Ship", content="Release MK22", importance=5, source="test")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert payload[0]["title"] == "Ship"
