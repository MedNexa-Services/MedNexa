"""Agent evaluation harness (task 2.13): scripted caller conversations run against
the configured *real* LLM and a seeded database, checked on what the agent did.

    cd backend && uv run python -m scripts.seed --reset    # fresh sample data
    cd agent   && uv run python -m agent.evals             # all scenarios
    cd agent   && uv run python -m agent.evals booking_en  # one scenario

Each scenario is a list of caller lines plus checks on the outcome: which tools
were called, whether an action succeeded, and the call outcome. The report shows
pass/fail, per-turn latency and the provider used. Write actions are rolled back
afterwards by cancelling anything the scenario booked.

The unit tests exercise this harness with a scripted LLM; these scenarios are meant
for comparing models and prompts (e.g. llama3.1:8b vs a cloud model) by hand.
"""

import argparse
import asyncio
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.database import SessionFactory, engine
from app.services import appointment_service

from agent.agent import MedNexaAgent
from agent.chat import first_active_hospital
from agent.events import CallEvents

Check = Callable[[MedNexaAgent], str | None]  # returns a failure message, or None


def called(tool: str) -> Check:
    def check(agent: MedNexaAgent) -> str | None:
        used = {e.tool for e in agent.ctx.events.events}
        return None if tool in used else f"expected a {tool} call; got {sorted(used)}"

    return check


def not_called(tool: str) -> Check:
    def check(agent: MedNexaAgent) -> str | None:
        used = {e.tool for e in agent.ctx.events.events}
        return f"{tool} must not be called" if tool in used else None

    return check


def outcome(expected: str) -> Check:
    def check(agent: MedNexaAgent) -> str | None:
        got = agent.call_outcome
        return None if got == expected else f"expected outcome {expected}, got {got}"

    return check


def replied_in(language: str) -> Check:
    def check(agent: MedNexaAgent) -> str | None:
        return None if agent.language == language else f"language ended as {agent.language}"

    return check


@dataclass
class Scenario:
    name: str
    caller_lines: list[str]
    checks: list[Check]
    phone: str = "+919876543210"


SCENARIOS = [
    Scenario(
        "info_parking",
        ["Hi, is there parking at the hospital?", "Thanks, that's all. Bye."],
        [called("get_hospital_info"), outcome("INFO_PROVIDED"), not_called("book_appointment")],
    ),
    Scenario(
        "booking_en",
        [
            "I'd like to see a cardiologist as soon as possible.",
            "The earliest one is fine. The patient is Amit Verma, 45, male.",
            "Yes, please book it.",
            "No, that's all, thank you.",
        ],
        [called("find_next_available"), called("book_appointment"), outcome("BOOKED")],
    ),
    Scenario(
        "booking_hi",
        [
            "नमस्ते, मुझे हड्डी के डॉक्टर को दिखाना है।",
            "जो सबसे पहला समय है वही ठीक है। मरीज़ का नाम सुनीता देवी है।",
            "हाँ, बुक कर दीजिए।",
        ],
        [called("book_appointment"), outcome("BOOKED"), replied_in("hi")],
        phone="+919811112222",
    ),
    Scenario(
        "medical_advice_refused",
        ["I have a bad headache, which tablet should I take?"],
        [not_called("book_appointment")],
    ),
    Scenario(
        "human_handoff",
        ["I want to talk to a real person about my bill, please."],
        [called("transfer_to_human"), outcome("ESCALATED")],
    ),
    Scenario(
        "lookup_needs_name",
        ["Do I have any appointment booked?", "The patient name is Rahul Kumar."],
        [called("get_my_appointments")],
    ),
]


@dataclass
class Turn:
    caller: str
    agent: str
    latency_ms: int
    provider: str | None


@dataclass
class Result:
    scenario: str
    turns: list[Turn] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


async def run_scenario(
    scenario: Scenario, make_agent: Callable[[str], MedNexaAgent]
) -> tuple[Result, MedNexaAgent]:
    agent = make_agent(scenario.phone)
    result = Result(scenario.name)
    greeting = await agent.get_greeting()
    result.turns.append(Turn("", greeting, 0, None))
    for line in scenario.caller_lines:
        start = time.monotonic()
        reply = await agent.process(line, agent.language)
        result.turns.append(
            Turn(
                line,
                reply,
                int((time.monotonic() - start) * 1000),
                agent.router.stats.last_provider,
            )
        )
    result.failures = [msg for check in scenario.checks if (msg := check(agent))]
    return result, agent


async def undo_bookings(events: CallEvents) -> None:
    """Cancel what a scenario booked so repeated runs start from the same data."""
    async with SessionFactory() as db:
        for event in events.succeeded("book") + events.succeeded("reschedule"):
            await appointment_service.cancel_appointment_by_staff(
                db, uuid.UUID(event.data["appointment_id"]), "evaluation cleanup"
            )


def print_report(results: Sequence[Result]) -> None:
    for r in results:
        print(f"\n=== {r.scenario}: {'PASS' if r.passed else 'FAIL'} ===")
        for t in r.turns:
            if t.caller:
                print(f"  caller: {t.caller}")
            suffix = f"   [{t.provider}, {t.latency_ms} ms]" if t.caller else ""
            print(f"  agent:  {t.agent}{suffix}")
        for failure in r.failures:
            print(f"  ✗ {failure}")
    passed = sum(r.passed for r in results)
    latencies = [t.latency_ms for r in results for t in r.turns if t.caller]
    avg = sum(latencies) // len(latencies) if latencies else 0
    print(f"\n{passed}/{len(results)} scenarios passed; average turn latency {avg} ms")


async def main_async(names: Sequence[str]) -> int:
    hospital_id = await first_active_hospital()
    selected = [s for s in SCENARIOS if not names or s.name in names]
    results = []
    for scenario in selected:
        result, agent = await run_scenario(scenario, lambda phone: MedNexaAgent(phone, hospital_id))
        await undo_bookings(agent.ctx.events)
        results.append(result)
    print_report(results)
    await engine.dispose()
    return 0 if all(r.passed for r in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent evaluation scenarios")
    parser.add_argument(
        "scenarios", nargs="*", help=f"any of: {', '.join(s.name for s in SCENARIOS)}"
    )
    raise SystemExit(asyncio.run(main_async(parser.parse_args().scenarios)))


if __name__ == "__main__":
    main()
