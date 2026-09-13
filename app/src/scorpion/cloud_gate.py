from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Callable
from uuid import uuid4


class CloudApprovalError(RuntimeError):
    """Raised when a cloud request does not carry a valid one-use approval."""


@dataclass(frozen=True)
class ApprovalToken:
    gate_id: str
    token_id: str
    reason: str


class CloudGate:
    """Issues and consumes single-use approvals for potentially billable cloud calls."""

    def __init__(self, approval_callback: Callable[[str], bool]):
        self._approval_callback = approval_callback
        self._gate_id = uuid4().hex
        self._valid_tokens: set[str] = set()

    def request_approval(self, reason: str) -> ApprovalToken | None:
        reason = reason.strip() or "OpenAI verwenden"
        if not self._approval_callback(reason):
            return None
        token_id = token_urlsafe(24)
        self._valid_tokens.add(token_id)
        return ApprovalToken(gate_id=self._gate_id, token_id=token_id, reason=reason)

    def consume(self, token: ApprovalToken) -> None:
        if token.gate_id != self._gate_id or token.token_id not in self._valid_tokens:
            raise CloudApprovalError("OpenAI-Aufruf ist nicht für diese Anfrage freigegeben.")
        self._valid_tokens.remove(token.token_id)
