from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .long_term_memory import LongTermMemoryStore, MemoryEntry


class DriveClientProtocol(Protocol):
    def upsert_json(
        self,
        name: str,
        payload: dict,
        revision: str | None = None,
    ) -> tuple[str, str]: ...


@dataclass(frozen=True)
class DriveSyncDecision:
    entry_id: str
    approved: bool


@dataclass(frozen=True)
class SyncProposal:
    entry_id: str
    reason: str


@dataclass(frozen=True)
class SyncResult:
    entry_id: str
    status: str
    remote_id: str | None = None
    remote_revision: str | None = None
    error: str | None = None


class DriveSyncService:
    """Approval-gated sync for structured long-term memory entries only."""

    _SAFE_FIELDS = (
        "id",
        "category",
        "title",
        "content",
        "importance",
        "created_at",
        "updated_at",
        "source",
        "project",
    )

    def __init__(
        self,
        client: DriveClientProtocol,
        *,
        store: LongTermMemoryStore | None = None,
    ):
        self.client = client
        self.store = store

    def request_sync(self, entry: MemoryEntry) -> SyncProposal:
        return SyncProposal(
            entry_id=entry.id,
            reason=f"Google Drive sync requested for memory: {entry.title}",
        )

    def sync(self, entry: MemoryEntry, *, approved: bool) -> SyncResult:
        if not approved:
            return SyncResult(entry_id=entry.id, status="not_approved")

        payload = {field: getattr(entry, field) for field in self._SAFE_FIELDS}
        name = f"memory-{entry.id}.json"

        try:
            remote_id, remote_revision = self.client.upsert_json(
                name,
                payload,
                revision=entry.remote_revision,
            )
        except Exception as exc:
            if self.store is not None and self.store.get(entry.id) is not None:
                self.store.update(entry.id, cloud_sync_state="failed")
            return SyncResult(
                entry_id=entry.id,
                status="failed",
                error=str(exc),
            )

        if self.store is not None and self.store.get(entry.id) is not None:
            self.store.update(
                entry.id,
                cloud_sync_state="synced",
                remote_revision=remote_revision,
            )

        return SyncResult(
            entry_id=entry.id,
            status="synced",
            remote_id=remote_id,
            remote_revision=remote_revision,
        )


def _drive_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDriveClient:
    """Lazy OAuth-backed Google Drive adapter for approved memory JSON only."""

    SCOPES = ("https://www.googleapis.com/auth/drive.file",)

    def __init__(
        self,
        *,
        folder_name: str = "ScorpionMemory",
        credentials_dir: str | Path | None = None,
        client_secret_file: str | Path | None = None,
    ):
        self.folder_name = str(folder_name).strip() or "ScorpionMemory"
        self.credentials_dir = (
            Path(credentials_dir)
            if credentials_dir is not None
            else Path.home() / ".scorpion" / "credentials"
        )
        self.client_secret_file = (
            Path(client_secret_file)
            if client_secret_file is not None
            else self.credentials_dir / "client_secret.json"
        )
        self.token_file = self.credentials_dir / "google-drive-token.json"
        self._service_cache = None

    def _service(self):
        if self._service_cache is not None:
            return self._service_cache

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Google Drive support is not installed. Install app requirements first."
            ) from exc

        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        credentials = None
        if self.token_file.exists():
            credentials = Credentials.from_authorized_user_file(
                str(self.token_file),
                self.SCOPES,
            )

        if credentials is not None and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        elif credentials is None or not credentials.valid:
            if not self.client_secret_file.exists():
                raise FileNotFoundError(
                    f"Google Drive OAuth client secret not found: {self.client_secret_file}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secret_file),
                self.SCOPES,
            )
            credentials = flow.run_local_server(port=0)

        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        self._service_cache = build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
        return self._service_cache

    def _folder_id(self) -> str:
        service = self._service()
        escaped = _drive_query_value(self.folder_name)
        response = (
            service.files()
            .list(
                q=(
                    f"name = '{escaped}' and "
                    "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                ),
                spaces="drive",
                fields="files(id,name)",
                pageSize=10,
            )
            .execute()
        )
        folders = response.get("files", [])
        if folders:
            return folders[0]["id"]

        created = (
            service.files()
            .create(
                body={
                    "name": self.folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                },
                fields="id",
            )
            .execute()
        )
        return created["id"]

    def upsert_json(
        self,
        name: str,
        payload: dict,
        revision: str | None = None,
    ) -> tuple[str, str]:
        _ = revision
        try:
            from googleapiclient.http import MediaInMemoryUpload
        except ImportError as exc:
            raise RuntimeError(
                "Google Drive support is not installed. Install app requirements first."
            ) from exc

        service = self._service()
        folder_id = self._folder_id()
        escaped_name = _drive_query_value(name)
        escaped_parent = _drive_query_value(folder_id)
        response = (
            service.files()
            .list(
                q=(
                    f"name = '{escaped_name}' and "
                    f"'{escaped_parent}' in parents and trashed = false"
                ),
                spaces="drive",
                fields="files(id,name,version,modifiedTime)",
                pageSize=10,
            )
            .execute()
        )
        media = MediaInMemoryUpload(
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            mimetype="application/json",
            resumable=False,
        )

        files = response.get("files", [])
        if files:
            result = (
                service.files()
                .update(
                    fileId=files[0]["id"],
                    body={"name": name},
                    media_body=media,
                    fields="id,version,modifiedTime",
                )
                .execute()
            )
        else:
            result = (
                service.files()
                .create(
                    body={"name": name, "parents": [folder_id]},
                    media_body=media,
                    fields="id,version,modifiedTime",
                )
                .execute()
            )

        revision_value = result.get("version") or result.get("modifiedTime") or result["id"]
        return result["id"], str(revision_value)
