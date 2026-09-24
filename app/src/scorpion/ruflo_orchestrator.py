from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


class RufloCommandError(RuntimeError):
    """Raised when Ruflo is unavailable or a coordination command fails."""


@dataclass(frozen=True)
class RufloStatus:
    enabled: bool
    available: bool
    detail: str
    version: str = ""


@dataclass(frozen=True)
class RufloPlan:
    objective: str
    agents: tuple[str, ...]
    requires_approval_to_apply: bool
    detail: str


Runner = Callable[[Sequence[str], Path | None, float], tuple[int, str, str]]


def _default_runner(command: Sequence[str], cwd: Path | None, timeout: float) -> tuple[int, str, str]:
    completed = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def _split_command(value: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, str):
        parts = shlex.split(value, posix=os.name != "nt")
    else:
        parts = [str(item) for item in value]
    cleaned = tuple(item.strip() for item in parts if str(item).strip())
    if not cleaned:
        raise ValueError("Ruflo-Befehl darf nicht leer sein.")
    return cleaned


class RufloOrchestrator:
    """Small, permission-friendly bridge between Scorpion and Ruflo.

    Ruflo coordinates roles and task records. It does not receive authority to
    apply Scorpion updates or silently edit persistent user data.
    """

    AGENTS = (
        ("coder", "scorpion-coder"),
        ("tester", "scorpion-tester"),
        ("reviewer", "scorpion-update"),
    )

    def __init__(
        self,
        *,
        enabled: bool = True,
        command: str | Sequence[str] = "ruflo",
        cwd: Path | str | None = None,
        timeout: float = 30.0,
        max_agents: int = 4,
        runner: Runner | None = None,
    ):
        self.enabled = bool(enabled)
        self.command = _split_command(command)
        self.cwd = Path(cwd) if cwd is not None else None
        self.timeout = max(1.0, float(timeout))
        self.max_agents = max(4, min(16, int(max_agents)))
        self._runner = runner or _default_runner

    def _run(self, args: Sequence[str], *, allow_existing: bool = False) -> str:
        if not self.enabled:
            raise RufloCommandError("Ruflo ist in Scorpion deaktiviert.")
        full = (*self.command, *tuple(str(item) for item in args))
        try:
            code, stdout, stderr = self._runner(full, self.cwd, self.timeout)
        except FileNotFoundError as exc:
            raise RufloCommandError(
                f"Ruflo wurde lokal nicht gefunden ({self.command[0]})."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RufloCommandError("Ruflo hat das Zeitlimit überschritten.") from exc

        combined = "\n".join(part.strip() for part in (stdout, stderr) if part and part.strip())
        if code != 0:
            lowered = combined.casefold()
            if allow_existing and any(token in lowered for token in ("already exists", "duplicate", "exists")):
                return combined
            detail = combined or f"Exit-Code {code}"
            raise RufloCommandError(f"Ruflo-Befehl fehlgeschlagen: {detail}")
        return combined

    def status(self) -> RufloStatus:
        if not self.enabled:
            return RufloStatus(False, False, "Ruflo ist deaktiviert.")
        try:
            output = self._run(("--version",))
        except RufloCommandError as exc:
            return RufloStatus(True, False, str(exc))
        version = output.splitlines()[0].strip() if output.strip() else ""
        return RufloStatus(True, True, "Ruflo ist lokal erreichbar.", version=version)

    def prepare_task(self, objective: str) -> RufloPlan:
        objective = " ".join(str(objective).strip().split())
        if not objective:
            raise ValueError("Ruflo braucht ein konkretes Ziel.")

        self._run((
            "swarm",
            "init",
            "--topology",
            "hierarchical",
            "--max-agents",
            str(self.max_agents),
            "--strategy",
            "specialized",
        ))
        for agent_type, name in self.AGENTS:
            self._run(
                ("agent", "spawn", "-t", agent_type, "--name", name),
                allow_existing=True,
            )
        self._run((
            "task",
            "create",
            "--type",
            "implementation",
            "--description",
            objective,
        ))

        return RufloPlan(
            objective=objective,
            agents=tuple(name for _agent_type, name in self.AGENTS),
            requires_approval_to_apply=True,
            detail=(
                "Ruflo hat die Entwicklungsaufgabe koordiniert. "
                "Scorpion wendet Code oder Updates weiterhin nur nach ausdrücklicher Freigabe an."
            ),
        )
