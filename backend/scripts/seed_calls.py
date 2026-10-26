import httpx
import json

API = "http://127.0.0.1:8000/api/v1"
hospital_id = "01b587a3-f471-4406-a1c6-4deb8dd44845"
apt_id = "61a26598-453f-40a9-982a-6ea76a41a540"

with httpx.Client() as client:
    # Call 1: Booked Appointment
    c1 = client.post(f"{API}/calls", json={
        "hospital_id": hospital_id,
        "caller_phone": "+919876543210",
        "language_detected": "en"
    }).json()
    s1_id = c1["id"]

    client.post(f"{API}/calls/{s1_id}/logs", json={
        "role": "ASSISTANT",
        "content": "Namaste! Welcome to MedNexa City Hospital. I am your AI receptionist. How may I assist your health needs today?"
    })
    client.post(f"{API}/calls/{s1_id}/logs", json={
        "role": "USER",
        "content": "Hello, I want to book an appointment with Dr. Anil Sharma for tomorrow morning."
    })
    client.post(f"{API}/calls/{s1_id}/logs", json={
        "role": "TOOL",
        "content": "Checking availability for Dr. Sharma on 2026-10-26...",
        "tool_called": "check_available_slots",
        "tool_result": "{\"available_slots\": [\"09:00:00\", \"09:15:00\", \"09:30:00\"]}"
    })
    client.post(f"{API}/calls/{s1_id}/logs", json={
        "role": "ASSISTANT",
        "content": "Dr. Sharma has openings tomorrow starting at 9:00 AM and 9:15 AM. Would 9:00 AM work for you?"
    })
    client.post(f"{API}/calls/{s1_id}/logs", json={
        "role": "USER",
        "content": "Yes, 9:00 AM is perfect. My name is Rahul Kumar."
    })
    client.post(f"{API}/calls/{s1_id}/logs", json={
        "role": "TOOL",
        "content": "Booking confirmed in database.",
        "tool_called": "book_appointment",
        "tool_result": "{\"token_number\": 1, \"status\": \"BOOKED\"}",
        "appointment_id": apt_id
    })
    client.post(f"{API}/calls/{s1_id}/logs", json={
        "role": "ASSISTANT",
        "content": "Your appointment with Dr. Anil Sharma is confirmed for tomorrow at 9:00 AM. Your token number is #1. Please arrive 15 minutes before your slot.",
        "appointment_id": apt_id
    })
    client.post(f"{API}/calls/{s1_id}/end", json={
        "call_outcome": "BOOKED",
        "summary": "Caller Rahul Kumar booked a cardiology slot with Dr. Anil Sharma for 2026-10-26 at 09:00 AM. Token #1 assigned.",
        "language_detected": "en",
        "escalated_to_human": False
    })

    # Call 2: FAQ Enquiry in Hindi
    c2 = client.post(f"{API}/calls", json={
        "hospital_id": hospital_id,
        "caller_phone": "+919812345678",
        "language_detected": "hi"
    }).json()
    s2_id = c2["id"]

    client.post(f"{API}/calls/{s2_id}/logs", json={
        "role": "ASSISTANT",
        "content": "नमस्ते! मेडनेक्सा सिटी हॉस्पिटल में आपका स्वागत है। मैं आपकी क्या सहायता कर सकता हूँ?"
    })
    client.post(f"{API}/calls/{s2_id}/logs", json={
        "role": "USER",
        "content": "नमस्ते, क्या अस्पताल में पार्किंग की व्यवस्था है और ओपीडी कब तक खुली रहती है?"
    })
    client.post(f"{API}/calls/{s2_id}/logs", json={
        "role": "TOOL",
        "content": "Searching knowledge base...",
        "tool_called": "query_hospital_info",
        "tool_result": "{\"answer\": \"Free parking available in basement. OPD runs Mon-Sat 9 AM to 8 PM.\"}"
    })
    client.post(f"{API}/calls/{s2_id}/logs", json={
        "role": "ASSISTANT",
        "content": "हाँ, अस्पताल के बेसमेंट में कार और टू-व्हीलर के लिए निःशुल्क पार्किंग उपलब्ध है। ओपीडी सोमवार से शनिवार सुबह 9 बजे से रात 8 बजे तक खुली रहती है।"
    })
    client.post(f"{API}/calls/{s2_id}/logs", json={
        "role": "USER",
        "content": "बहुत धन्यवाद जानकारी के लिए।"
    })
    client.post(f"{API}/calls/{s2_id}/logs", json={
        "role": "ASSISTANT",
        "content": "आपका स्वागत है! स्वास्थ्य का ध्यान रखें। शुभ दिन!"
    })
    client.post(f"{API}/calls/{s2_id}/end", json={
        "call_outcome": "INFO_PROVIDED",
        "summary": "कॉलर ने अस्पताल की पार्किंग और ओपीडी के समय के बारे में जानकारी मांगी। हिंदी में संतोषजनक उत्तर दिया गया।",
        "language_detected": "hi",
        "escalated_to_human": False
    })

    # Call 3: Emergency Escalation
    c3 = client.post(f"{API}/calls", json={
        "hospital_id": hospital_id,
        "caller_phone": "+919900112233",
        "language_detected": "en"
    }).json()
    s3_id = c3["id"]

    client.post(f"{API}/calls/{s3_id}/logs", json={
        "role": "ASSISTANT",
        "content": "Welcome to MedNexa City Hospital. How can I help you today?"
    })
    client.post(f"{API}/calls/{s3_id}/logs", json={
        "role": "USER",
        "content": "I am feeling severe sudden chest pain and sweating, difficulty breathing!"
    })
    client.post(f"{API}/calls/{s3_id}/logs", json={
        "role": "TOOL",
        "content": "Emergency safety trigger invoked.",
        "tool_called": "escalate_emergency",
        "tool_result": "{\"priority\": \"CRITICAL\", \"action\": \"TRANSFER_TO_ER\"}"
    })
    client.post(f"{API}/calls/{s3_id}/logs", json={
        "role": "ASSISTANT",
        "content": "Please stay calm. I am immediately transferring this call to our Emergency Medical Team and dispatching assistance. Please do not hang up."
    })
    client.post(f"{API}/calls/{s3_id}/end", json={
        "call_outcome": "ESCALATED",
        "summary": "Caller Mohan Lal presented acute emergency cardiac symptoms (severe chest pain, dyspnea). Escalated immediately to ER staff.",
        "language_detected": "en",
        "escalated_to_human": True
    })

    print("Successfully seeded 3 rich call sessions with transcripts!")
