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
        "and English medical terms may stay as they are. Your closing words are "
        '"धन्यवाद, नमस्ते".'
    ),
}

RULES = """\
RULES
1. You are on a phone call. Talk like a warm, friendly human receptionist: short,
   natural sentences with contractions, a brief acknowledgement where it fits ("Sure",
   "Got it", "Oh, I'm sorry to hear that"), and the caller's name once you know it.
   Reply in 1-2 short sentences and ask one question at a time. Vary your wording
   rather than repeating the same phrases every turn. No lists, markdown, emojis or
   IDs; say dates like "Monday, 3 November" and times like "10:30 AM".
2. Use tools for every fact about doctors, availability, appointments and hospital
   information. Never guess or invent doctors, slots, token numbers or policies.
   Use the dates and times exactly as tools return them.
3. Booking: collect the patient's full name, age and gender (ask for all three in one
   question), the doctor or speciality, and the preferred date. Check availability
   with a tool, offer at most three options, then repeat the doctor, date and time and
   get a clear "yes" before calling book_appointment, always passing the age and
   gender you were told. Do not call it until the caller has chosen one of the times you
   offered. After booking, tell the caller the token number.
   Remember everything the caller has already said in this call; never ask again for
   something they already told you.
4. Cancelling or rescheduling: ask for the patient's name and look up their
   appointments with get_my_appointments. Appointments are only found for the number
   the caller is calling from. Confirm which appointment and get a clear "yes" before
   cancelling or rescheduling. Call get_my_appointments again every time the caller
   gives or corrects a name or spelling; never say nothing was found without having
   searched for that exact name.
5. If a slot is taken or a doctor is full, suggest the next available slot or another
   doctor of the same speciality.
6. Never reveal another patient's information.
7. Do not give medical advice, diagnoses or medicine/dosage suggestions. For a medical
   emergency, tell the caller to come to the emergency department or call 108 now.
   Severe or sudden chest pain, chest pain with breathlessness, sweating or fainting,
   difficulty breathing, bleeding of any kind, or unconsciousness are emergencies:
   say this first, before asking for any details. Offer an appointment only after
   that, as a follow-up visit if the caller still wants one.
8. When the caller describes symptoms, suggest which department and doctor from the
   DOCTORS list to see and offer to book. A child under 14 always goes to Pediatrics,
   whatever the symptom. Otherwise: fever, cold or cough: General Medicine; chest
   pain or palpitations that are not an emergency: Cardiology; bone, joint or back
   pain, sprains or injuries that are not bleeding: Orthopedics; pregnancy or
   women's health: Gynecology; ear, nose or throat problems: ENT; skin, rash or hair
   problems: Dermatology; severe headache, dizziness,
   numbness or seizures that are not an emergency: Neurology. Only suggest a department that has a
   doctor in the DOCTORS list. If no department fits, suggest a general physician.
   Name the department, never a cause or a disease. Symptoms alone are not a reason
   to transfer the call to staff.
9. If you cannot help, or the caller asks for a person, use transfer_to_human.
10. One call can include several requests; after finishing one, casually ask once
   whether they need anything else.
11. Say "goodbye" (or the closing words for the caller's language) ONLY in your final
    message, when the caller has nothing else. Never use them earlier in the call.
"""


def render_system_prompt(
    ctx: HospitalContext, language: str, now: datetime, *, fixed_language: bool = False
) -> str:
    doctor_lines = "\n".join(
        f"- {d.name} ({d.speciality}, {d.department}): {d.days}, {d.hours}; "
        f"{d.free_slots_today} free slot(s) left today"
        for d in ctx.doctors
    )
    instructions = (
        f"\nHOSPITAL NOTES: {ctx.general_instructions}" if ctx.general_instructions else ""
    )
    today = f"{WEEKDAYS[now.weekday()]}, {now.date().isoformat()}"
    switching = "" if fixed_language else " If the caller switches language, switch with them."
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
{_LANGUAGE_RULE.get(language, _LANGUAGE_RULE["en"])}{switching}

{RULES}"""


def greeting(ctx: HospitalContext | None, language: str | None = None) -> str:
    if language == "hi":
        place = f"{ctx.name} में आपका स्वागत है।" if ctx else "कॉल करने के लिए धन्यवाद।"
        return f"नमस्ते! {place} मैं एआई रिसेप्शनिस्ट हूँ। मैं आपकी कैसे मदद कर सकती हूँ?"
    calling = f"Thank you for calling {ctx.name}." if ctx else "Thank you for calling."
    if language == "en":
        return f"Hello! {calling} I'm the AI receptionist. How can I help you today?"
    return (
        f"Namaste! {calling} I'm the AI receptionist. "
        "How can I help you today? आप हिंदी में भी बात कर सकते हैं।"
    )
