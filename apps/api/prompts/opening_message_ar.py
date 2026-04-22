"""Opening greeting shown as the first assistant message in every new session."""

import random

OPENING_MESSAGES: list[str] = [
    "أهلاً وسهلاً بك في مطعم الأصالة 🌙 أنا أصيل، نادلك لهذا اليوم. وش تشتهي الآن — مشاوي، كبسة، أو شي خفيف؟",
    "مرحباً بك في مطعم الأصالة ✨ عندنا اليوم أطباق شهية من المطبخ العربي الأصيل. قل لي ذوقك وأنا أقترح لك الأنسب.",
    "يا هلا ومرحبا 🌹 أنا أصيل من مطعم الأصالة. تبي أكلة حارة، دسمة، خفيفة، أو حلو؟ اطلب براحتك.",
    "أهلاً بك 🍽️ في مطعم الأصالة كل طبق له حكاية. اسألني عن أي صنف وأدلك عليه بسعره ومكوناته.",
]

SUGGESTED_PROMPTS: list[str] = [
    "أبي شي حار وغير غالي",
    "اقترح لي طبق رئيسي",
    "وش عندكم من المشويات؟",
    "أبي شي خفيف وصحي",
    "وش أطيب حلا عندكم؟",
]


def pick_opening() -> str:
    return random.choice(OPENING_MESSAGES)


def pick_suggestions(n: int = 4) -> list[str]:
    return random.sample(SUGGESTED_PROMPTS, k=min(n, len(SUGGESTED_PROMPTS)))
