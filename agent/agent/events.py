"""What happened during a call, recorded from tool results.

Used for the end-of-call summary, the call outcome reported to the backend, and
the guardrail that blocks claims ("your appointment is booked") that no tool
result backs up.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

ActionKind = Literal["info", "lookup", "book", "cancel", "reschedule", "escalate"]


@dataclass(frozen=True)
class CallEvent:
    tool: str
    kind: ActionKind
    ok: bool
    data: dict[str, Any]


@dataclass
class CallEvents:
    events: list[CallEvent] = field(default_factory=list)

    def add(self, event: CallEvent) -> None:
        self.events.append(event)

    def succeeded(self, kind: ActionKind) -> list[CallEvent]:
        return [e for e in self.events if e.kind == kind and e.ok]

    def confirmed_tokens(self) -> set[int]:
        """Token numbers the caller may legitimately be told about."""
        tokens = set()
        for e in self.events:
            if not e.ok:
                continue
            if e.kind in ("book", "reschedule") and "token_number" in e.data:
                tokens.add(int(e.data["token_number"]))
            for appt in e.data.get("appointments", []):
                tokens.add(int(appt["token_number"]))
        return tokens

    @property
    def escalated(self) -> bool:
        return bool(self.succeeded("escalate"))

    def outcome(self) -> str:
        """Backend CallOutcome value for this call."""
        if self.escalated:
            return "ESCALATED"
        outcomes: list[tuple[ActionKind, str]] = [
            ("book", "BOOKED"),
            ("reschedule", "RESCHEDULED"),
            ("cancel", "CANCELLED"),
        ]
        for kind, outcome in outcomes:
            if self.succeeded(kind):
                return outcome
        if self.succeeded("info") or self.succeeded("lookup"):
            return "INFO_PROVIDED"
        return "OTHER"

    def summary(self) -> str | None:
        parts = []
        for e in self.succeeded("book"):
            parts.append(
                f"Booked {e.data['patient_name']} with {e.data['doctor_name']} on "
                f"{e.data['date']} at {e.data['time']} (token {e.data['token_number']})."
            )
        for e in self.succeeded("reschedule"):
            parts.append(
                f"Rescheduled {e.data['patient_name']}'s appointment with "
                f"{e.data['doctor_name']} to {e.data['date']} at {e.data['time']} "
                f"(token {e.data['token_number']})."
            )
        for e in self.succeeded("cancel"):
            parts.append(
                f"Cancelled {e.data['patient_name']}'s appointment with "
                f"{e.data['doctor_name']} on {e.data['date']} at {e.data['time']}."
            )
        info_tools = sorted({e.tool for e in self.events if e.kind in ("info", "lookup")})
        if info_tools:
            parts.append(f"Answered questions using: {', '.join(info_tools)}.")
        failed = [e for e in self.events if not e.ok and e.kind in ("book", "cancel", "reschedule")]
        if failed:
            codes = ", ".join(sorted({str(e.data.get("error")) for e in failed}))
            parts.append(f"Unsuccessful attempts: {codes}.")
        for e in self.succeeded("escalate"):
            parts.append(f"Transferred to staff: {e.data.get('reason', 'no reason given')}.")
        return " ".join(parts) or None
