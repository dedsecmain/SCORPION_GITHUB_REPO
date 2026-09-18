import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def test_v301_manifest_signature_verifies_with_current_release_key():
    root = Path(__file__).resolve().parents[2] / "release"
    public_key = base64.b64decode(
        (root / "SCORPION_RELEASE_PUBLIC_KEY.txt").read_text(encoding="utf-8").strip(),
        validate=True,
    )
    manifest = (root / "v3.0.1" / "manifest.json").read_bytes()
    signature = base64.b64decode(
        (root / "v3.0.1" / "manifest.sig.b64").read_text(encoding="utf-8").strip(),
        validate=True,
    )
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, manifest)
