from datetime import time

import pytest
from app.models import Appointment, AppointmentStatus
from sqlalchemy import select

from agent.tools import TOOLS, ToolContext, ToolInputError, execute_tool, parse_time
from tests.conftest import CALLER, MONDAY, NOW


@pytest.fixture
def ctx(seed, session_factory) -> ToolContext:
    return ToolContext(
        hospital_id=seed.hospital.id,
        caller_phone=CALLER,
        session_factory=session_factory,
        now=lambda: NOW,
    )


def other_caller(ctx: ToolContext, phone: str | None = "+919999999999") -> ToolContext:
    return ToolContext(ctx.hospital_id, phone, ctx.session_factory, now=ctx.now)


async def book(ctx: ToolContext, seed, at: str = "09:00", name: str = "Rahul Kumar") -> dict:
    return await execute_tool(
        ctx,
        "book_appointment",
        {"patient_name": name, "doctor_id": str(seed.cardiologist.id), "date": MONDAY.isoformat(),
         "time": at, "patient_age": 34, "patient_gender": "male"},
    )  # fmt: skip


async def test_info_tools(ctx, seed) -> None:
    info = await execute_tool(ctx, "get_hospital_info", {"query": "where do I park?"})
    assert info["results"][0]["answer"] == "Free parking in the basement."

    doctors = await execute_tool(ctx, "list_doctors", {"speciality": "cardio"})
    assert [d["name"] for d in doctors["doctors"]] == ["Dr. Anil Sharma"]
    assert doctors["doctors"][0]["days"][0] == "Monday"

    details = await execute_tool(
        ctx, "get_doctor_details", {"doctor_id": str(seed.dermatologist.id)}
    )
    assert details["doctor"]["department"] == "Dermatology"

    slots = await execute_tool(
        ctx,
        "check_available_slots",
        {"doctor_id": str(seed.cardiologist.id), "date": MONDAY.isoformat()},
    )
    assert slots["free_slots"] == ["09:00", "09:30", "10:00", "10:30"]
    assert slots["weekday"] == "Monday"

    nxt = await execute_tool(ctx, "find_next_available", {"speciality": "derma", "limit": 1})
    assert nxt["slots"][0]["doctor_name"] == "Dr. Neha Rao"

    now = await execute_tool(ctx, "get_current_datetime", {})
    assert now == {"ok": True, "date": NOW.date().isoformat(), "weekday": "Friday", "time": "08:00"}


async def test_booking_uses_caller_phone_and_records_event(ctx, seed, session_factory) -> None:
    result = await book(ctx, seed)
    assert result["ok"] and result["token_number"] == 1
    assert result["time"] == "09:00" and result["weekday"] == "Monday"

    async with session_factory() as db:
        appt = await db.scalar(select(Appointment))
    assert appt.booking_source.value == "AI_CALL"
    assert ctx.events.succeeded("book")[0].data["token_number"] == 1


async def test_booking_errors_come_back_as_results(ctx, seed) -> None:
    await book(ctx, seed)
    taken = await book(ctx, seed, name="Priya Sharma")
    assert taken == {
        "ok": False,
        "error": "slot_unavailable",
        "message": "That slot is already booked",
    }

    off_grid = await book(ctx, seed, at="09:10")
    assert off_grid["error"] == "invalid_slot"

    bad_date = await execute_tool(
        ctx,
        "check_available_slots",
        {"doctor_id": str(seed.cardiologist.id), "date": "next Monday"},
    )
    assert bad_date["error"] == "invalid_arguments"

    bad_id = await execute_tool(ctx, "get_doctor_details", {"doctor_id": "dr-sharma"})
    assert bad_id["error"] == "invalid_arguments"

    missing = await execute_tool(ctx, "book_appointment", {"patient_name": "X"})
    assert missing["error"] == "invalid_arguments"

    assert (await execute_tool(ctx, "drop_tables", {}))["error"] == "unknown_tool"
    assert not ctx.events.succeeded("book")[1:]


async def test_twelve_hour_time_is_accepted(ctx, seed) -> None:
    result = await book(ctx, seed, at="10:30 AM")
    assert result["time"] == "10:30"


async def test_lookup_cancel_and_reschedule_flow(ctx, seed) -> None:
    await book(ctx, seed)
    mine = await execute_tool(ctx, "get_my_appointments", {"patient_name": "rahul kumar"})
    appt_id = mine["appointments"][0]["appointment_id"]

    moved = await execute_tool(
        ctx,
        "reschedule_appointment",
        {"appointment_id": appt_id, "new_date": MONDAY.isoformat(), "new_time": "10:00"},
    )
    assert moved["ok"] and moved["time"] == "10:00" and moved["token_number"] == 2

    cancelled = await execute_tool(
        ctx, "cancel_appointment", {"appointment_id": moved["appointment_id"], "reason": "better"}
    )
    assert cancelled["status"] == AppointmentStatus.CANCELLED.value
    assert (await execute_tool(ctx, "get_my_appointments", {"patient_name": "Rahul Kumar"}))[
        "appointments"
    ] == []


async def test_other_callers_cannot_see_or_cancel(ctx, seed) -> None:
    booked = await book(ctx, seed)
    stranger = other_caller(ctx)
    assert (await execute_tool(stranger, "get_my_appointments", {"patient_name": "Rahul Kumar"}))[
        "appointments"
    ] == []
    denied = await execute_tool(
        stranger, "cancel_appointment", {"appointment_id": booked["appointment_id"]}
    )
    assert denied["error"] == "not_owner"


async def test_tools_needing_caller_id_fail_without_it(ctx, seed) -> None:
    anonymous = other_caller(ctx, phone=None)
    result = await book(anonymous, seed)
    assert result["ok"] is False and "phone number is unavailable" in result["message"]


async def test_doctor_from_another_hospital_is_hidden(ctx, seed, session_factory) -> None:
    other = ToolContext(
        hospital_id=seed.dermatologist.id,  # any id that isn't this doctor's hospital
        caller_phone=CALLER,
        session_factory=session_factory,
        now=lambda: NOW,
    )
    result = await execute_tool(
        other, "get_doctor_details", {"doctor_id": str(seed.cardiologist.id)}
    )
    assert result["ok"] is False


async def test_transfer_sets_escalation(ctx) -> None:
    result = await execute_tool(ctx, "transfer_to_human", {"reason": "Caller wants billing"})
    assert result["ok"] and ctx.escalation_reason == "Caller wants billing"
    assert ctx.events.outcome() == "ESCALATED"


@pytest.mark.parametrize(
    "text, expected",
    [("09:30", time(9, 30)), ("9:05", time(9, 5)), ("4 pm", time(16)), ("12:15 a.m.", time(0, 15))],
)
def test_parse_time(text: str, expected: time) -> None:
    assert parse_time(text) == expected


@pytest.mark.parametrize("text", ["13 pm", "noon", "25:00"])
def test_parse_time_rejects_garbage(text: str) -> None:
    with pytest.raises(ToolInputError):
        parse_time(text)


def test_tool_schemas_are_well_formed() -> None:
    names = [t.name for t in TOOLS]
    assert len(names) == len(set(names))
    for spec in TOOLS:
        schema = spec.schema()
        assert schema["type"] == "function"
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "title" not in params
    book = next(t for t in TOOLS if t.name == "book_appointment").schema()
    assert set(book["function"]["parameters"]["required"]) == {
        "patient_name", "doctor_id", "date", "time"
    }  # fmt: skip
