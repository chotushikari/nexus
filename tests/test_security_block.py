from pathlib import Path

from nexus_api.schemas.domain import EventType
from nexus_api.services.security import scan_document_for_prompt_injection
from nexus_api.services.storage import DATA_DIR, store


def test_malicious_vendor_document_is_blocked():
    store.reset()
    result = scan_document_for_prompt_injection(
        "mission-test",
        "elena-rao",
        Path(DATA_DIR / "synthetic" / "malicious_vendor_document.txt"),
    )

    assert result["blocked"] is True
    event_types = [event.type for event in store.list_events("mission-test")]
    assert EventType.security_alert in event_types
    assert EventType.policy_blocked in event_types

