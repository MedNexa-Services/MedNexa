"""System prompt with hospital context loaded from the database (task 2.6).

Patient data is never put in the prompt; the agent fetches it per call via tools.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, time

from app.core.timeutils import hospital_now
from app.services import contracts, hospital_service
from sqlalchemy.ext.asyncio import AsyncSession

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass(frozen=True)
class DoctorSummary:
    name: str
    speciality: str
    department: str
    days: str
    hours: str
    free_slots_today: int


@dataclass(frozen=True)
class HospitalContext:
    hospital_id: uuid.UUID
    name: str
    address: str
    phone: str
    opening_time: time
    closing_time: time
    timezone: str
    general_instructions: str | None
    departments: list[str]
    doctors: list[DoctorSummary]


def _fmt_time(t: time) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def _fmt_days(days: list[int]) -> str:
    return ", ".join(WEEKDAYS[d - 1][:3] for d in days)


async def load_hospital_context(
    db: AsyncSession, hospital_id: uuid.UUID, now: datetime | None = None
) -> HospitalContext:
    hospital = await hospital_service.get_hospital(db, hospital_id)
    now = now or hospital_now(hospital.timezone)
    doctors = await contracts.list_doctors(db, hospital_id)
    summaries = []
    for d in doctors:
        free_today = await contracts.get_available_slots(db, d.id, now.date(), now=now)
        summaries.append(
            DoctorSummary(
                name=d.name,
                speciality=d.speciality,
                department=d.department,
                days=_fmt_days(d.available_days),
                hours=f"{_fmt_time(d.slot_start_time)}-{_fmt_time(d.slot_end_time)}",
                free_slots_today=len(free_today),
            )
        )
    return HospitalContext(
        hospital_id=hospital.id,
        name=hospital.name,
        address=hospital.address,
        phone=hospital.phone,
        opening_time=hospital.opening_time,
        closing_time=hospital.closing_time,
        timezone=hospital.timezone,
        general_instructions=hospital.general_instructions,
        departments=sorted({d.department for d in doctors}),
        doctors=summaries,
    )


_LANGUAGE_RULE = {
    "en": "The caller is speaking English. Reply in English.",
    "hi": (
        "The caller is speaking Hindi. Reply in simple, polite Hindi written in "
        "Devanagari script (your reply is read aloud by a Hindi voice). Doctor names "
        "and English medical terms may stay as they are."
    ),
}

RULES = """\
RULES
1. You are on a phone call: answer in 1-3 short sentences, one question at a time.
   No lists, markdown, emojis or IDs; say dates like "Monday, 3 November" and times
   like "10:30 AM".
2. Use tools for every fact about doctors, availability, appointments and hospital
   information. Never guess or invent doctors, slots, token numbers or policies.
   Use the dates and times exactly as tools return them.
3. Booking: collect the patient's full name, the doctor or speciality, and the
   preferred date (age and gender if offered). Check availability with a tool, offer
   at most three options, then repeat the doctor, date and time and get a clear "yes"
   before calling book_appointment. After booking, tell the caller the token number.
4. Cancelling or rescheduling: ask for the patient's name and look up their
   appointments with get_my_appointments. Appointments are only found for the number
   the caller is calling from. Confirm which appointment and get a clear "yes" before
   cancelling or rescheduling.
5. If a slot is taken or a doctor is full, suggest the next available slot or another
   doctor of the same speciality.
6. Never reveal another patient's information.
7. Do not give medical advice, diagnoses or medicine/dosage suggestions. For a medical
   emergency, tell the caller to come to the emergency department or call 108 now.
8. If you cannot help, or the caller asks for a person, use transfer_to_human.
9. One call can include several requests; after finishing one, ask if there is
   anything else.
10. Say "goodbye" (Hindi: "धन्यवाद, नमस्ते") ONLY in your final message, when the
    caller has nothing else. Never use these words earlier in the call.
"""


def render_system_prompt(ctx: HospitalContext, language: str, now: datetime) -> str:
    doctor_lines = "\n".join(
        f"- {d.name} ({d.speciality}, {d.department}): {d.days}, {d.hours}; "
        f"{d.free_slots_today} free slot(s) left today"
        for d in ctx.doctors
    )
    instructions = (
        f"\nHOSPITAL NOTES: {ctx.general_instructions}" if ctx.general_instructions else ""
    )
    today = f"{WEEKDAYS[now.weekday()]}, {now.date().isoformat()}"
    return f"""\
You are MedNexa, the AI receptionist answering phone calls for {ctx.name}.

HOSPITAL CONTEXT
- Address: {ctx.address}
- Phone: {ctx.phone}
- Hours: {_fmt_time(ctx.opening_time)} to {_fmt_time(ctx.closing_time)}
- Departments: {", ".join(ctx.departments) or "none listed"}
- Today: {today}; current time {_fmt_time(now.time())}{instructions}

DOCTORS (use tools for live availability)
{doctor_lines or "- No active doctors."}

LANGUAGE
{_LANGUAGE_RULE.get(language, _LANGUAGE_RULE["en"])} If the caller switches language,
switch with them.

{RULES}"""


def greeting(ctx: HospitalContext | None) -> str:
    """Opening line; works without hospital context (e.g. the database is down)."""
    calling = f"Thank you for calling {ctx.name}." if ctx else "Thank you for calling."
    return (
        f"Namaste! {calling} I'm the AI receptionist. "
        "How can I help you today? आप हिंदी में भी बात कर सकते हैं।"
    )
