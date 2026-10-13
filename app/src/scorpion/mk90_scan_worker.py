"""Scanner worker started only in its matching Python 3.12 environment.

Protocol: one JSON object on stdin, one tagged JSON result on stdout.
Never print page content, passwords or prompt text to diagnostic output.
"""
from __future__ import annotations

import json
import os
import re
import sys

# Enforce local-only telemetry settings even when a worker is run directly.
# Configure this before importing Guardrails or LlamaFirewall.
os.environ.update({
    "DO_NOT_TRACK": "1",
    "OTEL_SDK_DISABLED": "true",
    "OTEL_TRACES_EXPORTER": "none",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_LOGS_EXPORTER": "none",
})


_SECRET_VALUE = re.compile(
    r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|private[_-]?key|"
    r"authorization|cookie)\s*[:=]\s*[^\s,;]{4,}"
)


def _check_firewall(text: str) -> tuple[str, str]:
    # REGEX does not trigger Hugging Face model downloads or cloud calls.
    from llamafirewall import LlamaFirewall, Role, ScannerType, UserMessage

    firewall = LlamaFirewall(scanners={Role.USER: [ScannerType.REGEX]})
    result = firewall.scan(UserMessage(content=text))
    decision = str(getattr(result.decision, "value", result.decision)).lower()
    if decision == "allow":
        return "allow", "Regex-Scanner ohne Treffer"
    return "block", "LlamaFirewall hat möglicherweise unsicheren Inhalt erkannt"


def _check_guardrails(text: str) -> tuple[str, str]:
    # A custom Guardrails validator, no Guardrails Hub or remote inference.
    from guardrails import Guard
    from guardrails.validator_base import (
        FailResult,
        PassResult,
        Validator,
        register_validator,
    )

    @register_validator(name="scorpion/mk90-no-credentials", data_type="string")
    class NoCredentials(Validator):
        def validate(self, value, metadata):
            if _SECRET_VALUE.search(str(value)):
                return FailResult(error_message="Mögliche Zugangsdaten im Inhalt")
            return PassResult()

    guard = Guard().use(NoCredentials(on_fail="exception"))
    try:
        guard.validate(text)
    except Exception:
        return "block", "Guardrails-Validierung blockiert mögliche Zugangsdaten"
    return "allow", "Keine Zugangsdaten-Zuweisung gefunden"


def main() -> int:
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"llamafirewall", "guardrails"}:
            raise ValueError("unknown engine")
        payload = json.load(sys.stdin)
        value = payload.get("text")
        if not isinstance(value, str) or len(value) > 10000:
            raise ValueError("invalid scan input")
        decision, reason = (
            _check_firewall(value) if sys.argv[1] == "llamafirewall"
            else _check_guardrails(value)
        )
        print("MK90_RESULT:" + json.dumps({"decision": decision, "reason": reason}))
        return 0
    except Exception:
        # Hide exception detail: it can contain user text or other secrets.
        print("MK90_RESULT:" + json.dumps({"decision": "error", "reason": "Scanner unavailable"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
