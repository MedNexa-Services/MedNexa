"""Text chat with the agent in a terminal: Phase 1's "text-only, no voice" mode.

    uv run mednexa-chat                          # first active hospital, test caller
    uv run mednexa-chat --phone +919812345678 --hospital-id <uuid>

Type /quit to end the call; the summary and outcome are printed at the end.
"""

import argparse
import asyncio
import logging
import uuid

from app.database import SessionFactory, engine
from app.models import Hospital
from sqlalchemy import select

from agent.agent import MedNexaAgent
from agent.config import get_settings


async def first_active_hospital() -> uuid.UUID:
    async with SessionFactory() as db:
        hospital_id = await db.scalar(
            select(Hospital.id).where(Hospital.is_active).order_by(Hospital.created_at).limit(1)
        )
    if hospital_id is None:
        raise SystemExit(
            "No hospital found. Seed one with: cd backend && uv run python -m scripts.seed"
        )
    return hospital_id


async def run(phone: str, hospital_id: uuid.UUID | None) -> None:
    hospital_id = hospital_id or await first_active_hospital()
    agent = MedNexaAgent(phone, hospital_id)
    print(f"[caller {phone} -> hospital {hospital_id}, LLM mode {get_settings().llm_mode}]")
    print(f"agent> {await agent.get_greeting()}")
    loop = asyncio.get_running_loop()
    while True:
        try:
            text = await loop.run_in_executor(None, input, "you> ")
        except (EOFError, KeyboardInterrupt):
            break
        if text.strip() in {"/quit", "/exit"}:
            break
        print(f"agent> {await agent.process(text, agent.language)}")
        stats = agent.router.stats
        print(f"       [{stats.last_provider}, {stats.last_latency_ms} ms]")
    print(f"\n[outcome: {agent.call_outcome}]\n[summary: {await agent.get_summary()}]")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the MedNexa agent in the terminal")
    parser.add_argument("--phone", default="+919876543210", help="caller ID to simulate")
    parser.add_argument("--hospital-id", type=uuid.UUID, default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="log routing and tools")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    asyncio.run(run(args.phone, args.hospital_id))


if __name__ == "__main__":
    main()
