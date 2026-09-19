from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AutonomyKind(str, Enum):
    LOCAL_READ = "local_read"
    LOCAL_COMPUTE = "local_compute"
    CLOUD = "cloud"
    MUTATING = "mutating"
    APPLY_UPDATE = "apply_update"


@dataclass(frozen=True)
class AutonomyDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str


class AutonomyPolicy:
    """Central MK74 permission boundary.

    Local observation and computation may proceed locally. Cloud, persistent
    mutations and update application always require a fresh explicit approval.
    """

    _LOCAL = {AutonomyKind.LOCAL_READ, AutonomyKind.LOCAL_COMPUTE}
    _CONFIRM = {
        AutonomyKind.CLOUD,
        AutonomyKind.MUTATING,
        AutonomyKind.APPLY_UPDATE,
    }

    def decide(
        self,
        kind: AutonomyKind | str,
        *,
        approved: bool = False,
    ) -> AutonomyDecision:
        kind = AutonomyKind(kind)
        if kind in self._LOCAL:
            return AutonomyDecision(
                allowed=True,
                requires_confirmation=False,
                reason="Lokale, nicht-verändernde Aktion ist freigegeben.",
            )
        if kind in self._CONFIRM:
            if approved:
                return AutonomyDecision(
                    allowed=True,
                    requires_confirmation=False,
                    reason="Konkrete Freigabe für diese Aktion liegt vor.",
                )
            return AutonomyDecision(
                allowed=False,
                requires_confirmation=True,
                reason="Diese Aktion braucht eine frische ausdrückliche Freigabe.",
            )
        return AutonomyDecision(
            allowed=False,
            requires_confirmation=True,
            reason="Unbekannte Autonomieklasse wird sicherheitshalber blockiert.",
        )
