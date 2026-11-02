from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def hospital_now(timezone: str) -> datetime:
    return datetime.now(ZoneInfo(timezone))


def generate_time_slots(start: time, end: time, duration_minutes: int) -> list[time]:
    anchor = date(2000, 1, 1)
    cursor = datetime.combine(anchor, start)
    stop = datetime.combine(anchor, end)
    step = timedelta(minutes=duration_minutes)
    slots = []
    while cursor + step <= stop:
        slots.append(cursor.time())
        cursor += step
    return slots


def add_minutes(t: time, minutes: int) -> time:
    return (datetime.combine(date(2000, 1, 1), t) + timedelta(minutes=minutes)).time()
