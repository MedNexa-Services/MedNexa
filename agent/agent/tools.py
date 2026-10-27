"""Agent tools: thin wrappers around Part 1's service contract (task 2.4).

Each tool:
- takes LLM-provided arguments validated by a Pydantic model;
- gets `hospital_id` and the caller's phone from the call context, never from the LLM;
- opens its own DB session and calls `app.services.contracts`;
- returns a JSON-serialisable dict: {"ok": true, ...} or
  {"ok": false, "error": <code>, "message": <text for the caller>}.

Domain errors (slot taken, not owner, ...) become {"ok": false} results the LLM
can explain; they are never raised into the agent loop.
"""

import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from app.core.exceptions import DomainError
from app.core.timeutils import hospital_now
from app.models import BookingSource, Hospital
from app.schemas.appointment import AppointmentOut, BookingRequest
from app.schemas.patient import PatientIn
from app.services import contracts
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.events import ActionKind, CallEvent, CallEvents

logger = logging.getLogger(__name__)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class ToolContext:
    """Per-call state shared by all tools."""

    hospital_id: uuid.UUID
    caller_phone: str | None  # normalized; None when caller ID is unavailable
    session_factory: async_sessionmaker[AsyncSession]
    now: Callable[[], datetime] | None = None  # override for tests
    events: CallEvents = field(default_factory=CallEvents)
    escalation_reason: str | None = None

    async def current_time(self, db: AsyncSession) -> datetime:
        if self.now is not None:
            return self.now()
        tz = await db.scalar(select(Hospital.timezone).where(Hospital.id == self.hospital_id))
        return hospital_now(tz or "Asia/Kolkata")


class ToolInputError(ValueError):
    """An argument the LLM supplied could not be understood."""


# --- argument parsing helpers -------------------------------------------------------

_TIME_12H = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?\s*$", re.I)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ToolInputError(f"Date must be YYYY-MM-DD, got {value!r}") from exc


def parse_time(value: str) -> time:
    """Accepts 24-hour 'HH:MM' (or 'H:MM') and 12-hour '10:30 AM' / '4 pm'."""
    value = value.strip()
    match = _TIME_12H.match(value)
    if match:
        hour, minute, half = int(match[1]), int(match[2] or 0), match[3].lower()
        if not 1 <= hour <= 12 or minute > 59:
            raise ToolInputError(f"Invalid time {value!r}")
        hour = hour % 12 + (12 if half == "p" else 0)
        return time(hour, minute)
    try:
        hour_text, minute_text = value.split(":")[:2]
        return time(int(hour_text), int(minute_text))
    except ValueError as exc:
        raise ToolInputError(f"Time must be HH:MM, got {value!r}") from exc


def parse_id(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value.strip())
    except ValueError as exc:
        raise ToolInputError(f"Unknown {what} id {value!r}; look it up with a tool first") from exc


def fmt_time(t: time) -> str:
    return t.strftime("%H:%M")


def _appointment(a: AppointmentOut) -> dict[str, Any]:
    return {
        "appointment_id": str(a.id),
        "patient_name": a.patient_name,
        "doctor_name": a.doctor_name,
        "department": a.department,
        "date": a.appointment_date.isoformat(),
        "weekday": WEEKDAYS[a.appointment_date.weekday()],
        "time": fmt_time(a.appointment_time),
        "token_number": a.token_number,
        "status": a.status.value,
    }


def _require_caller(ctx: ToolContext) -> str:
    if not ctx.caller_phone:
        raise DomainError("The caller's phone number is unavailable on this call")
    return ctx.caller_phone


# --- tool argument models -----------------------------------------------------------


class NoArgs(BaseModel):
    pass


class HospitalInfoArgs(BaseModel):
    query: str = Field(description="The caller's question, e.g. 'parking' or 'OPD timings'")


class ListDoctorsArgs(BaseModel):
    speciality: str | None = Field(default=None, description="e.g. 'cardio', 'ortho'")
    department: str | None = Field(default=None, description="e.g. 'General Medicine'")


class DoctorArgs(BaseModel):
    doctor_id: str = Field(description="doctor_id from list_doctors")


class SlotsArgs(BaseModel):
    doctor_id: str = Field(description="doctor_id from list_doctors")
    date: str = Field(description="YYYY-MM-DD")


class NextAvailableArgs(BaseModel):
    speciality: str = Field(description="Speciality or department, e.g. 'cardiology'")
    preferred_date: str | None = Field(default=None, description="YYYY-MM-DD, earliest date")
    limit: int = Field(default=3, ge=1, le=10)


class BookArgs(BaseModel):
    patient_name: str = Field(description="Full name of the patient (may differ from caller)")
    doctor_id: str = Field(description="doctor_id from list_doctors or find_next_available")
    date: str = Field(description="YYYY-MM-DD")
    time: str = Field(description="Slot start time, HH:MM (24-hour)")
    patient_age: int | None = Field(default=None, ge=0, le=150)
    patient_gender: str | None = Field(default=None, description="MALE, FEMALE or OTHER")
    notes: str | None = Field(default=None, description="Reason for visit, if offered")


class MyAppointmentsArgs(BaseModel):
    patient_name: str = Field(description="Patient's full name as given by the caller")


class CancelArgs(BaseModel):
    appointment_id: str = Field(description="appointment_id from get_my_appointments")
    reason: str | None = None


class RescheduleArgs(BaseModel):
    appointment_id: str = Field(description="appointment_id from get_my_appointments")
    new_date: str = Field(description="YYYY-MM-DD")
    new_time: str = Field(description="HH:MM (24-hour)")


class TransferArgs(BaseModel):
    reason: str = Field(description="Why the caller needs a human")


# --- tool implementations -----------------------------------------------------------


async def get_hospital_info(
    ctx: ToolContext, db: AsyncSession, a: HospitalInfoArgs
) -> dict[str, Any]:
    entries = await contracts.get_hospital_info(db, ctx.hospital_id, a.query)
    return {
        "ok": True,
        "results": [{"category": e.category, "question": e.question, "answer": e.answer}
                    for e in entries],
    }  # fmt: skip


async def list_doctors(ctx: ToolContext, db: AsyncSession, a: ListDoctorsArgs) -> dict[str, Any]:
    doctors = await contracts.list_doctors(db, ctx.hospital_id, a.speciality, a.department)
    return {
        "ok": True,
        "doctors": [
            {
                "doctor_id": str(d.id),
                "name": d.name,
                "speciality": d.speciality,
                "department": d.department,
                "qualification": d.qualification,
                "days": [WEEKDAYS[i - 1] for i in d.available_days],
                "hours": f"{fmt_time(d.slot_start_time)}-{fmt_time(d.slot_end_time)}",
            }
            for d in doctors
        ],
    }


async def get_doctor_details(ctx: ToolContext, db: AsyncSession, a: DoctorArgs) -> dict[str, Any]:
    d = await contracts.get_doctor(db, parse_id(a.doctor_id, "doctor"))
    if d.hospital_id != ctx.hospital_id:
        raise DomainError("Doctor not found")
    return {
        "ok": True,
        "doctor": {
            "doctor_id": str(d.id),
            "name": d.name,
            "speciality": d.speciality,
            "department": d.department,
            "qualification": d.qualification,
            "bio": d.bio,
            "days": [WEEKDAYS[i - 1] for i in d.available_days],
            "hours": f"{fmt_time(d.slot_start_time)}-{fmt_time(d.slot_end_time)}",
            "slot_minutes": d.slot_duration_minutes,
            "schedule_changes": [
                {
                    "date": o.date.isoformat(),
                    "available": o.is_available,
                    "hours": (
                        f"{fmt_time(o.start_time or d.slot_start_time)}-"
                        f"{fmt_time(o.end_time or d.slot_end_time)}"
                    ) if o.is_available else None,
                    "reason": o.override_reason,
                }
                for o in d.upcoming_overrides
            ],
        },
    }  # fmt: skip


async def check_available_slots(ctx: ToolContext, db: AsyncSession, a: SlotsArgs) -> dict[str, Any]:
    on = parse_date(a.date)
    now = await ctx.current_time(db)
    slots = await contracts.get_available_slots(db, parse_id(a.doctor_id, "doctor"), on, now=now)
    return {
        "ok": True,
        "date": on.isoformat(),
        "weekday": WEEKDAYS[on.weekday()],
        "free_slots": [fmt_time(s.start) for s in slots],
    }


async def find_next_available(
    ctx: ToolContext, db: AsyncSession, a: NextAvailableArgs
) -> dict[str, Any]:
    start = parse_date(a.preferred_date) if a.preferred_date else None
    now = await ctx.current_time(db)
    slots = await contracts.find_next_available(
        db, ctx.hospital_id, a.speciality, start, a.limit, now=now
    )
    return {
        "ok": True,
        "slots": [
            {
                "doctor_id": str(s.doctor_id),
                "doctor_name": s.doctor_name,
                "speciality": s.speciality,
                "date": s.date.isoformat(),
                "weekday": WEEKDAYS[s.date.weekday()],
                "time": fmt_time(s.start),
            }
            for s in slots
        ],
    }


async def book_appointment(ctx: ToolContext, db: AsyncSession, a: BookArgs) -> dict[str, Any]:
    phone = _require_caller(ctx)
    gender = a.patient_gender.strip().upper() if a.patient_gender else None
    try:
        patient = PatientIn(name=a.patient_name, phone=phone, age=a.patient_age, gender=gender)
    except ValidationError as exc:
        raise ToolInputError("Invalid patient details (name, age or gender)") from exc
    request = BookingRequest(
        patient=patient,
        doctor_id=parse_id(a.doctor_id, "doctor"),
        appointment_date=parse_date(a.date),
        appointment_time=parse_time(a.time),
        notes=a.notes,
        booking_source=BookingSource.AI_CALL,
    )
    c = await contracts.book_appointment(db, request, now=await ctx.current_time(db))
    return {
        "ok": True,
        "appointment_id": str(c.appointment_id),
        "token_number": c.token_number,
        "patient_name": c.patient_name,
        "doctor_name": c.doctor_name,
        "department": c.department,
        "date": c.appointment_date.isoformat(),
        "weekday": WEEKDAYS[c.appointment_date.weekday()],
        "time": fmt_time(c.appointment_time),
    }


async def get_my_appointments(
    ctx: ToolContext, db: AsyncSession, a: MyAppointmentsArgs
) -> dict[str, Any]:
    phone = _require_caller(ctx)
    appts = await contracts.get_patient_appointments(
        db, ctx.hospital_id, phone, a.patient_name, now=await ctx.current_time(db)
    )
    return {"ok": True, "appointments": [_appointment(x) for x in appts]}


async def cancel_appointment(ctx: ToolContext, db: AsyncSession, a: CancelArgs) -> dict[str, Any]:
    phone = _require_caller(ctx)
    appt = await contracts.cancel_appointment(
        db,
        parse_id(a.appointment_id, "appointment"),
        phone,
        a.reason,
        now=await ctx.current_time(db),
    )
    return {"ok": True, **_appointment(appt)}


async def reschedule_appointment(
    ctx: ToolContext, db: AsyncSession, a: RescheduleArgs
) -> dict[str, Any]:
    phone = _require_caller(ctx)
    c = await contracts.reschedule_appointment(
        db,
        parse_id(a.appointment_id, "appointment"),
        phone,
        parse_date(a.new_date),
        parse_time(a.new_time),
        now=await ctx.current_time(db),
    )
    return {
        "ok": True,
        "appointment_id": str(c.appointment_id),
        "token_number": c.token_number,
        "patient_name": c.patient_name,
        "doctor_name": c.doctor_name,
        "date": c.appointment_date.isoformat(),
        "weekday": WEEKDAYS[c.appointment_date.weekday()],
        "time": fmt_time(c.appointment_time),
    }


async def get_current_datetime(ctx: ToolContext, db: AsyncSession, _: NoArgs) -> dict[str, Any]:
    now = await ctx.current_time(db)
    return {
        "ok": True,
        "date": now.date().isoformat(),
        "weekday": WEEKDAYS[now.weekday()],
        "time": fmt_time(now.time()),
    }


async def transfer_to_human(ctx: ToolContext, db: AsyncSession, a: TransferArgs) -> dict[str, Any]:
    ctx.escalation_reason = a.reason
    return {
        "ok": True,
        "message": "Staff will be connected. Tell the caller to stay on the line.",
        "reason": a.reason,
    }


# --- registry -----------------------------------------------------------------------

ToolFn = Callable[[ToolContext, AsyncSession, Any], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args: type[BaseModel]
    fn: ToolFn
    kind: ActionKind

    def schema(self) -> dict[str, Any]:
        """OpenAI-style function schema (accepted by Ollama, Groq and OpenAI)."""
        params = self.args.model_json_schema()
        params.pop("title", None)
        for prop in params.get("properties", {}).values():
            prop.pop("title", None)
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": params},
        }


TOOLS: list[ToolSpec] = [
    ToolSpec("get_hospital_info", "Answer general questions about the hospital (address, "
             "timings, parking, departments, insurance, pharmacy, reports...).",
             HospitalInfoArgs, get_hospital_info, "info"),
    ToolSpec("list_doctors", "List active doctors, optionally filtered by speciality or "
             "department. Returns doctor_id values needed by other tools.",
             ListDoctorsArgs, list_doctors, "info"),
    ToolSpec("get_doctor_details", "Details of one doctor, including upcoming leave or changed "
             "hours.", DoctorArgs, get_doctor_details, "info"),
    ToolSpec("check_available_slots", "Free appointment slots for a doctor on a date.",
             SlotsArgs, check_available_slots, "info"),
    ToolSpec("find_next_available", "Earliest free slots across all doctors of a speciality "
             "(searches 14 days).", NextAvailableArgs, find_next_available, "info"),
    ToolSpec("book_appointment", "Book a slot after the caller has confirmed the doctor, date "
             "and time. Uses the calling phone number.", BookArgs, book_appointment, "book"),
    ToolSpec("get_my_appointments", "Upcoming appointments of a patient registered to the "
             "calling phone number.", MyAppointmentsArgs, get_my_appointments, "lookup"),
    ToolSpec("cancel_appointment", "Cancel an appointment after the caller confirms. Only works "
             "for appointments of the calling number.", CancelArgs, cancel_appointment, "cancel"),
    ToolSpec("reschedule_appointment", "Move an appointment to another free slot with the same "
             "doctor after the caller confirms.", RescheduleArgs, reschedule_appointment,
             "reschedule"),
    ToolSpec("get_current_datetime", "Current date, weekday and time at the hospital.",
             NoArgs, get_current_datetime, "info"),
    ToolSpec("transfer_to_human", "Hand the call to hospital staff (caller asks for a person, "
             "emergency, or you cannot help).", TransferArgs, transfer_to_human, "escalate"),
]  # fmt: skip

TOOLS_BY_NAME = {t.name: t for t in TOOLS}


async def execute_tool(ctx: ToolContext, name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    """Run one tool call and record it in ctx.events. Never raises."""
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return {"ok": False, "error": "unknown_tool", "message": f"No tool named {name!r}"}
    try:
        args = spec.args.model_validate(raw_args or {})
        async with ctx.session_factory() as db:
            result = await spec.fn(ctx, db, args)
    except ValidationError as exc:
        result = {"ok": False, "error": "invalid_arguments", "message": _short(exc)}
    except ToolInputError as exc:
        result = {"ok": False, "error": "invalid_arguments", "message": str(exc)}
    except DomainError as exc:
        result = {"ok": False, "error": exc.code, "message": exc.message}
    except Exception:
        logger.exception("tool_failed tool=%s", name)
        result = {"ok": False, "error": "internal_error", "message": "System error, try again"}
    ctx.events.add(CallEvent(tool=name, kind=spec.kind, ok=bool(result["ok"]), data=result))
    return result


def _short(exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    return f"{where}: {first['msg']}" if where else str(first["msg"])
