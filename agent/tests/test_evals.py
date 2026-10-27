"""The evaluation harness, driven by a scripted LLM (real runs use a real model)."""

from app.models import Appointment, AppointmentStatus
from sqlalchemy import select

from agent.agent import MedNexaAgent
from agent.config import AgentSettings
from agent.evals import (
    Scenario,
    called,
    not_called,
    outcome,
    print_report,
    replied_in,
    run_scenario,
    undo_bookings,
)
from agent.router import ModelRouter
from tests.conftest import MONDAY, NOW
from tests.fakes import ScriptedProvider, call, say


def factory(seed, session_factory, replies):
    config = AgentSettings(_env_file=None)

    def make(phone: str) -> MedNexaAgent:
        return MedNexaAgent(
            phone,
            seed.hospital.id,
            router=ModelRouter(config, ScriptedProvider("scripted", replies), None),
            settings=config,
            session_factory=session_factory,
            now=lambda: NOW,
        )

    return make


async def test_passing_scenario_and_cleanup(seed, session_factory, monkeypatch, capsys) -> None:
    replies = [
        call("book_appointment", patient_name="Amit Verma", doctor_id=str(seed.cardiologist.id),
             date=MONDAY.isoformat(), time="09:00"),
        say("Booked. Your token number is 1."),
    ]  # fmt: skip
    scenario = Scenario(
        "booking",
        ["Book Dr. Sharma Monday 9 AM for Amit Verma"],
        [called("book_appointment"), not_called("transfer_to_human"), outcome("BOOKED"),
         replied_in("en")],
    )  # fmt: skip
    result, agent = await run_scenario(scenario, factory(seed, session_factory, replies))
    assert result.passed, result.failures
    assert result.turns[1].agent == "Booked. Your token number is 1."
    assert result.turns[1].provider == "scripted"

    monkeypatch.setattr("agent.evals.SessionFactory", session_factory)
    await undo_bookings(agent.ctx.events)
    async with session_factory() as db:
        assert (await db.scalar(select(Appointment))).status == AppointmentStatus.CANCELLED

    print_report([result])
    assert "1/1 scenarios passed" in capsys.readouterr().out


async def test_failing_checks_are_reported(seed, session_factory, capsys) -> None:
    scenario = Scenario(
        "handoff", ["Get me a human"], [called("transfer_to_human"), outcome("ESCALATED"),
                                       replied_in("hi")],
    )  # fmt: skip
    result, _ = await run_scenario(scenario, factory(seed, session_factory, [say("Sure.")]))
    assert not result.passed
    assert len(result.failures) == 3

    print_report([result])
    out = capsys.readouterr().out
    assert "FAIL" in out and "0/1 scenarios passed" in out
