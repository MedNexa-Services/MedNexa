from datetime import time

import pytest
from app.models import Appointment, AppointmentStatus
from app.schemas.hospital import HospitalCreate
from app.services import hospital_service
from sqlalchemy import select

from agent.tools import (
    TOOLS,
    ToolContext,
    ToolInputError,
    execute_tool,
    parse_time,
    says_yes,
    speciality_key,
)
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


@pytest.mark.parametrize(
    ("term", "name"),
    [("Cardiology", "Dr. Anil Sharma"), ("heart", "Dr. Anil Sharma"),
     ("dermatology", "Dr. Neha Rao"), ("Skin specialist", "Dr. Neha Rao")],
)  # fmt: skip
async def test_speciality_names_are_matched_loosely(ctx, seed, term, name) -> None:
    doctors = await execute_tool(ctx, "list_doctors", {"speciality": term})
    assert [d["name"] for d in doctors["doctors"]] == [name]
    nxt = await execute_tool(ctx, "find_next_available", {"speciality": term, "limit": 1})
    assert nxt["slots"][0]["doctor_name"] == name


def test_speciality_key_handles_british_spelling() -> None:
    assert speciality_key("Orthopaedics") == speciality_key("Orthopedic Surgeon") == "ortho"
    assert speciality_key("paediatrician") == "pedia"
    assert speciality_key("ENT") == "ent"


async def test_a_doctor_name_works_in_place_of_an_id(ctx, seed) -> None:
    slots = await execute_tool(
        ctx, "check_available_slots", {"doctor_id": "Dr. Anil Sharma", "date": MONDAY.isoformat()}
    )
    assert slots["ok"] and slots["free_slots"] == ["09:00", "09:30", "10:00", "10:30"]
    unknown = await execute_tool(
        ctx, "check_available_slots", {"doctor_id": "Dr. Nobody", "date": MONDAY.isoformat()}
    )
    assert unknown["error"] == "invalid_arguments"


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


@pytest.fixture
async def other_hospital_ctx(ctx, session_factory) -> ToolContext:
    async with session_factory() as db:
        other = await hospital_service.create_hospital(
            db,
            HospitalCreate(name="Other Hospital", address="2 Station Rd", phone="+917612999999",
                           opening_time=time(9), closing_time=time(17)),
        )  # fmt: skip
    return ToolContext(other.id, CALLER, session_factory, now=lambda: NOW)


async def test_tools_only_reach_this_hospitals_doctors(other_hospital_ctx, seed) -> None:
    doctor_id = str(seed.cardiologist.id)
    for tool, args in [
        ("get_doctor_details", {"doctor_id": doctor_id}),
        ("check_available_slots", {"doctor_id": doctor_id, "date": MONDAY.isoformat()}),
        ("book_appointment", {"patient_name": "Rahul Kumar", "doctor_id": doctor_id,
                              "date": MONDAY.isoformat(), "time": "09:00"}),
    ]:  # fmt: skip
        result = await execute_tool(other_hospital_ctx, tool, args)
        assert result["error"] == "not_found", (tool, result)


async def test_tools_only_reach_this_hospitals_appointments(ctx, other_hospital_ctx, seed) -> None:
    booked = await book(ctx, seed)
    appt = {"appointment_id": booked["appointment_id"]}
    cancelled = await execute_tool(other_hospital_ctx, "cancel_appointment", appt)
    moved = await execute_tool(
        other_hospital_ctx,
        "reschedule_appointment",
        {**appt, "new_date": MONDAY.isoformat(), "new_time": "10:00"},
    )
    assert cancelled["error"] == moved["error"] == "not_found"


async def test_transfer_sets_escalation(ctx) -> None:
    ctx.turn = 3
    result = await execute_tool(ctx, "transfer_to_human", {"reason": "Caller wants billing"})
    assert result["ok"] and ctx.escalation_reason == "Caller wants billing"
    assert ctx.events.outcome() == "ESCALATED"


@pytest.mark.parametrize(
    "said",
    [
        "I want to talk to a real person about my bill, please.",
        "Can you connect me to the staff?",
        "मुझे किसी इंसान से बात करनी है",
    ],
)
async def test_transfer_is_immediate_when_the_caller_asks_for_a_person(ctx, said) -> None:
    ctx.confirm_changes = True
    ctx.last_caller_text = said
    result = await execute_tool(ctx, "transfer_to_human", {"reason": "Caller asked"})
    assert result["ok"] and ctx.escalation_reason == "Caller asked"


async def test_a_greeting_is_never_transferred(ctx) -> None:
    ctx.confirm_changes = True
    ctx.last_caller_text = "Hey, good evening."
    ctx.turn = 1
    result = await execute_tool(ctx, "transfer_to_human", {"reason": "greeting only"})
    assert not result["ok"] and result["error"] == "not_requested"
    assert ctx.readback is None and ctx.escalation_reason is None


async def test_a_later_unrequested_transfer_asks_the_caller_first(ctx) -> None:
    ctx.confirm_changes = True
    ctx.last_caller_text = "I don't understand the bill they sent me."
    ctx.turn = 3
    first = await execute_tool(ctx, "transfer_to_human", {"reason": "billing"})
    assert not first["ok"] and first["error"] == "needs_confirmation"
    assert first["readback"] == "Would you like me to connect you to one of our staff?"
    assert ctx.escalation_reason is None

    ctx.readback_spoken, ctx.turn, ctx.last_caller_text = True, 4, "Yes, please."
    second = await execute_tool(ctx, "transfer_to_human", {"reason": "billing"})
    assert second["ok"] and ctx.escalation_reason == "billing"


async def test_a_transfer_the_caller_declines_does_not_happen(ctx) -> None:
    ctx.confirm_changes, ctx.turn = True, 3
    ctx.last_caller_text = "I have a question about my bill."
    await execute_tool(ctx, "transfer_to_human", {"reason": "x"})
    ctx.readback_spoken, ctx.turn, ctx.last_caller_text = True, 4, "No thanks, I'll manage."
    result = await execute_tool(ctx, "transfer_to_human", {"reason": "x"})
    assert not result["ok"] and ctx.escalation_reason is None


@pytest.mark.parametrize(
    "text",
    ["Yes", "yes please", "Yeah, go ahead.", "Okay", "Sure", "That's correct", "Haan ji",
     "हाँ, कर दीजिए", "Yes, please confirm.", "The first slot is fine."],
)  # fmt: skip
def test_clear_yes(text: str) -> None:
    assert says_yes(text)


@pytest.mark.parametrize(
    "text",
    ["No", "No, thanks", "Not really", "Wait a moment", "Yes but make it later", "Actually no",
     "नहीं", "What?", "Tomorrow morning please", ""],
)  # fmt: skip
def test_not_a_clear_yes(text: str) -> None:
    assert not says_yes(text)


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
