"""Pure text helpers: language detection, claim clean-up, rumour patterns, known facts."""
import re

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def words(text: str) -> set:
    """Lower-case latin words/numbers, so 'rs' doesn't match inside 'first' and 'hai?' matches 'hai'."""
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def has_word(text: str, vocab) -> bool:
    w = words(text)
    return any(x in w for x in vocab)


def has_phrase(text: str, phrases) -> bool:
    """Substring match: multi-word phrases and Devanagari terms."""
    t = (text or "").lower()
    return any(p in t for p in phrases)


# ------------------------------------------------------------------ language
HINGLISH_WORDS = {
    "hai", "hain", "nahi", "nhi", "kya", "kyu", "kyun", "tum", "mera", "meri", "bhai", "kr", "karo",
    "kar", "raha", "rha", "rahi", "gaya", "gayi", "hoga", "hogi", "sach", "jhooth", "jhoot", "yeh",
    "ye", "wala", "wali", "aaj", "abhi", "matlab", "sahi", "galat", "ke", "ka", "ki", "ho", "jayega",
    "jayenge", "jayegi", "diya", "kiya", "naya", "nahin", "hua", "hue", "sabko", "bhejo", "karein",
}


def detect_language(text: str) -> str:
    """'hindi' (Devanagari), 'hinglish' (Roman Hindi) or 'english'."""
    t = URL_RE.sub(" ", text or "")
    deva = sum(1 for ch in t if "ऀ" <= ch <= "ॿ")
    latin = sum(1 for ch in t if ch.isascii() and ch.isalpha())
    if deva and deva >= latin * 0.3:
        return "hindi"
    if len(words(t) & HINGLISH_WORDS) >= 1:
        return "hinglish"
    if deva:
        return "hindi"
    return "english"


# ------------------------------------------------------------------ questions
def is_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if "?" in t:
        return True
    starters = ("what", "why", "how", "when", "where", "who", "which", "is", "are", "can", "do",
                "does", "did", "should", "was", "were", "will")
    if t.split(" ", 1)[0] in starters:
        return True
    if has_word(t, {"kya", "kyu", "kyun", "kaise", "kab", "kaha", "kahan", "kaun", "kon", "kitna",
                    "bata", "bta", "batao", "samjha", "explain"}):
        return True
    return has_phrase(t, ("tell me", "bta de", "bata do", "is it true", "sach hai", "क्या"))


def question_to_claim(text: str) -> str:
    """'Is Salman Khan dead?' -> 'Salman Khan is dead.'"""
    clean = re.sub(r"\?+", "", text or "").strip()
    m = re.match(r"(?i)^(is|are)\s+(.+?)\s+(dead|alive|true|real|fake|banned|married|arrested)\.?$", clean)
    if m:
        return f"{m.group(2)} {m.group(1).lower()} {m.group(3)}."
    stripped = re.sub(r"(?i)\b(kya|kyu|kyun)\b", " ", clean)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped or clean


# ------------------------------------------------------------------ topic hints
MEDICAL_WORDS = {
    "liver", "kidney", "heart", "cancer", "blood", "bp", "diabetes", "smoking", "cigarette",
    "tobacco", "alcohol", "medicine", "fever", "infection", "disease", "health", "symptom",
    "symptoms", "cirrhosis", "vaccine", "vaccines", "covid", "cure", "virus", "ayurvedic",
    "remedy", "doctor", "hospital", "dengue", "malaria",
}


def is_medical(text: str) -> bool:
    return has_word(text, MEDICAL_WORDS) or has_phrase(text, ("blood pressure", "fatty liver", "इलाज", "बीमारी"))


LIVE_WORDS = {
    "today", "latest", "breaking", "yesterday", "tonight", "accident", "dead", "died", "death",
    "killed", "earthquake", "blast", "explosion", "flood", "arrested", "resigned", "resign", "banned",
    "ban", "announced", "launched", "trailer", "teaser", "aaj", "rip", "demonetisation",
    "demonetization", "election", "results", "strike", "curfew", "lockdown",
}
LIVE_PHRASES = ("passed away", "आज", "मौत", "निधन", "मर गया", "मर गई", "ब्रेकिंग", "बंद", "चुनाव")


def is_time_sensitive(text: str) -> bool:
    return (
        has_word(text, LIVE_WORDS)
        or has_phrase(text, LIVE_PHRASES)
        or re.search(r"\b20[2-3]\d\b", text or "") is not None
    )


# ------------------------------------------------------------------ rumour writing patterns
_FORWARD_PHRASES = (
    "forward this", "forward it", "forward to", "share this", "share it", "send this", "send to",
    "share with", "before it is deleted", "before it's deleted", "before they delete",
    "sabko bhejo", "aage bhejo", "share karo", "forward karo", "jitna ho sake", "sab group",
    "10 groups", "10 logo", "10 people", "zyada se zyada", "शेयर करें", "आगे भेजें", "फॉरवर्ड",
)
_URGENCY_PHRASES = (
    "urgent", "immediately", "turant", "jaldi", "last date", "only today", "within 24 hours",
    "तुरंत", "जल्दी",
)
_CERTAINTY_PHRASES = (
    "100% true", "100 % true", "100% sach", "confirmed news", "pakki khabar", "media won't show",
    "media will not show", "media nahi dikhayega", "they don't want you to know", "secret",
    "मीडिया नहीं दिखाएगा", "100% सच",
)
_AUTHORITY_PHRASES = (
    "doctors say", "scientists say", "nasa says", "who says", "unesco", "according to sources",
    "as per sources", "sources said", "aiims doctor",
)
_MONEY_BAIT = (
    "free recharge", "free laptop", "free scooty", "free mobile", "claim now", "click the link",
    "click here", "register now", "lucky draw", "you have won", "kyc update", "account will be blocked",
    "muft", "free me", "free mein", "link par click", "register karein", "register karo",
    "मुफ्त", "फ्री", "इस लिंक", "लिंक पर क्लिक", "रजिस्टर करें", "इनाम", "लॉटरी",
)


SIGNAL_TEXT = {
    "caps": ("Written mostly in CAPITAL LETTERS", "Zyada tar CAPITAL LETTERS mein likha hai", "ज़्यादातर बड़े (CAPITAL) अक्षरों में लिखा है"),
    "exclaim": ("Lots of exclamation marks", "Bahut saare exclamation marks (!!!)", "बहुत सारे विस्मयादिबोधक चिह्न (!!!)"),
    "forward": ("Asks you to forward or share it", "Aage forward/share karne ko bolta hai", "आगे फॉरवर्ड/शेयर करने को कहता है"),
    "urgency": ("Creates urgency", "Jaldbaazi ka dabav banata hai", "जल्दबाज़ी का दबाव बनाता है"),
    "certainty": ("Claims to be '100% true' or hidden by the media", "'100% sach' ya 'media nahi dikhayega' jaisa daava", "'100% सच' या 'मीडिया नहीं दिखाएगा' जैसा दावा"),
    "authority": ("Cites unnamed experts or sources", "Bina naam ke experts/sources ka hawala", "बिना नाम के विशेषज्ञों/स्रोतों का हवाला"),
    "bait": ("Free offer / link bait — a common scam pattern", "Free offer / link bait — aam scam pattern", "मुफ्त ऑफ़र / लिंक का लालच — आम स्कैम तरीका"),
    "emoji": ("Heavy use of emojis", "Bahut zyada emojis", "बहुत ज़्यादा इमोजी"),
}
_LANG_INDEX = {"english": 0, "hinglish": 1, "hindi": 2}


def writing_signals(text: str, lang: str = "english") -> list:
    """Classic signs of a manipulative forward. Cheap, offline, shown to the user and the AI."""
    t = (text or "").lower()
    keys = []
    letters = [c for c in text or "" if c.isalpha() and c.isascii()]
    if len(letters) >= 25 and sum(c.isupper() for c in letters) / len(letters) > 0.45:
        keys.append("caps")
    if re.search(r"[!]{3,}|(?:!\s*){4,}", text or ""):
        keys.append("exclaim")
    if has_phrase(t, _FORWARD_PHRASES):
        keys.append("forward")
    if has_phrase(t, _URGENCY_PHRASES):
        keys.append("urgency")
    if has_phrase(t, _CERTAINTY_PHRASES):
        keys.append("certainty")
    if has_phrase(t, _AUTHORITY_PHRASES):
        keys.append("authority")
    if has_phrase(t, _MONEY_BAIT):
        keys.append("bait")
    if len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text or "")) >= 8:
        keys.append("emoji")
    i = _LANG_INDEX.get(lang, 0)
    return [SIGNAL_TEXT[k][i] for k in keys]


# ------------------------------------------------------------------ known facts
_MONEY = r"(₹|rs\.?|inr|rupees?|rupaye|rupay|रुपये|रुपए|रुपया)"


def known_fact_hints(text: str) -> list:
    """Verified facts given to the AI as background (never used as a final verdict by themselves)."""
    t = (text or "").lower()
    hints = []

    if (re.search(_MONEY + r"\s*300(?![\d,])", t)
            or re.search(r"(?<![\d,])300\s*" + _MONEY, t)
            or re.search(r"(?<![\d,])300\s*(ka|ke|ki)?\s*(note|notes|नोट)", t)):
        hints.append(
            "The RBI has never issued a ₹300 banknote. Banknotes in circulation are ₹10, ₹20, ₹50, "
            "₹100, ₹200 and ₹500 (₹2000 notes were withdrawn from circulation in 2023 but remain legal "
            "tender). A claim that a ₹300 note exists or is being launched is false unless the evidence "
            "shows an official RBI announcement."
        )

    mentions_500 = re.search(r"(?<![\d,])500(?![\d,])", t) and (
        re.search(_MONEY, t) or has_word(t, {"note", "notes"}) or "नोट" in t
    )
    bans = has_word(t, {"ban", "banned", "band", "demonetisation", "demonetization", "demonetised",
                        "demonetized", "withdrawn", "withdraw", "scrapped", "invalid", "discontinued"}) \
        or has_phrase(t, ("बंद", "नोटबंदी"))
    if mentions_500 and bans:
        hints.append(
            "No official RBI / Government of India decision to ban or demonetise ₹500 notes is known. "
            "Messages claiming this are a recurring WhatsApp rumour that PIB Fact Check has debunked "
            "before. Treat it as Fake unless the evidence shows an official RBI or Government announcement."
        )

    if has_word(t, {"dead", "death", "died", "rip"}) or has_phrase(
        t, ("passed away", "निधन", "मौत", "मर गया", "मर गई", "mar gaya", "mar gayi")
    ):
        hints.append(
            "Death claims about living people must be confirmed by credible recent reports or official "
            "statements. If the evidence does not confirm it, answer Unverifiable — or Fake if the "
            "evidence shows the person is alive/active or the rumour was denied. Well-established "
            "historical deaths can be judged from common knowledge."
        )

    if has_word(t, {"smoking", "smoke", "cigarette", "cigarettes", "tobacco"}) and "liver" in t:
        hints.append(
            "Medical consensus: smoking/tobacco can increase the risk of liver damage, including "
            "progression of fatty liver disease, fibrosis and liver cancer."
        )

    if has_word(t, {"kyc", "otp", "lottery", "lucky", "prize"}) or has_phrase(t, ("you have won", "account will be blocked")):
        hints.append(
            "Banks, RBI and government departments never ask for OTPs, PINs or KYC updates through "
            "WhatsApp/SMS links. Messages promising prizes or threatening account blocking are a common "
            "phishing pattern."
        )
    return hints


# ------------------------------------------------------------------ search helpers
STOPWORDS = {
    "is", "the", "a", "an", "of", "to", "in", "on", "and", "or", "for", "that", "this", "it", "was",
    "are", "be", "has", "have", "will", "kya", "hai", "hain", "ki", "ka", "ke", "ko", "me", "mein",
    "se", "tha", "please", "check", "forward", "forwarded", "whatsapp", "viral", "message", "news",
    "true", "fake", "real", "sach", "share", "plz", "pls", "bhai", "yeh", "ye", "all", "friends",
    "dosto", "urgent", "breaking",
}


def heuristic_query(text: str, max_words: int = 10) -> str:
    t = URL_RE.sub(" ", text or "")
    tokens = [tok.strip(".,!?\"'()[]{}:;|*-_#@") for tok in t.split()]
    kept = [tok for tok in tokens if tok and tok.lower() not in STOPWORDS]
    return " ".join(kept[:max_words])


def find_urls(text: str) -> list:
    return [u.rstrip(".,);]'\"") for u in URL_RE.findall(text or "")]


def is_only_url(text: str) -> bool:
    return bool(find_urls(text)) and not URL_RE.sub("", text or "").strip()
