"""Optional, fail-closed MK90 scanner bridge across isolated Python venvs.

No web content or credentials are passed to an external API by this code.
Scans run only when explicitly enabled in Scorpion settings.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class SecurityUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class SecurityVerdict:
    allowed: bool
    reason: str


class MK90SecurityGate:
    def __init__(
        self,
        *,
        firewall_python: str | Path | None = None,
        guardrails_python: str | Path | None = None,
        timeout: float = 25.0,
        runner=None,
    ):
        base = Path.home() / "ScorpionMK90"
        self.firewall_python = Path(firewall_python or base / "firewall" / "Scripts" / "python.exe")
        self.guardrails_python = Path(guardrails_python or base / "guardrails" / "Scripts" / "python.exe")
        self.timeout = max(1, min(120.0, float(timeout)))
        self._runner = runner or subprocess.run

    def _scan(self, python: Path, engine: str, text: str) -> SecurityVerdict:
        if not python.is_file():
            raise SecurityUnavailable(f"{engine} ist noch nicht eingerichtet.")
        # Own source is loaded via PYTHONPATH, third-party dependency via venv.
        source_root = Path(__file__).resolve().parents[1]
        env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "USERPROFILE": os.environ.get("USERPROFILE", ""),
            "APPDATA": os.environ.get("APPDATA", ""),
            "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
            "HOMEDRIVE": os.environ.get("HOMEDRIVE", ""),
            "HOMEPATH": os.environ.get("HOMEPATH", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
            "PYTHONPATH": str(source_root),
            "PYTHONIOENCODING": "utf-8",
            "DO_NOT_TRACK": "1",
        }
        try:
            proc = self._runner(
                [str(python), "-m", "scorpion.mk90_scan_worker", engine],
                input=json.dumps({"text": text[:10000]}),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=self.timeout,
                env=env,
                check=False,
            )
            # Other libraries can emit diagnostics to stdout.
            marked = [line[len("MK90_RESULT:"):] for line in proc.stdout.splitlines()
                      if line.startswith("MK90_RESULT:")]
            if proc.returncode != 0 or not marked:
                raise SecurityUnavailable(f"{engine}-Prüfung fehlgeschlagen.")
            result = json.loads(marked[-1])
            if result.get("decision") not in {"allow", "block"}:
                raise SecurityUnavailable(f"{engine}: ungültige Entscheidung.")
            return SecurityVerdict(
                allowed=result["decision"] == "allow",
                reason=f"{engine}: {result.get('reason', 'Prüfung abgeschlossen')}",
            )
        except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            raise SecurityUnavailable(f"{engine}-Prüfung nicht verfügbar.") from exc

    def scan_untrusted(self, text: str) -> SecurityVerdict:
        """Require both independently installed scanners to allow the content."""
        for python, name in (
            (self.firewall_python, "llamafirewall"),
            (self.guardrails_python, "guardrails"),
        ):
            result = self._scan(python, name, text)
            if not result.allowed:
                return result
        return SecurityVerdict(True, "Beide MK90-Basisscanner haben den Text freigegeben.")
