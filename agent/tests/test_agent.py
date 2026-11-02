import json
import uuid
from collections.abc import Sequence

import pytest
from app.models import Appointment, AppointmentStatus
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy import select

from agent.agent import MedNexaAgent
from agent.config import AgentSettings
from agent.graph import FINAL_ANSWER_NOTE, recent_history
from agent.router import ModelRouter
from tests.conftest import CALLER, MONDAY, NOW
from tests.fakes import ScriptedProvider, call, say


def last_tool_result(messages: Sequence[BaseMessage]) -> dict:
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    return json.loads(tool_messages[-1].content)


def make_agent(seed, session_factory, replies, *, phone: str = CALLER, **settings):
    provider = ScriptedProvider("scripted", replies)
    settings.setdefault("confirm_changes", False)
    settings.setdefault("llm_retry_delay_seconds", 0)
    config = AgentSettings(_env_file=None, **settings)
    agent = MedNexaAgent(
        phone,
        str(seed.hospital.id),
        router=ModelRouter(config, provider, None),
        settings=config,
        session_factory=session_factory,
        now=lambda: NOW,
    )
    return agent, provider


async def test_greeting_is_in_hindi_when_the_caller_chose_hindi(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [])
    agent.fixed_language = "hi"
    greeting = await agent.get_greeting()
    assert "Test City Hospital" in greeting
    assert "नमस्ते" in greeting
    assert "AI receptionist" not in greeting


async def test_a_caller_who_chose_english_is_never_switched_to_hindi(seed, session_factory) -> None:
    agent, provider = make_agent(seed, session_factory, [say("Sure.")])
    agent.fixed_language = "en"
    greeting = await agent.get_greeting()
    assert "हिंदी" not in greeting
    await agent.process("mujhe kal doctor se milna hai", "hi")
    assert agent.language == "en"
    system_prompt = provider.calls[0][0][0].content
    assert "Reply in English" in system_prompt
    assert "switch with them" not in system_prompt


async def test_greeting_names_the_hospital(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [])
    greeting = await agent.get_greeting()
    assert "Test City Hospital" in greeting
    assert "हिंदी" in greeting


BOOK_ARGS_MONDAY_9 = "Rahul Kumar with Dr. Anil Sharma on Monday, "


async def test_booking_waits_for_the_caller_to_say_yes_to_the_read_back(
    seed, session_factory
) -> None:
    args = {
        "patient_name": "Rahul Kumar",
        "doctor_id": str(seed.cardiologist.id),
        "date": MONDAY.isoformat(),
        "time": "09:00",
    }

    agent, provider = make_agent(
        seed,
        session_factory,
        [call("book_appointment", "c1", **args), call("book_appointment", "c2", **args)],
        confirm_changes=True,
    )
    reply = await agent.process("Book a heart doctor on Monday for Rahul Kumar", "en")
    assert reply.startswith("Just to confirm: " + BOOK_ARGS_MONDAY_9)
    assert reply.endswith("at 9:00 AM. Shall I book it?")
    async with session_factory() as db:
        assert await db.scalar(select(Appointment)) is None
    assert agent.call_outcome == "OTHER"

    done = await agent.process("Yes, please", "en")
    assert done.startswith("All set! Your appointment is booked with Dr. Anil Sharma on Monday, ")
    assert "Your token number is 1." in done
    async with session_factory() as db:
        assert (await db.scalar(select(Appointment))).status == AppointmentStatus.BOOKED
    assert agent.call_outcome == "BOOKED"

    assert len(provider.calls) == 2
    asked = [m.content for m in provider.calls[-1][0] if m.type == "ai" and not m.tool_calls]
    assert any(text.startswith("Just to confirm: ") for text in asked)


@pytest.mark.parametrize(
    "answer",
    ["No, make it 10 AM", "Actually, not today", "Hmm, wait", "The first slot is okay but later"],
)
async def test_anything_but_a_clear_yes_does_not_book(seed, session_factory, answer) -> None:
    args = {
        "patient_name": "Rahul Kumar",
        "doctor_id": str(seed.cardiologist.id),
        "date": MONDAY.isoformat(),
        "time": "09:00",
    }
    agent, _ = make_agent(
        seed,
        session_factory,
        [call("book_appointment", "c1", **args), call("book_appointment", "c2", **args)],
        confirm_changes=True,
    )  # fmt: skip
    await agent.process("Book Dr. Sharma Monday 9 for Rahul Kumar", "en")
    reply = await agent.process(answer, "en")
    assert reply.startswith("Just to confirm: ")
    async with session_factory() as db:
        assert await db.scalar(select(Appointment)) is None


async def test_a_yes_to_a_different_question_does_not_book(seed, session_factory) -> None:
    first = {
        "patient_name": "Rahul Kumar",
        "doctor_id": str(seed.cardiologist.id),
        "date": MONDAY.isoformat(),
        "time": "09:00",
    }
    other = {**first, "time": "09:30"}
    agent, _ = make_agent(
        seed,
        session_factory,
        [call("book_appointment", "c1", **first), call("book_appointment", "c2", **other)],
        confirm_changes=True,
    )  # fmt: skip
    await agent.process("Book Dr. Sharma Monday 9 for Rahul Kumar", "en")
    reply = await agent.process("Yes", "en")
    assert "9:30 AM" in reply and reply.startswith("Just to confirm: ")
    async with session_factory() as db:
        assert await db.scalar(select(Appointment)) is None


async def test_a_model_that_books_twice_in_one_turn_still_waits_for_the_caller(
    seed, session_factory
) -> None:
    args = {
        "patient_name": "Rahul Kumar",
        "doctor_id": str(seed.cardiologist.id),
        "date": MONDAY.isoformat(),
        "time": "09:00",
    }
    both = AIMessage(
        content="",
        tool_calls=[
            {"name": "book_appointment", "args": args, "id": "c1"},
            {"name": "book_appointment", "args": args, "id": "c2"},
        ],
    )
    agent, _ = make_agent(seed, session_factory, [both], confirm_changes=True)
    reply = await agent.process("Book Dr. Sharma Monday 9 for Rahul Kumar", "en")
    assert reply.startswith("Just to confirm: ")
    async with session_factory() as db:
        assert await db.scalar(select(Appointment)) is None


async def test_the_confirmation_names_the_patient_doctor_and_time(seed, session_factory) -> None:
    args = {
        "patient_name": "Rahul Kumar",
        "doctor_id": str(seed.cardiologist.id),
        "date": MONDAY.isoformat(),
        "time": "09:00",
    }
    agent, _ = make_agent(
        seed,
        session_factory,
        [call("book_appointment", "c1", **args), say("You're booked for Monday at 9 AM!")],
        confirm_changes=True,
    )
    reply = await agent.process("Book Dr. Sharma Monday 9 for Rahul Kumar", "en")
    assert reply.startswith("Just to confirm: Rahul Kumar with Dr. Anil Sharma on Monday, ")
    assert reply.endswith("at 9:00 AM. Shall I book it?")


async def test_a_taken_slot_is_reported_before_asking_for_confirmation(
    seed, session_factory
) -> None:
    other, _ = make_agent(
        seed, session_factory,
        [call("book_appointment", patient_name="Someone Else", doctor_id=str(seed.cardiologist.id),
              date=MONDAY.isoformat(), time="09:00"), say("Booked.")],
    )  # fmt: skip
    await other.process("Book 9 AM", "en")

    def after(messages):
        assert last_tool_result(messages)["error"] == "slot_unavailable"
        return say("Sorry, that time is taken.")

    agent, _ = make_agent(
        seed, session_factory,
        [call("book_appointment", patient_name="Rahul Kumar", doctor_id=str(seed.cardiologist.id),
              date=MONDAY.isoformat(), time="09:00"), after],
        phone="+919000000002", confirm_changes=True,
    )  # fmt: skip
    assert await agent.process("Book 9 AM", "en") == "Sorry, that time is taken."


async def test_cancelling_needs_confirmation_too(seed, session_factory) -> None:
    owner, _ = make_agent(
        seed, session_factory,
        [call("book_appointment", patient_name="Rahul Kumar", doctor_id=str(seed.cardiologist.id),
              date=MONDAY.isoformat(), time="09:00"), say("Booked.")],
    )  # fmt: skip
    await owner.process("Book 9 AM for Rahul Kumar", "en")

    def cancel(call_id):
        def build(messages):
            appts = last_tool_result(messages)["appointments"]
            return call("cancel_appointment", call_id, appointment_id=appts[0]["appointment_id"])

        return build

    agent, _ = make_agent(
        seed, session_factory,
        [call("get_my_appointments", "c1", patient_name="Rahul Kumar"), cancel("c2"),
         say("Do you want me to cancel the 9 AM appointment?")],
        confirm_changes=True,
    )  # fmt: skip
    reply = await agent.process("Cancel Rahul Kumar's appointment", "en")
    assert reply.startswith(
        "Just to confirm: cancel Rahul Kumar's appointment with Dr. Anil Sharma"
    )
    assert reply.endswith("Shall I cancel it?")
    async with session_factory() as db:
        assert (await db.scalar(select(Appointment))).status == AppointmentStatus.BOOKED
    assert agent.call_outcome == "INFO_PROVIDED"


async def test_booking_conversation_end_to_end(seed, session_factory) -> None:
    def offer(messages):
        slot = last_tool_result(messages)["slots"][0]
        return say(f"{slot['doctor_name']} is free on {slot['weekday']} at {slot['time']}. "
                   "Shall I book it, and what is the patient's name?")  # fmt: skip

    def do_book(messages):
        slot = last_tool_result(messages)["slots"][0]
        return call("book_appointment", "c2", patient_name="Rahul Kumar",
                    doctor_id=slot["doctor_id"], date=slot["date"], time=slot["time"])  # fmt: skip

    agent, provider = make_agent(
        seed,
        session_factory,
        [
            call(
                "find_next_available", "c1", speciality="cardio", preferred_date=MONDAY.isoformat()
            ),
            offer,
            do_book,
        ],
    )
    await agent.get_greeting()
    first = await agent.process("I need a heart doctor next Monday", "en")
    assert first.startswith("Dr. Anil Sharma is free on Monday at 09:00")

    second = await agent.process("Yes please, the patient is Rahul Kumar", "en")
    assert second.startswith("All set! Your appointment is booked with Dr. Anil Sharma on Monday")
    assert "Your token number is 1." in second

    async with session_factory() as db:
        appt = await db.scalar(select(Appointment))
    assert appt.status == AppointmentStatus.BOOKED
    assert agent.call_outcome == "BOOKED"
    assert "Booked Rahul Kumar with Dr. Anil Sharma" in (await agent.get_summary() or "")

    sent, tools = provider.calls[-1]
    assert isinstance(sent[0], SystemMessage) and "Test City Hospital" in sent[0].content
    assert sent[1].content.startswith("Namaste!")
    assert [m.content for m in sent if isinstance(m, HumanMessage)] == [
        "I need a heart doctor next Monday",
        "Yes please, the patient is Rahul Kumar",
    ]
    assert any(t["function"]["name"] == "book_appointment" for t in tools)


async def test_hindi_turn_switches_prompt_language(seed, session_factory) -> None:
    agent, provider = make_agent(seed, session_factory, [say("जी, बताइए।")])
    reply = await agent.process("मुझे डॉक्टर से मिलना है", "en")
    assert reply == "जी, बताइए।"
    assert agent.language == "hi"
    assert "Devanagari" in provider.calls[0][0][0].content


async def test_ungrounded_booking_claim_is_replaced(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [say("Done, your appointment is booked!")])
    reply = await agent.process("Book me with Dr. Sharma", "en")
    assert reply.startswith("Sorry, I couldn't complete that yet")


async def test_tool_round_limit_forces_an_answer(seed, session_factory) -> None:
    loop = [call("get_current_datetime", f"c{i}") for i in range(2)]
    agent, provider = make_agent(
        seed, session_factory, [*loop, say("It is Friday morning.")], max_tool_rounds=2
    )
    reply = await agent.process("What day is it?", "en")
    assert reply == "It is Friday morning."
    final_messages, final_tools = provider.calls[-1]
    assert final_tools == []
    assert final_messages[-1].content == FINAL_ANSWER_NOTE


async def test_tool_calls_after_the_limit_are_dropped(seed, session_factory) -> None:
    stubborn = AIMessage(
        content="Let me check.",
        tool_calls=[{"name": "get_current_datetime", "args": {}, "id": "x"}],
    )
    agent, _ = make_agent(
        seed, session_factory, [call("get_current_datetime"), stubborn], max_tool_rounds=1
    )
    assert await agent.process("time?", "en") == "Let me check."


async def test_one_failed_turn_asks_the_caller_to_repeat_and_the_call_goes_on(
    seed, session_factory
) -> None:
    agent, _ = make_agent(seed, session_factory, [RuntimeError("blip"), say("Hello there.")])
    assert "say that again" in await agent.process("Hello", "en")
    assert not agent.escalated
    assert await agent.process("Hello", "en") == "Hello there."
    assert agent.call_outcome == "OTHER"


async def test_repeated_failures_hand_over_to_staff(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [RuntimeError("model down")] * 3)
    assert not agent.escalated
    for _ in range(2):
        assert "say that again" in await agent.process("Hello", "en")
        assert not agent.escalated
    reply = await agent.process("Hello", "en")
    assert "connect you to our staff" in reply
    assert agent.escalated and agent.call_outcome == "ESCALATED"
    assert "Agent error" in (await agent.get_summary() or "")


async def test_a_good_turn_resets_the_failure_count(seed, session_factory) -> None:
    errors = [RuntimeError("blip")] * 2
    agent, _ = make_agent(seed, session_factory, [*errors, say("ok"), *errors, say("ok")])
    for expected in ("say that again", "say that again", "ok", "say that again", "say that again"):
        assert expected in await agent.process("Hello", "en")
    assert not agent.escalated


async def test_the_greeting_survives_a_failed_first_turn(seed, session_factory) -> None:
    agent, provider = make_agent(seed, session_factory, [RuntimeError("blip"), say("Hi.")])
    await agent.get_greeting()
    await agent.process("Hello", "en")
    await agent.process("Hello", "en")
    sent, _ = provider.calls[-1]
    assert sent[1].content.startswith("Hello!") or sent[1].content.startswith("Namaste!")


async def test_speech_hints_name_the_doctors_and_departments(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [])
    assert agent.speech_hints is None
    await agent.get_greeting()
    hints = agent.speech_hints
    assert "Test City Hospital" in hints and "Dr. Anil Sharma" in hints and "Cardiology" in hints


async def test_empty_utterance_does_not_call_the_llm(seed, session_factory) -> None:
    agent, provider = make_agent(seed, session_factory, [])
    assert "didn't catch" in await agent.process("   ", "en")
    assert provider.calls == []


async def test_cancel_flow_with_ownership(seed, session_factory) -> None:
    owner, _ = make_agent(
        seed,
        session_factory,
        [call("book_appointment", patient_name="Rahul Kumar", doctor_id=str(seed.cardiologist.id),
              date=MONDAY.isoformat(), time="09:00"),
         say("Booked. Your token number is 1.")],
    )  # fmt: skip
    await owner.process("Book Dr. Sharma Monday 9 for Rahul Kumar", "en")

    def cancel_found(messages):
        appts = last_tool_result(messages)["appointments"]
        return call("cancel_appointment", "c2", appointment_id=appts[0]["appointment_id"])

    same_caller, _ = make_agent(
        seed,
        session_factory,
        [call("get_my_appointments", "c1", patient_name="Rahul Kumar"), cancel_found,
         say("Your appointment has been cancelled.")],
    )  # fmt: skip
    cancelled = await same_caller.process("Cancel Rahul Kumar's appointment", "en")
    assert cancelled.startswith(
        "Done. I've cancelled Rahul Kumar's appointment with Dr. Anil Sharma"
    )
    assert same_caller.call_outcome == "CANCELLED"


async def test_unparseable_caller_id_is_tolerated(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [], phone="anonymous")
    assert agent.ctx.caller_phone is None


def test_recent_history_never_starts_mid_tool_exchange() -> None:
    messages: list[BaseMessage] = [
        HumanMessage("one"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="{}", tool_call_id="1"),
        AIMessage(content="answer"),
        HumanMessage("two"),
        AIMessage(content="reply"),
    ]
    assert [m.content for m in recent_history(messages, 4)] == ["answer", "two", "reply"]
    assert [m.content for m in recent_history(messages, 5)] == ["answer", "two", "reply"]
    assert recent_history(messages, 10) == messages


@pytest.mark.parametrize("limit", [1, 2])
def test_recent_history_keeps_latest_caller_turn(limit: int) -> None:
    tool_call = AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}])
    messages: list[BaseMessage] = [
        HumanMessage("only"),
        tool_call,
        ToolMessage(content="{}", tool_call_id="1"),
    ]
    assert [m.content for m in recent_history(messages, limit)] == ["only"]


async def test_greeting_survives_a_missing_hospital(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [])
    agent.ctx.hospital_id = uuid.uuid4()
    greeting = await agent.get_greeting()
    assert greeting.startswith("Namaste!") and "हिंदी" in greeting
    for _ in range(2):
        assert "say that again" in await agent.process("Hello", "en")
    assert "connect you to our staff" in await agent.process("Hello", "en")
