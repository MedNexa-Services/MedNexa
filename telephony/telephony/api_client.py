"""Thin async HTTP client for the MedNexa backend API (Part 1).

This is the *only* place where the telephony pipeline talks to the backend.
It wraps the call-session endpoints and exposes typed helpers so the rest of
the pipeline never constructs raw HTTP requests.

Endpoints used (from Part 1's /api/v1):
  POST /calls                  → start_call
  POST /calls/{id}/logs        → append_log
  POST /calls/{id}/end         → end_call
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import httpx

from telephony.config import get_settings
from telephony.logging_setup import get_logger

log = get_logger("api_client")


class BackendClient:
    """Async HTTP client for the MedNexa backend.

    Use as an async context manager or call ``aclose()`` when done.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self._base = (base_url or get_settings().backend_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "BackendClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"/api/v1{path}"
        resp = await self._client.post(url, json=body)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    # ── call session ─────────────────────────────────────────────────────────

    async def start_call(self, hospital_id: str, caller_phone: str) -> str:
        """Create a call session. Returns the session UUID string."""
        data = await self._post(
            "/calls",
            {"hospital_id": hospital_id, "caller_phone": caller_phone},
        )
        session_id: str = data["id"]
        log.info("call_started", session_id=session_id, caller_phone=caller_phone)
        return session_id

    async def append_log(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        tool_called: str | None = None,
        tool_result: str | None = None,
        appointment_id: str | None = None,
    ) -> None:
        """Append one conversation turn to the call log."""
        body: dict[str, Any] = {"role": role, "content": content}
        if tool_called:
            body["tool_called"] = tool_called
        if tool_result:
            body["tool_result"] = tool_result
        if appointment_id:
            body["appointment_id"] = appointment_id
        try:
            await self._post(f"/calls/{session_id}/logs", body)
        except Exception as exc:
            # Logging failures are non-fatal — the call must continue.
            log.warning("append_log_failed", session_id=session_id, error=str(exc))

    async def end_call(
        self,
        session_id: str,
        *,
        outcome: str = "completed",
        summary: str | None = None,
        language_detected: str | None = None,
        escalated_to_human: bool = False,
    ) -> None:
        """Mark the call session as ended with outcome metadata."""
        body: dict[str, Any] = {
            "call_outcome": outcome,
            "escalated_to_human": escalated_to_human,
        }
        if summary:
            body["summary"] = summary
        if language_detected:
            body["language_detected"] = language_detected
        try:
            await self._post(f"/calls/{session_id}/end", body)
            log.info("call_ended", session_id=session_id, outcome=outcome)
        except Exception as exc:
            log.warning("end_call_failed", session_id=session_id, error=str(exc))

    async def health_check(self) -> bool:
        """Return True if the backend is reachable and healthy."""
        try:
            resp = await self._client.get("/api/v1/health")
            return resp.status_code == 200
        except Exception:
            return False
