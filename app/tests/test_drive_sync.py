from dataclasses import replace

from scorpion.drive_sync import DriveSyncService
from scorpion.long_term_memory import LongTermMemoryStore


class FakeDrive:
    def __init__(self, fail=False):
        self.fail = fail
        self.uploads = []

    def upsert_json(self, name, payload, revision=None):
        self.uploads.append((name, payload, revision))
        if self.fail:
            raise RuntimeError("drive offline")
        return "remote-1", "rev-2"


def make_entry(store):
    return store.add(
        category="projects",
        title="Scorpion MK22",
        content="Hybrid memory",
        importance=5,
        source="test",
        project="scorpion",
    )


def test_drive_sync_refuses_without_approval(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    entry = make_entry(store)
    drive = FakeDrive()
    service = DriveSyncService(drive, store=store)
    result = service.sync(entry, approved=False)
    assert result.status == "not_approved"
    assert drive.uploads == []
    assert store.get(entry.id).cloud_sync_state == "local_only"


def test_drive_sync_marks_approved_entry_synced(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    entry = make_entry(store)
    drive = FakeDrive()
    service = DriveSyncService(drive, store=store)
    result = service.sync(entry, approved=True)
    assert result.status == "synced"
    assert result.remote_revision == "rev-2"
    assert drive.uploads[0][0].startswith("memory-")
    saved = store.get(entry.id)
    assert saved.cloud_sync_state == "synced"
    assert saved.remote_revision == "rev-2"


def test_drive_failure_keeps_local_copy(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    entry = make_entry(store)
    service = DriveSyncService(FakeDrive(fail=True), store=store)
    result = service.sync(entry, approved=True)
    assert result.status == "failed"
    saved = store.get(entry.id)
    assert saved is not None
    assert saved.content == "Hybrid memory"
    assert saved.cloud_sync_state == "failed"


def test_sync_proposal_is_specific_to_one_entry(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    entry = make_entry(store)
    proposal = DriveSyncService(FakeDrive()).request_sync(entry)
    assert proposal.entry_id == entry.id
    assert "Scorpion MK22" in proposal.reason


def test_memory_payload_has_fixed_safe_fields_only(tmp_path):
    store = LongTermMemoryStore(tmp_path / "memory.json")
    entry = make_entry(store)
    drive = FakeDrive()
    DriveSyncService(drive).sync(entry, approved=True)
    payload = drive.uploads[0][1]
    forbidden = {"raw_screenshot", "audio", "token", "password", "cookie", "private_key"}
    assert forbidden.isdisjoint(payload)
