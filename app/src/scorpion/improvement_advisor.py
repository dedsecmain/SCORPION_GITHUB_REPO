from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ImprovementProposal:
    id: str
    area: str
    title: str
    detail: str
    evidence: str
    status: str
    auto_apply: bool
    created_at: str


class ImprovementAdvisor:
    """Local proposal store. It can suggest improvements, never apply them."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._items: list[ImprovementProposal] = []
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
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            try:
                item = ImprovementProposal(**raw)
            except TypeError:
                continue
            if item.auto_apply:
                continue
            self._items.append(item)

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(
            json.dumps([asdict(item) for item in self._items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def propose(self, *, area: str, title: str, detail: str, evidence: str = "") -> ImprovementProposal:
        area = str(area).strip().lower()
        title = str(title).strip()
        detail = str(detail).strip()
        evidence = str(evidence).strip()
        if not area or not title or not detail:
            raise ValueError("area, title and detail must not be empty")
        for item in self._items:
            if item.status == "proposed" and item.area == area and item.title.casefold() == title.casefold():
                return item
        proposal = ImprovementProposal(
            id=uuid.uuid4().hex,
            area=area,
            title=title,
            detail=detail,
            evidence=evidence,
            status="proposed",
            auto_apply=False,
            created_at=_now(),
        )
        self._items.append(proposal)
        self._persist()
        return proposal

    def pending(self) -> list[ImprovementProposal]:
        return [item for item in self._items if item.status == "proposed"]

    def diagnose(
        self,
        *,
        language_mismatch_count: int = 0,
        ollama_failures: int = 0,
    ) -> list[ImprovementProposal]:
        proposals: list[ImprovementProposal] = []
        if int(language_mismatch_count) >= 2:
            proposals.append(self.propose(
                area="language",
                title="Deutsch-Konsistenz prüfen",
                detail="Mehrere Antworten scheinen von der gewünschten Hochdeutsch-Ausgabe abzuweichen.",
                evidence=f"language_mismatch_count={int(language_mismatch_count)}",
            ))
        if int(ollama_failures) >= 2:
            proposals.append(self.propose(
                area="local-ai",
                title="Ollama-Stabilität prüfen",
                detail="Wiederholte lokale Modellfehler wurden erkannt. Scorpion schlägt eine Diagnose vor.",
                evidence=f"ollama_failures={int(ollama_failures)}",
            ))
        return proposals
