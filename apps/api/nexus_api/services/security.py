from pathlib import Path

from nexus_api.schemas.domain import EventType
from nexus_api.services.events import event_bus


PROMPT_INJECTION_PATTERNS = [
    "ignore all previous instructions",
    "system override",
    "delete all audit logs",
    "grant yourself",
    "send all financial records",
]


def scan_document_for_prompt_injection(
    mission_id: str,
    agent_id: str,
    document_path: Path,
) -> dict[str, object]:
    text = document_path.read_text(encoding="utf-8")
    matches = [pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern in text.lower()]
    if not matches:
        return {"blocked": False, "matches": []}

    event_bus.emit(
        EventType.security_alert,
        mission_id,
        "Prompt injection detected in vendor document",
        agent_id,
        metadata={"document": str(document_path), "matches": matches, "threat": "prompt_injection"},
    )
    event_bus.emit(
        EventType.policy_blocked,
        mission_id,
        "Vendor document quarantined by Nexus Security Layer",
        agent_id,
        metadata={"document": str(document_path), "reason": "prompt_injection_detected"},
    )
    return {"blocked": True, "matches": matches}

