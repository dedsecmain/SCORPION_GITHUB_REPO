from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path


_ALLOWED_CATEGORIES = {"projects", "decisions", "preferences", "open_tasks", "important_facts"}
_SECRET_MARKERS = {"password", "token", "api_key", "apikey", "cookie", "private_key", "private-key", "secret"}
_MUTABLE_FIELDS = {"category", "title", "content", "importance", "source", "project", "cloud_sync_state", "remote_revision"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_category(category: str) -> str:
    value = str(category).strip().lower()
    if value in _SECRET_MARKERS or any(marker in value for marker in _SECRET_MARKERS):
        raise ValueError("Sensitive categories cannot be stored in long-term memory")
    if value not in _ALLOWED_CATEGORIES:
        raise ValueError(f"Unsupported memory category: {category}")
    return value


def _validate_importance(value: int) -> int:
    score = int(value)
    if not 1 <= score <= 5:
        raise ValueError("importance must be between 1 and 5")
    return score


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    category: str
    title: str
    content: str
    importance: int
    created_at: str
    updated_at: str
    source: str
    project: str | None = None
    cloud_sync_state: str = "local_only"
    remote_revision: str | None = None


class LongTermMemoryStore:
    """Atomic, local-authoritative structured memory storage."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, list):
            return
        expected = {field.name for field in fields(MemoryEntry)}
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            if not {"id", "category", "title", "content", "importance", "created_at", "updated_at", "source"}.issubset(raw):
                continue
            try:
                cleaned = {key: value for key, value in raw.items() if key in expected}
                cleaned["category"] = _validate_category(cleaned["category"])
                cleaned["importance"] = _validate_importance(cleaned["importance"])
                entry = MemoryEntry(**cleaned)
            except (TypeError, ValueError):
                continue
            self._entries[entry.id] = entry

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        data = [asdict(entry) for entry in self._entries.values()]
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(
        self,
        *,
        category: str,
        title: str,
        content: str,
        importance: int,
        source: str,
        project: str | None = None,
    ) -> MemoryEntry:
        category = _validate_category(category)
        importance = _validate_importance(importance)
        title = str(title).strip()
        content = str(content).strip()
        source = str(source).strip()
        if not title or not content or not source:
            raise ValueError("title, content and source must not be empty")
        timestamp = _now()
        entry = MemoryEntry(
            id=uuid.uuid4().hex,
            category=category,
            title=title,
            content=content,
            importance=importance,
            created_at=timestamp,
            updated_at=timestamp,
            source=source,
            project=str(project).strip() if project else None,
        )
        self._entries[entry.id] = entry
        self._persist()
        return entry

    def get(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(str(entry_id))

    def list(self, category: str | None = None, project: str | None = None) -> list[MemoryEntry]:
        category_filter = _validate_category(category) if category is not None else None
        project_filter = str(project) if project is not None else None
        items = list(self._entries.values())
        if category_filter is not None:
            items = [item for item in items if item.category == category_filter]
        if project_filter is not None:
            items = [item for item in items if item.project == project_filter]
        return sorted(items, key=lambda item: (item.updated_at, item.created_at, item.id))

    def update(self, entry_id: str, **changes) -> MemoryEntry:
        existing = self.get(entry_id)
        if existing is None:
            raise KeyError(entry_id)
        unknown = set(changes) - _MUTABLE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported memory fields: {', '.join(sorted(unknown))}")
        payload = asdict(existing)
        if "category" in changes:
            changes["category"] = _validate_category(changes["category"])
        if "importance" in changes:
            changes["importance"] = _validate_importance(changes["importance"])
        for key in ("title", "content", "source"):
            if key in changes and not str(changes[key]).strip():
                raise ValueError(f"{key} must not be empty")
        payload.update(changes)
        payload["updated_at"] = _now()
        updated = MemoryEntry(**payload)
        self._entries[entry_id] = updated
        self._persist()
        return updated

    def delete(self, entry_id: str) -> bool:
        if str(entry_id) not in self._entries:
            return False
        del self._entries[str(entry_id)]
        self._persist()
        return True
