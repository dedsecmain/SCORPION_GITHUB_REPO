import base64
import hashlib
import json
from pathlib import Path

import pytest

from scorpion.updater import UpdateVerificationError, Updater


class FakeTransport:
    def __init__(self):
        self.json_calls = []
        self.asset_downloads = []
        self.payloads = {}

    def get_json(self, url):
        self.json_calls.append(url)
        return {
            "tag_name": "v3.1.0",
            "body": "Voice fixes",
            "assets": [
                {"name": "manifest.json", "browser_download_url": "manifest"},
                {"name": "manifest.sig", "browser_download_url": "sig"},
                {"name": "SCORPION_update.zip", "browser_download_url": "zip"},
            ],
        }

    def get_bytes(self, url):
        self.asset_downloads.append(url)
        return self.payloads[url]


def test_check_does_not_download_payload(tmp_path):
    fake = FakeTransport()
    updater = Updater(repo="owner/repo", transport=fake, state_path=tmp_path / "state.json")
    info = updater.check(force=True)
    assert info.version == "v3.1.0"
    assert fake.asset_downloads == []


def test_empty_repo_disables_update_network(tmp_path):
    fake = FakeTransport()
    updater = Updater(repo="", transport=fake, state_path=tmp_path / "state.json")
    assert updater.check(force=True) is None
    assert fake.json_calls == []


def test_invalid_signature_is_blocked(tmp_path):
    updater = Updater(repo="owner/repo", state_path=tmp_path / "state.json")
    with pytest.raises(UpdateVerificationError):
        updater.verify_manifest(b"{}", b"invalid")


def test_stage_requires_confirmation_before_asset_download(tmp_path):
    fake = FakeTransport()
    updater = Updater(repo="owner/repo", transport=fake, state_path=tmp_path / "state.json")
    info = updater.check(force=True)
    with pytest.raises(PermissionError):
        updater.stage_update(info, confirmed=False, destination=tmp_path / "stage")
    assert fake.asset_downloads == []


def test_manifest_rejects_parent_traversal(tmp_path):
    updater = Updater(repo="owner/repo", state_path=tmp_path / "state.json")
    manifest = {"files": [{"path": "../evil.py", "sha256": "0" * 64}]}
    with pytest.raises(UpdateVerificationError):
        updater.validate_manifest(manifest)


def test_manifest_rejects_filename_prefix_trick(tmp_path):
    updater = Updater(repo="owner/repo", state_path=tmp_path / "state.json")
    manifest = {"files": [{"path": "requirements.txt.evil", "sha256": "0" * 64}]}
    with pytest.raises(UpdateVerificationError):
        updater.validate_manifest(manifest)


def test_valid_ed25519_signature_is_accepted(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    manifest = json.dumps({
        "files": [{"path": "README.md", "sha256": "0" * 64}],
        "min_updater": 1,
    }).encode("utf-8")
    signature = private.sign(manifest)
    updater = Updater(
        repo="owner/repo",
        state_path=tmp_path / "state.json",
        public_key_b64=base64.b64encode(public).decode("ascii"),
    )
    parsed = updater.verify_manifest(manifest, signature)
    assert parsed["files"][0]["path"] == "README.md"
