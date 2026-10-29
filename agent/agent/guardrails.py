"""Output guardrails applied to every reply before it is spoken (task 2.10).

Checks, in order:
- empty reply             -> ask the caller to repeat
- medical advice          -> replaced with a safe refusal + offer to book a doctor
- ungrounded action claim -> a "booked/cancelled/rescheduled" or token-number claim
                             with no matching successful tool result in this call
                             is replaced with a safe retry message
- internal IDs (UUIDs)    -> removed (never read aloud)
- length                  -> trimmed at a sentence boundary for speech
"""

import re
from dataclasses import dataclass, field

from agent.events import ActionKind, CallEvents

_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")

_MEDICAL_ADVICE = [
    re.compile(p, re.I)
    for p in (
        r"\b\d+(\.\d+)?\s?(mg|mcg|ml|milligrams?)\b",
        r"\b(take|taking|try)\b.{0,40}\b(tablets?|pills?|capsules?|syrups?|paracetamol|"
        r"ibuprofen|aspirin|crocin|dolo|antibiotics?|painkillers?|medicines?|medications?)\b",
        r"\b(dosage|dose of)\b",
        r"\bi (would )?(recommend|suggest|prescribe)\b.{0,40}\b(tablets?|pills?|medicines?|"
        r"medications?|antibiotics?|treatment)\b",
        r"\byou (probably|likely|might|may|could) have (a |an )?\w*\s?(infection|disease|"
        r"diabetes|fever|flu|dengue|malaria|covid|fracture|condition)\b",
        r"(दवा|दवाई|गोली|टैबलेट)\s?(लें|ले लें|लीजिए|खाएं|खाइए)",
        r"खुराक",
    )
]

_CLAIMS: dict[ActionKind, list[re.Pattern[str]]] = {
    "book": [
        re.compile(p, re.I)
        for p in (
            r"\b(appointment|it|slot)\s+(is|has been|was)\s+(successfully\s+)?(booked|confirmed)",
            r"\bi('ve| have)\s+(booked|confirmed)\b",
            r"\bsuccessfully booked\b",
            r"(अपॉइंटमेंट|अपॉइंटमेंट).{0,30}(बुक हो गई|बुक हो गया|कन्फर्म)",
        )
    ],
    "cancel": [
        re.compile(p, re.I)
        for p in (
            r"\b(appointment|it)\s+(is|has been|was)\s+(successfully\s+)?(cancelled|canceled)",
            r"\bi('ve| have)\s+(cancelled|canceled)\b",
            r"(रद्द|कैंसल)\s?(हो गई|हो गया|कर दी|कर दिया)",
        )
    ],
    "reschedule": [
        re.compile(p, re.I)
        for p in (
            r"\b(appointment|it)\s+(is|has been|was)\s+(successfully\s+)?(rescheduled|moved)",
            r"\bi('ve| have)\s+(rescheduled|moved)\b",
        )
    ],
}
_TOKEN_CLAIM = re.compile(r"(token(\s+number)?|टोकन(\s+नंबर)?)\s*(is|है|:)?\s*(\d+)", re.I)

_FALLBACKS = {
    "empty": {
        "en": "Sorry, could you please say that again?",
        "hi": "माफ़ कीजिए, क्या आप दोबारा बता सकते हैं?",
    },
    "medical_advice": {
        "en": (
            "I'm sorry, I can't give medical advice. I can book an appointment with a "
            "doctor for you. If it's an emergency, please come to the emergency "
            "department or call 108."
        ),
        "hi": (
            "माफ़ कीजिए, मैं चिकित्सा सलाह नहीं दे सकती। मैं आपके लिए डॉक्टर के साथ "
            "अपॉइंटमेंट बुक कर सकती हूँ। आपात स्थिति में तुरंत इमरजेंसी विभाग आएं या 108 पर कॉल करें।"
        ),
    },
    "ungrounded_claim": {
        "en": "Sorry, I couldn't complete that yet. Could you confirm the details once more?",
        "hi": "माफ़ कीजिए, यह अभी पूरा नहीं हुआ। क्या आप एक बार फिर विवरण बता सकते हैं?",
    },
}


@dataclass
class GuardrailResult:
    text: str
    violations: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.violations)


def _fallback(kind: str, language: str) -> str:
    return _FALLBACKS[kind].get(language, _FALLBACKS[kind]["en"])


def _ungrounded(text: str, events: CallEvents) -> bool:
    for action, patterns in _CLAIMS.items():
        if any(p.search(text) for p in patterns) and not events.succeeded(action):
            return True
    tokens = {int(m.group(5)) for m in _TOKEN_CLAIM.finditer(text)}
    return bool(tokens - events.confirmed_tokens())


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    kept = ""
    for sentence in _SENTENCE_END.split(text):
        if len(kept) + len(sentence) + 1 > limit:
            break
        kept = f"{kept} {sentence}".strip()
    return kept or text[:limit].rsplit(" ", 1)[0]


def apply_guardrails(
    text: str, events: CallEvents, language: str, *, max_chars: int
) -> GuardrailResult:
    text = text.strip()
    if not text:
        return GuardrailResult(_fallback("empty", language), ["empty"])
    if any(p.search(text) for p in _MEDICAL_ADVICE):
        return GuardrailResult(_fallback("medical_advice", language), ["medical_advice"])
    if _ungrounded(text, events):
        return GuardrailResult(_fallback("ungrounded_claim", language), ["ungrounded_claim"])

    violations = []
    if _UUID.search(text):
        text = re.sub(r"\s{2,}", " ", _UUID.sub("", text)).strip()
        violations.append("internal_id")
    trimmed = _trim(text, max_chars)
    if trimmed != text:
        violations.append("too_long")
    return GuardrailResult(trimmed, violations)
