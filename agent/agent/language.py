import re

SUPPORTED = ("en", "hi")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_WORD = re.compile(r"[a-z]+")

_HINGLISH = {
    "mujhe", "mera", "meri", "mere", "aap", "aapka", "aapki", "hai", "hain", "nahi",
    "nahin", "kya", "kab", "kaise", "kitne", "kitna", "chahiye", "karna", "karni",
    "karwana", "karwani", "kal", "aaj", "parso", "subah", "shaam", "dopahar", "haan",
    "ji", "theek", "thik", "accha", "acha", "bhai", "dikhana", "milna", "lena", "hoga",
    "batao", "bataiye", "bataye", "kripya", "dhanyavaad", "dhanyawad", "namaste",
}  # fmt: skip

_ALIASES = {"ur": "hi", "hin": "hi", "eng": "en"}


def normalize_language(code: str | None) -> str | None:
    if not code:
        return None
    code = _ALIASES.get(code.lower(), code.lower())
    return code if code in SUPPORTED else None


def detect_language(text: str, hint: str | None = None) -> str:
    letters = _LETTER.findall(text)
    if letters and len(_DEVANAGARI.findall(text)) / len(letters) >= 0.3:
        return "hi"
    words = _WORD.findall(text.lower())
    hinglish = sum(w in _HINGLISH for w in words)
    if hinglish >= 2 or (words and hinglish / len(words) >= 0.3):
        return "hi"
    if words and _is_plain_english(words, hinglish):
        return "en"
    return normalize_language(hint) or "en"


def _is_plain_english(words: list[str], hinglish: int) -> bool:
    return hinglish == 0 and len(words) >= 3
