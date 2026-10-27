from datetime import timedelta

from tests.api.helpers import create_doctor, create_hospital
from tests.factories import next_weekday

_MONDAY = next_weekday(1, weeks_ahead=2)
MONDAY = _MONDAY.isoformat()
# Derived from MONDAY so it is always the following day (computing it separately
# put it before MONDAY when the tests ran on a Tuesday).
TUESDAY = (_MONDAY + timedelta(days=1)).isoformat()


async def _book(client, doctor_id: str, at: str, name: str = "Rahul Kumar", **kw):
    return await client.post(
        "/api/v1/appointments",
        json={
            "patient": {"name": name, "phone": kw.pop("phone", "98765 43210")},
            "doctor_id": doctor_id,
            "appointment_date": kw.pop("on", MONDAY),
            "appointment_time": at,
            **kw,
        },
    )


async def test_patient_endpoints(client) -> None:
    hospital = await create_hospital(client)
    created = await client.post(
        "/api/v1/patients",
        json={"hospital_id": hospital["id"], "name": " Rahul  Kumar ", "phone": "09876543210"},
    )
    assert created.status_code == 201
    patient = created.json()
    assert patient["name"] == "Rahul Kumar" and patient["phone"] == "+919876543210"

    duplicate = await client.post(
        "/api/v1/patients",
        json={"hospital_id": hospital["id"], "name": "rahul kumar", "phone": "+919876543210"},
    )
    assert duplicate.status_code == 409

    by_phone = await client.get("/api/v1/patients", params={"phone": "98765-43210"})
    assert by_phone.json()["total"] == 1
    by_name = await client.get("/api/v1/patients", params={"name": "RAHUL"})
    assert by_name.json()["total"] == 1
    bad_phone = await client.get("/api/v1/patients", params={"phone": "12"})
    assert bad_phone.status_code == 422

    updated = await client.patch(f"/api/v1/patients/{patient['id']}", json={"age": 40})
    assert updated.json()["age"] == 40


async def test_slots_endpoints(client) -> None:
    hospital = await create_hospital(client)
    doctor = await create_doctor(client, hospital["id"], slot_end_time="10:00")

    slots = await client.get(f"/api/v1/doctors/{doctor['id']}/slots", params={"date": MONDAY})
    assert slots.json() == [
        {"start": "09:00:00", "end": "09:30:00"},
        {"start": "09:30:00", "end": "10:00:00"},
    ]

    nxt = await client.get(
        "/api/v1/slots/next-available",
        params={"hospital_id": hospital["id"], "speciality": "cardio", "from": MONDAY, "limit": 1},
    )
    assert nxt.json()[0]["doctor_name"] == "Dr. Sharma"
    assert nxt.json()[0]["date"] == MONDAY


async def test_staff_booking_flow(client) -> None:
    hospital = await create_hospital(client)
    doctor = await create_doctor(client, hospital["id"])

    booked = await _book(client, doctor["id"], "09:00")
    assert booked.status_code == 201
    confirmation = booked.json()
    assert confirmation["token_number"] == 1

    appt = (await client.get(f"/api/v1/appointments/{confirmation['appointment_id']}")).json()
    assert appt["booking_source"] == "DASHBOARD"
    assert appt["patient_phone"] == "+919876543210"

    taken = await _book(client, doctor["id"], "09:00", name="Priya")
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "slot_unavailable"

    off_grid = await _book(client, doctor["id"], "09:10", name="Priya")
    assert off_grid.status_code == 422
    assert off_grid.json()["error"]["code"] == "invalid_slot"

    moved = await client.post(
        f"/api/v1/appointments/{confirmation['appointment_id']}/reschedule",
        json={"new_date": TUESDAY, "new_time": "10:00"},
    )
    assert moved.status_code == 200
    new_id = moved.json()["appointment_id"]

    cancelled = await client.post(
        f"/api/v1/appointments/{new_id}/cancel", json={"reason": "Patient request"}
    )
    assert cancelled.json()["status"] == "CANCELLED"
    again = await client.post(f"/api/v1/appointments/{new_id}/cancel", json={})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "not_cancellable"


async def test_appointment_listing_filters(client) -> None:
    hospital = await create_hospital(client)
    doctor = await create_doctor(client, hospital["id"])
    other = await create_doctor(client, hospital["id"], name="Dr. Patel")
    first = (await _book(client, doctor["id"], "09:00")).json()
    await _book(client, doctor["id"], "09:30", name="Sita Kumar")
    await _book(client, other["id"], "09:00", on=TUESDAY)
    await client.post(f"/api/v1/appointments/{first['appointment_id']}/cancel", json={})

    def query(**params):
        return client.get("/api/v1/appointments", params=params)

    assert (await query()).json()["total"] == 3
    assert (await query(doctor_id=doctor["id"])).json()["total"] == 2
    assert (await query(date=TUESDAY)).json()["total"] == 1
    assert (await query(status="BOOKED")).json()["total"] == 2
    assert (await query(date_from=MONDAY, date_to=MONDAY)).json()["total"] == 2

    page = (await query(limit=1, offset=1)).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert page["items"][0]["appointment_time"] == "09:30:00"

    patients = (await client.get("/api/v1/patients", params={"name": "sita"})).json()["items"]
    history = await client.get(f"/api/v1/patients/{patients[0]['id']}/appointments")
    assert history.json()["total"] == 1


async def test_explicit_booking_source_is_kept(client) -> None:
    hospital = await create_hospital(client)
    doctor = await create_doctor(client, hospital["id"])
    booked = (await _book(client, doctor["id"], "09:00", booking_source="WALK_IN")).json()
    appt = (await client.get(f"/api/v1/appointments/{booked['appointment_id']}")).json()
    assert appt["booking_source"] == "WALK_IN"
