"""Runtime capability registry.

`/api/health` must never claim a Google capability that this process has not
actually exercised. Modules record what they observed here; the health endpoint
reads it. Three levels of truth are distinguished:

  * `installed`  – the SDK imports.
  * `configured` – credentials / switches make a call possible.
  * `exercised`  – a real call has succeeded in this process.
"""

from __future__ import annotations

from threading import RLock
from typing import Literal

from nexus_api.core.config import settings
from nexus_api.schemas.domain import CapabilityReport

CapabilityName = Literal["gemini", "adk", "firestore"]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._exercised: dict[str, bool] = {"gemini": False, "adk": False, "firestore": False}
        self._notes: dict[str, str] = {}

    def reset(self) -> None:
        with self._lock:
            self._exercised = {"gemini": False, "adk": False, "firestore": False}
            self._notes = {}

    def record_success(self, name: CapabilityName, note: str = "") -> None:
        with self._lock:
            self._exercised[name] = True
            self._notes[f"{name}_last"] = note or "call succeeded"

    def record_failure(self, name: CapabilityName, note: str) -> None:
        with self._lock:
            self._notes[f"{name}_last"] = note

    def note(self, key: str, value: str) -> None:
        with self._lock:
            self._notes[key] = value

    def exercised(self, name: CapabilityName) -> bool:
        return self._exercised.get(name, False)

    def report(self) -> CapabilityReport:
        from nexus_api.services import adk_runtime, planner

        gemini_installed, gemini_note = planner.gemini_sdk_status()
        adk_installed, adk_note = adk_runtime.adk_sdk_status()

        with self._lock:
            notes = dict(self._notes)
            exercised = dict(self._exercised)

        notes.setdefault("gemini_sdk", gemini_note)
        notes.setdefault("adk_sdk", adk_note)
        notes["gemini_configured"] = (
            "api_key_present"
            if settings.resolved_gemini_api_key
            else ("vertexai" if settings.google_genai_use_vertexai else "no_credentials")
        )
        notes["gemini_model"] = settings.gemini_model
        notes["planner_enabled"] = str(settings.enable_gemini_planner).lower()
        notes["adk_enabled"] = str(settings.enable_adk).lower()

        return CapabilityReport(
            # `true` only when a real call succeeded in this process.
            gemini=exercised["gemini"],
            adk=exercised["adk"],
            firestore=exercised["firestore"],
            details={
                **notes,
                "gemini_sdk_installed": str(gemini_installed).lower(),
                "adk_sdk_installed": str(adk_installed).lower(),
            },
        )


capabilities = CapabilityRegistry()
