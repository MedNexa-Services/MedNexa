import argparse
import asyncio
import random
from datetime import date, time, timedelta

from sqlalchemy import select, text

from app.core.exceptions import DomainError
from app.core.timeutils import hospital_now
from app.database import SessionFactory, engine
from app.models import Base, BookingSource, Hospital
from app.schemas.appointment import BookingRequest
from app.schemas.doctor import DoctorCreate
from app.schemas.hospital import HospitalCreate, HospitalInfoCreate
from app.schemas.patient import PatientIn
from app.schemas.schedule import ScheduleOverrideIn
from app.services import (
    appointment_service,
    doctor_service,
    hospital_service,
    schedule_service,
    slot_service,
)

HOSPITAL_NAME = "MedNexa City Hospital"

DOCTORS = [
    ("Dr. Anil Sharma", "Cardiologist", "Cardiology", "MBBS, MD, DM (Cardiology)",
     [1, 2, 3, 4, 5], time(9), time(13), 15, 16),
    ("Dr. Meera Iyer", "Cardiologist", "Cardiology", "MBBS, MD, DNB (Cardiology)",
     [2, 4, 6], time(14), time(18), 20, 12),
    ("Dr. Rajesh Verma", "Orthopedic Surgeon", "Orthopedics", "MBBS, MS (Ortho)",
     [1, 3, 5], time(10), time(14), 20, 12),
    ("Dr. Kavita Singh", "Orthopedic Surgeon", "Orthopedics", "MBBS, DNB (Ortho)",
     [2, 4, 6], time(9), time(12), 15, 10),
    ("Dr. Suresh Patel", "General Physician", "General Medicine", "MBBS, MD (Medicine)",
     [1, 2, 3, 4, 5, 6], time(9), time(13), 10, 24),
    ("Dr. Anjali Gupta", "General Physician", "General Medicine", "MBBS",
     [1, 2, 3, 4, 5], time(16), time(20), 10, 20),
    ("Dr. Neha Kulkarni", "Pediatrician", "Pediatrics", "MBBS, MD (Pediatrics)",
     [1, 2, 3, 4, 5, 6], time(10), time(14), 15, 20),
    ("Dr. Sunita Rao", "Gynecologist", "Gynecology", "MBBS, MS (Obstetrics and Gynaecology)",
     [1, 3, 5], time(11), time(15), 20, 12),
    ("Dr. Imran Qureshi", "ENT Specialist", "ENT", "MBBS, MS (ENT)",
     [2, 4, 6], time(10), time(13), 15, 12),
    ("Dr. Pooja Nair", "Dermatologist", "Dermatology", "MBBS, MD (Dermatology)",
     [1, 2, 3, 4, 5], time(15), time(18), 15, 12),
    ("Dr. Vikram Joshi", "Neurologist", "Neurology", "MBBS, DM (Neurology)",
     [2, 4], time(11), time(14), 20, 9),
]  # fmt: skip

# (doctor, days from today, available, opens, closes, reason)
OVERRIDES = [
    ("Dr. Anil Sharma", 7, False, None, None, "Conference"),
    ("Dr. Rajesh Verma", 7, True, None, time(12), "Surgery at 12"),
    ("Dr. Meera Iyer", 10, False, None, None, "Medical conference"),
    ("Dr. Anjali Gupta", 8, True, None, time(18), "Clinic review meeting"),
    ("Dr. Suresh Patel", 12, False, None, None, "Personal leave"),
    ("Dr. Neha Kulkarni", 9, False, None, None, "Vaccination camp"),
    ("Dr. Sunita Rao", 11, False, None, None, "Surgery day"),
    ("Dr. Vikram Joshi", 10, True, time(13), None, "Ward rounds in the morning"),
]  # fmt: skip

DEMO_DAYS = 13

FAQ = [
    ("Timings", "What are the OPD timings?",
     "OPD runs Monday to Saturday, 9 AM to 8 PM. Emergency is open 24x7."),
    ("Location", "Where is the hospital located?",
     "12 Civil Lines, near Gol Bazaar, Jabalpur, Madhya Pradesh 482001."),
    ("Parking", "Is parking available?",
     "Free parking for cars and two-wheelers is available in the basement."),
    ("Emergency", "Is there an emergency department?",
     "Yes, the emergency department and ambulance service (call 108) are available 24x7."),
    ("Pharmacy", "Is there a pharmacy in the hospital?",
     "The in-house pharmacy on the ground floor is open 24 hours."),
    ("Insurance", "Which insurance and payment options are accepted?",
     "Cashless treatment is available with major insurers and Ayushman Bharat. "
     "Cash, cards and UPI are accepted."),
    ("Departments", "Which departments are available?",
     "Cardiology, Orthopedics, General Medicine, Pediatrics, Gynecology, ENT, Dermatology "
     "and Neurology, plus radiology and pathology labs."),
    ("Reports", "How do I collect lab reports?",
     "Lab reports are ready within 24 hours and can be collected at the pathology "
     "counter or received on WhatsApp."),
    ("Visiting", "What are the visiting hours for admitted patients?",
     "Visiting hours are 5 PM to 7 PM every day, with one attendant allowed per patient."),
    ("Booking", "How early should I book an appointment?",
     "Appointments can be booked up to two weeks ahead. Walk-ins are seen as slots allow."),
    ("Lab", "What are the pathology lab timings?",
     "The pathology collection counter is open 7 AM to 8 PM, Monday to Saturday."),
]  # fmt: skip

PATIENTS = [
    ("Rahul Kumar", "+919876543210", 34, "MALE"),
    ("Sita Kumar", "+919876543210", 31, "FEMALE"),
    ("Priya Sharma", "+919812345678", 27, "FEMALE"),
    ("Mohan Lal", "+919900112233", 62, "MALE"),
]

FAMILIES = [
    ("Verma", [("Amit", 41, "MALE"), ("Neelam", 38, "FEMALE"), ("Aarav", 9, "MALE")]),
    ("Joshi", [("Deepak", 52, "MALE"), ("Kamla", 49, "FEMALE")]),
    ("Tiwari", [("Sanjay", 45, "MALE"), ("Pooja", 40, "FEMALE"), ("Ritika", 12, "FEMALE")]),
    ("Khan", [("Faisal", 36, "MALE"), ("Shabana", 33, "FEMALE"), ("Zoya", 6, "FEMALE")]),
    ("Yadav", [("Manoj", 58, "MALE"), ("Sushila", 55, "FEMALE")]),
    ("Malhotra", [("Karan", 29, "MALE"), ("Divya", 27, "FEMALE")]),
    ("Singh", [("Harpreet", 47, "MALE"), ("Gurpreet", 44, "FEMALE")]),
    ("Nair", [("Arjun", 31, "MALE"), ("Lakshmi", 64, "FEMALE")]),
    ("Pandey", [("Vivek", 35, "MALE"), ("Anita", 32, "FEMALE")]),
    ("Dubey", [("Rohit", 26, "MALE"), ("Sneha", 24, "FEMALE")]),
    ("Chaturvedi", [("Mahesh", 67, "MALE"), ("Savita", 63, "FEMALE")]),
    ("Ansari", [("Imran", 39, "MALE"), ("Nasreen", 35, "FEMALE")]),
    ("Deshmukh", [("Tanvi", 22, "FEMALE"), ("Yash", 4, "MALE")]),
]  # fmt: skip

SOURCES = [BookingSource.DASHBOARD] * 5 + [BookingSource.AI_CALL] * 4 + [BookingSource.WALK_IN]


def next_working_day(after: date, days: list[int]) -> date:
    d = after + timedelta(days=1)
    while d.isoweekday() not in days:
        d += timedelta(days=1)
    return d


async def reset() -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


async def seed() -> None:
    async with SessionFactory() as db:
        if await db.scalar(select(Hospital).where(Hospital.name == HOSPITAL_NAME)):
            print(f"'{HOSPITAL_NAME}' already exists; use --reset to recreate it.")
            return

        hospital = await hospital_service.create_hospital(
            db,
            HospitalCreate(
                name=HOSPITAL_NAME,
                address="12 Civil Lines, Jabalpur, Madhya Pradesh 482001",
                phone="+917612400000",
                email="reception@mednexa.example",
                opening_time=time(9),
                closing_time=time(20),
                general_instructions="Patients should arrive 15 minutes before their slot.",
            ),
        )
        for category, question, answer in FAQ:
            await hospital_service.create_info(
                db,
                hospital.id,
                HospitalInfoCreate(category=category, question=question, answer=answer),
            )

        doctors = []
        for name, spec, dept, qual, days, start, end, slot, cap in DOCTORS:
            doctors.append(
                await doctor_service.create_doctor(
                    db,
                    DoctorCreate(
                        hospital_id=hospital.id,
                        name=name,
                        speciality=spec,
                        department=dept,
                        qualification=qual,
                        available_days=days,
                        slot_start_time=start,
                        slot_end_time=end,
                        slot_duration_minutes=slot,
                        max_daily_appointments=cap,
                    ),
                )
            )

        today = hospital_now(hospital.timezone).date()
        sharma, iyer, verma, *_ = doctors
        by_name = {d.name: d for d in doctors}
        for doctor_name, offset, available, opens, closes, reason in OVERRIDES:
            doctor = by_name[doctor_name]
            await schedule_service.upsert_override(
                db,
                doctor.id,
                ScheduleOverrideIn(
                    date=next_working_day(
                        today + timedelta(days=offset - 1), doctor.available_days
                    ),
                    is_available=available,
                    start_time=opens,
                    end_time=closes,
                    override_reason=reason,
                ),
            )

        bookings = [
            (PATIENTS[0], sharma, 0),
            (PATIENTS[1], sharma, 1),
            (PATIENTS[2], iyer, 0),
            (PATIENTS[3], verma, 0),
        ]
        booked = 0
        for (name, phone, age, gender), doctor, slot_index in bookings:
            on = next_working_day(today, doctor.available_days)
            slots = await slot_service.get_available_slots(db, doctor.id, on)
            try:
                await appointment_service.book_appointment(
                    db,
                    BookingRequest(
                        patient=PatientIn(name=name, phone=phone, age=age, gender=gender),
                        doctor_id=doctor.id,
                        appointment_date=on,
                        appointment_time=slots[slot_index].start,
                        booking_source=BookingSource.DASHBOARD,
                    ),
                )
                booked += 1
            except (DomainError, IndexError) as exc:
                print(f"Skipped a sample booking for {name}: {exc}")

        rng = random.Random(15)
        people = [
            (f"{first} {family}", f"+91981200{number:04d}", age, gender)
            for number, (family, members) in enumerate(FAMILIES)
            for first, age, gender in members
        ]
        cancelled = 0
        for offset in range(1, DEMO_DAYS + 1):
            on = today + timedelta(days=offset)
            for doctor in doctors:
                slots = await slot_service.get_available_slots(db, doctor.id, on)
                if not slots:
                    continue
                busiest = 4 if offset <= 4 else 2
                for chosen in rng.sample(slots, min(len(slots), rng.randint(0, busiest))):
                    name, phone, age, gender = rng.choice(people)
                    try:
                        confirmation = await appointment_service.book_appointment(
                            db,
                            BookingRequest(
                                patient=PatientIn(name=name, phone=phone, age=age, gender=gender),
                                doctor_id=doctor.id,
                                appointment_date=on,
                                appointment_time=chosen.start,
                                booking_source=rng.choice(SOURCES),
                            ),
                        )
                    except DomainError:
                        continue
                    booked += 1
                    if rng.random() < 0.1:
                        await appointment_service.cancel_appointment_by_staff(
                            db, confirmation.appointment_id, "Patient asked to cancel"
                        )
                        cancelled += 1

        print(
            f"Seeded '{HOSPITAL_NAME}' ({hospital.id}): {len(doctors)} doctors, "
            f"{len(FAQ)} FAQ entries, {len(OVERRIDES)} schedule overrides, "
            f"{booked} appointments ({cancelled} cancelled)."
        )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed a sample hospital: doctors, schedule overrides, FAQ entries and bookings."
    )
    parser.add_argument("--reset", action="store_true", help="delete all data first")
    args = parser.parse_args()
    if args.reset:
        await reset()
    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
