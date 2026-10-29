"""Full agent turns: real graph, tools and database, with a scripted LLM."""

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


async def test_greeting_names_the_hospital(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [])
    greeting = await agent.get_greeting()
    assert "Test City Hospital" in greeting
    assert "हिंदी" in greeting


async def test_booking_conversation_end_to_end(seed, session_factory) -> None:
    def offer(messages):
        slot = last_tool_result(messages)["slots"][0]
        return say(f"{slot['doctor_name']} is free on {slot['weekday']} at {slot['time']}. "
                   "Shall I book it, and what is the patient's name?")  # fmt: skip

    def do_book(messages):
        # The earlier find_next_available result is still in the conversation history.
        slot = last_tool_result(messages)["slots"][0]
        return call("book_appointment", "c2", patient_name="Rahul Kumar",
                    doctor_id=slot["doctor_id"], date=slot["date"], time=slot["time"])  # fmt: skip

    def confirm(messages):
        token = last_tool_result(messages)["token_number"]
        return say(f"Your appointment has been booked. Your token number is {token}.")

    agent, provider = make_agent(
        seed,
        session_factory,
        [
            call(
                "find_next_available", "c1", speciality="cardio", preferred_date=MONDAY.isoformat()
            ),
            offer,
            do_book,
            confirm,
        ],
    )
    await agent.get_greeting()
    first = await agent.process("I need a heart doctor next Monday", "en")
    assert first.startswith("Dr. Anil Sharma is free on Monday at 09:00")

    second = await agent.process("Yes please, the patient is Rahul Kumar", "en")
    assert second == "Your appointment has been booked. Your token number is 1."

    async with session_factory() as db:
        appt = await db.scalar(select(Appointment))
    assert appt.status == AppointmentStatus.BOOKED
    assert agent.call_outcome == "BOOKED"
    assert "Booked Rahul Kumar with Dr. Anil Sharma" in (await agent.get_summary() or "")

    # The LLM saw: system prompt, greeting, and both caller turns (memory across turns).
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


async def test_llm_failure_hands_over_to_staff(seed, session_factory) -> None:
    agent, _ = make_agent(seed, session_factory, [RuntimeError("model down")])
    reply = await agent.process("Hello", "en")
    assert "connect you to our staff" in reply
    assert agent.escalated and agent.call_outcome == "ESCALATED"
    assert "Agent error" in (await agent.get_summary() or "")


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
    assert await same_caller.process("Cancel Rahul Kumar's appointment", "en") == (
        "Your appointment has been cancelled."
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
    agent.ctx.hospital_id = uuid.uuid4()  # e.g. a misconfigured hospital id
    greeting = await agent.get_greeting()
    assert greeting.startswith("Namaste!") and "हिंदी" in greeting
    # The next turn can't build a prompt either, so the caller is handed to staff.
    assert "connect you to our staff" in await agent.process("Hello", "en")
