from datetime import date, time
from typing import Any

MONTHS_HI = [
    "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
    "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
]  # fmt: skip


def _clock(value: str) -> str:
    hour, minute = (int(part) for part in value.strip().split(":")[:2])
    return time(hour, minute).strftime("%I:%M %p").lstrip("0")


def _when(data: dict[str, Any], language: str) -> str:
    day = date.fromisoformat(data["date"])
    at = _clock(data["time"])
    if language == "hi":
        return f"{day.day} {MONTHS_HI[day.month - 1]}, {at}"
    return f"{data['weekday']}, {day.day} {day.strftime('%B')} at {at}"


def done_reply(kind: str, data: dict[str, Any], language: str) -> str:
    when = _when(data, language)
    doctor, patient, token = data["doctor_name"], data["patient_name"], data["token_number"]
    if language == "hi":
        more = "क्या मैं और कुछ मदद कर सकती हूँ?"
        return {
            "book": f"आपकी अपॉइंटमेंट {doctor} के साथ {when} पर बुक हो गई है। आपका टोकन नंबर "
            f"{token} है। कृपया पंद्रह मिनट पहले पहुँचिए। {more}",
            "cancel": f"{patient} की {doctor} के साथ {when} की अपॉइंटमेंट रद्द कर दी गई है। {more}",
            "reschedule": f"{patient} की अपॉइंटमेंट अब {doctor} के साथ {when} पर है। आपका टोकन नंबर "
            f"{token} है। {more}",
        }[kind]
    more = "Is there anything else I can help you with?"
    return {
        "book": f"All set! Your appointment is booked with {doctor} on {when}. "
        f"Your token number is {token}. Please arrive about 15 minutes early. {more}",
        "cancel": f"Done. I've cancelled {patient}'s appointment with {doctor} on {when}. {more}",
        "reschedule": f"Done. {patient}'s appointment with {doctor} is now on {when}. "
        f"Your token number is {token}. {more}",
    }[kind]
