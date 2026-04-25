"""
Streaming single-pass orchestrator — RAG-first, plain-text output.

The latency work in this module focuses on:
  1. lightweight request routing (chit-chat / simple lookup / full)
  2. compact history and prompt assembly to reduce prefill cost
  3. per-request profiling so we can see where time is being spent
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from apps.api.config import settings
from apps.api.models.chat import ChoiceQuestion, MealCard
from apps.api.models.session import ChatMessage
from apps.api.prompts.system_prompt_ar import SYSTEM_PROMPT
from apps.api.services import llm_client, menu_loader, rag, session_store

RouteName = Literal["chitchat", "simple", "full", "allergen", "offtopic"]

# Matches [MEAL_001] / [meal_023] etc. Case-insensitive, zero-padded numeric tail.
MEAL_TAG_RE = re.compile(r"\[\s*(MEAL_\d{1,4})\s*\]", re.IGNORECASE)

_CHITCHAT_RE = re.compile(
    r"^\s*(مرحبا|مرحباً|مرحبتين|أهلين|اهلين|هلا|هاي|هاي+|أهلا|أهلاً|السلام|سلام|"
    r"صباح|مساء|شكرا|شكراً|مشكور|تسلم|يسلمو|ممتاز|تمام|اوكي|أوكي|"
    r"ok|hi|hello|thanks?|كيفك|كيف الحال|شو أخبارك|شو اخبارك|"
    r"باي|مع السلامة|يلا باي)\b.*",
    re.IGNORECASE,
)
_FOLLOW_UP_RE = re.compile(
    r"(كم سعره|قديش سعره|سعره|سعرها|سعرهم|"
    r"والثاني|والتاني|الثاني|التاني|طيب والثاني|طيب والتاني|"
    r"هالطبق|هذا الطبق|هدا الطبق|هذا الصنف|هدا الصنف|"
    r"نفسه|نفسها|مثله|مثلو|زيه|زيو|معه|معها|اله|إله|له|"
    r"ضيفه|ضفلي|أضفه|أضفها|أضيفه|كررها|كرره|يكملها|يكمله|يكمل الطلب|يناسبها|يناسبه)",
    re.IGNORECASE,
)
_COMPANION_RE = re.compile(
    r"(يكملها|يكمله|يكمل الطلب|معها|معه|جنبها|جنبه|"
    r"يناسبها|يناسبه|شو يمشي معها|شو يمشي معه|"
    r"اقترح شي يكملها|اقترح شي يكمله|"
    r"رشح شي معها|رشح شي معه|"
    r"مشروب معها|مشروب معه|"
    r"طبق جانبي معها|طبق جانبي معه)",
    re.IGNORECASE,
)
_COMPLIMENT_RE = re.compile(
    r"^\s*(اقتراح جميل|اقتراح حلو|اقتراح ممتاز|حلو الاقتراح|عجبني الاقتراح|"
    r"جميل|حلو|ممتاز|يعطيك العافيه|يعطيك العافية)\s*[؟?!.,،]*\s*$",
    re.IGNORECASE,
)
_OPINION_RE = re.compile(
    r"(ما رأيك|شو رأيك|ايش رأيك|إيش رأيك|كيف .*?|بتنصح فيه|بتنصح فيه؟|ينفع اجربه|ينفع أجربه|"
    r"رأيك ب|رأيك في)",
    re.IGNORECASE,
)
_AFFIRMATIVE_RE = re.compile(
    r"^\s*(نعم|ايوه|أيوه|ايوا|أيوا|أجل|أكيد|اكيد|تمام|موافق|يس|yes|yep|sure|ok)\s*[؟?!.,،]*\s*$",
    re.IGNORECASE,
)
_NEGATIVE_RE = re.compile(
    r"^\s*(لا|لأ|لا شكرا|لا شكرًا|مش الآن|مو الآن|مو لازم|خلاص لا|no|nope)\s*[؟?!.,،]*\s*$",
    re.IGNORECASE,
)
_RECOMMENDATION_RE = re.compile(
    r"(اقترح|اقتراح|اقترحلي|رشّح|رشحلي|أنصح|تنصح|بتنصحني|أفضل|افضل|أطيب|"
    r"غير غالي|مش غالي|رخيص|ميزاني|ميزانية|حار|حارة|خفيف|خفيفة|أخف|اخف|"
    r"حلو|حلوى|حلويات|صحي|صحية|سكري|السكري|بدون سكر|قليل السكر|اقل سكر|أقل سكر|"
    r"أريد|اريد|أحتاج|احتاج|بحتاج|بدي|أبي|ابي|أجرب|اجرب|"
    r"أخبرني عن|خبرني عن|احكيلي عن|مناسب|يشبع|مشبّع|مشبع|شو الأفضل|شو الأحسن|إيش الأفضل)",
    re.IGNORECASE,
)
_PREFERENCE_CUE_RE = re.compile(
    r"(لحم|لحمه|دجاج|فراخ|سمك|بحري|روبيان|جمبري|"
    r"مقبلات|حلويات|حلو|مشروبات|مشروب|سلطات|سلطه|مشاوي|شاورما|"
    r"برغر|بيتزا|كبسة|مندي|أرز|رز|شوربة|شوربه|"
    r"حار|خفيف|صحي|سكري|السكري|بدون سكر|قليل السكر|طفل|اطفال|أطفال|صغير|صغيرة|مشبع|غير غالي|رخيص|ميزانية|ميزانيه|"
    r"رئيسي|طبق رئيسي|حلوى|حلا)",
    re.IGNORECASE,
)
_POPULAR_RE = re.compile(
    r"(الأكثر طلب|الاكثر طلب|الأكثر مبيع|الاكثر مبيع|مشهور|الأشهر|الاشهر|"
    r"top seller|best seller|best-seller)",
    re.IGNORECASE,
)
_FULL_ROUTE_RE = re.compile(
    r"(اقترح|اقتراح|اقترحلي|رشّح|رشحلي|أنصح|تنصح|بتنصحني|أفضل|افضل|أطيب|"
    r"غير غالي|مش غالي|رخيص|ميزاني|ميزانية|حار|حارة|خفيف|خفيفة|أخف|اخف|"
    r"بدون|حساسية|سكري|السكري|بدون سكر|قليل السكر|أحتاج|احتاج|طفل|اطفال|أطفال|للعيلة|للعائلة|الأكتر|الأكثر|اقل|أقل|أكثر|أكتر|"
    r"مناسب|يشبع|مشبّع|مشبع|ماذا|إيش الأفضل|شو الأفضل|شو الأحسن)",
    re.IGNORECASE,
)
_ALLERGEN_RE = re.compile(
    r"(مكسرات|جوز|لوز|كاجو|فستق|حليب|لبن|لاكتوز|جبن|جبنة|"
    r"جلوتين|قمح|طحين|بيض|سمسم|طحينة|فول|صويا|بصل|ثوم|"
    r"حار|حارة|بهارات|سمك|جمبري|روبيان|قشريات|حساسية|"
    r"نباتي|نباتية|vegan|vegetarian|"
    r"شو فيه|شو بالـ|شو في|فيه شو|فيها شو|ايش فيه|إيش فيه|"
    r"مكوّنات|مكونات|مكوناته|مكوّناته)",
    re.IGNORECASE,
)
# Off-topic / facility questions the waiter shouldn't food-ground.
_OFFTOPIC_RE = re.compile(
    r"(واي فاي|wifi|wi-?fi|كلمة السر|باسورد|password|"
    r"الحمام|التواليت|الدفع|فيزا|بطاقة|كاش|كاشير|"
    r"ساعات العمل|متى تفتحو|متى تسكرو|مفتوحين|سكرتو|"
    r"موقف سيارات|parking|الموقف|التوصيل|ديليفري|delivery|"
    r"فرع|فروع|العنوان|الموقع|تلفون|رقمكم|احجز|حجز|reservation)",
    re.IGNORECASE,
)
_SIMPLE_LOOKUP_RE = re.compile(
    r"(شو عندكم|إيش عندكم|ايش عندكم|وش عندكم|عندكم|في عندكم|فيه|"
    r"هل يوجد|بدي|بدنا|ابغى|أبغى|ابي|أبي|"
    r"عندكم من|المشاوي|المقبلات|الحلويات|المشروبات|السلطات)",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")
# Arabic diacritics (tashkeel) — stripped so "مندي" matches "مَنْدي" etc.
_TASHKEEL_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")


def _normalize_arabic(text: str) -> str:
    """Fold variants so lexical match is robust across typing styles."""
    text = _TASHKEEL_RE.sub("", text)
    # Alef family → plain alef
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    # Ya / alef maqsura
    text = text.replace("ى", "ي")
    # Ta marbuta / ha — fold both directions so either query/menu side matches
    text = text.replace("ة", "ه")
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


# Tiny Arabic stopword set for token-overlap fallback. Anything purely
# functional (question markers, prepositions, determiners) should not count
# as a name token.
_AR_STOPWORDS = frozenset(
    [
        "عن", "من", "الى", "إلى", "في", "على", "مع", "او", "أو", "و", "ف",
        "شو", "وش", "كيف", "ايش", "إيش", "ما", "هل", "هاي", "هذا", "هذه",
        "هاد", "هادي", "بدي", "بدك", "احكيلي", "أجرب", "اجرب", "اجرّب",
        "أجرّب", "بتنصحني", "اقترحلي", "رشحلي", "رشّحلي", "اليوم", "عندكم",
        "ال", "لي", "إلي", "الي",
    ]
)

_SAFETY_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "مكسرات": ("مكسرات", "جوز", "لوز", "كاجو", "فستق"),
    "ألبان": ("حليب", "لبن", "لاكتوز", "جبن", "جبنة", "ألبان"),
    "جلوتين": ("جلوتين", "قمح", "طحين", "برغل"),
    "بيض": ("بيض",),
    "سمسم": ("سمسم", "طحينة"),
    "بصل": ("بصل",),
    "ثوم": ("ثوم",),
    "فول": ("فول",),
    "صويا": ("صويا",),
    "سمك": ("سمك",),
    "قشريات": ("جمبري", "روبيان", "قشريات"),
    "حار": ("حار", "حارة", "بهارات"),
}

_PROMPT_LEAK_PREFIXES = (
    "القائمة (",
    "معرفات مسموحة",
    "سياق متابعة:",
    "تعليمات:",
    "سلة:",
    "سؤال:",
)


def _token_stem(token: str) -> str:
    """Strip leading ال and normalize so 'السمبوسة' ~ 'سمبوسة'."""
    if token.startswith("ال") and len(token) > 3:
        token = token[2:]
    return token.strip("؟?!.,،:؛")


def _content_tokens(text: str) -> list[str]:
    return [
        stem
        for raw in _normalize_arabic(text).split()
        for stem in [_token_stem(raw)]
        if stem and stem not in _AR_STOPWORDS and len(stem) >= 3
    ]


@dataclass(frozen=True)
class _MealNameEntry:
    meal_id: str
    normalized: str
    tokens: frozenset[str]  # content tokens of the meal name for overlap match


_NAME_INDEX_CACHE: list[_MealNameEntry] | None = None
_DISTINCTIVE_TOKENS_CACHE: frozenset[str] | None = None


def _get_name_index() -> list[_MealNameEntry]:
    """Cached [(meal_id, normalized_name_ar, tokens)], longest first for greedy match."""
    global _NAME_INDEX_CACHE
    if _NAME_INDEX_CACHE is None:
        menu = menu_loader.load_menu()
        entries = [
            _MealNameEntry(
                meal_id=m.id,
                normalized=_normalize_arabic(m.name_ar),
                tokens=frozenset(_content_tokens(m.name_ar)),
            )
            for m in menu.meals
            if m.name_ar.strip()
        ]
        # Sort longest-name-first so "مندي لحم" beats "مندي" on substring scan.
        entries.sort(key=lambda e: len(e.normalized), reverse=True)
        _NAME_INDEX_CACHE = entries
    return _NAME_INDEX_CACHE


def _get_distinctive_tokens() -> frozenset[str]:
    """
    Tokens that appear in at most N menu names — used to gate the token-overlap
    fallback so shared category words like "لحم" / "دجاج" alone can't trigger
    a lexical match. A true dish stem ("مندي", "كنافة", "سمبوسة") is usually
    unique or near-unique across the menu.
    """
    global _DISTINCTIVE_TOKENS_CACHE
    if _DISTINCTIVE_TOKENS_CACHE is None:
        df: dict[str, int] = {}
        for entry in _get_name_index():
            for tok in entry.tokens:
                df[tok] = df.get(tok, 0) + 1
        _DISTINCTIVE_TOKENS_CACHE = frozenset(t for t, c in df.items() if c <= 2)
    return _DISTINCTIVE_TOKENS_CACHE


def _meal_to_rag_payload(meal) -> dict[str, Any]:
    """Shape a Meal to match the Qdrant payload dicts returned by rag.search_menu."""
    return {
        "score": 1.0,
        "id": meal.id,
        "name_ar": meal.name_ar,
        "price": meal.price,
        "currency": meal.currency,
        "category": meal.category,
        "spice_level": meal.spice_level,
        "calories": meal.calories,
        "featured": meal.featured,
        "recommendation_rank": meal.recommendation_rank,
        "sales_pitch_ar": meal.sales_pitch_ar,
        "tags": meal.tags,
        "ingredients": meal.ingredients,
        "allergens": meal.allergens,
        "description_ar": meal.description_ar,
    }


def _lexical_meal_hits(query: str) -> list[dict[str, Any]]:
    """
    Return menu items whose normalized name_ar is a substring of the normalized
    query. When the guest literally types a dish name, this wins over semantic
    similarity (which otherwise confuses e.g. "مندي لحم" → "سمبوسة لحم").
    """
    norm_query = _normalize_arabic(query)
    if not norm_query:
        return []
    query_tokens = frozenset(_content_tokens(query))

    hits: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Pass 1 — full-name substring match (strongest signal).
    for entry in _get_name_index():
        if len(entry.normalized) < 3:
            continue
        if entry.normalized in norm_query and entry.meal_id not in seen:
            meal = menu_loader.get_meal_by_id(entry.meal_id)
            if meal is not None:
                hits.append(_meal_to_rag_payload(meal))
                seen.add(entry.meal_id)

    # Pass 2 — token-overlap fallback. Only runs when pass-1 found nothing,
    # otherwise a generic shared token like "لحم" would drag in every meat
    # dish alongside the exact-name match. Triggers when the guest typed a
    # distinctive stem (e.g. "السمبوسة" → "سمبوسة") but not the full menu
    # name. Requires >=1 token overlap AND that overlap is at least half of
    # the menu name's tokens.
    if not hits and query_tokens:
        distinctive = _get_distinctive_tokens()
        for entry in _get_name_index():
            if entry.meal_id in seen or not entry.tokens:
                continue
            overlap = entry.tokens & query_tokens
            if not overlap:
                continue
            # Require the overlap to include at least one distinctive token —
            # stops generic category words ("لحم", "دجاج") from mass-matching.
            if not (overlap & distinctive):
                continue
            if len(overlap) / len(entry.tokens) >= 0.5:
                meal = menu_loader.get_meal_by_id(entry.meal_id)
                if meal is not None:
                    payload = _meal_to_rag_payload(meal)
                    # Slightly lower score for fuzzy match so true substring
                    # hits still rank first when both happen.
                    payload["score"] = 0.9
                    hits.append(payload)
                    seen.add(entry.meal_id)

    return hits


@dataclass
class TurnBuildResult:
    messages: list[dict[str, str]]
    route: RouteName
    rag_used: bool
    history_chars: int
    prompt_chars: int
    timings: dict[str, Any]
    model_name: str
    rag_results: list[dict[str, Any]]
    direct_reply: str | None = None
    guided_questions: list[ChoiceQuestion] | None = None
    guided_submit_label: str | None = None


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _merge_context_hint(user_message: str, context_hint: str | None) -> str:
    if not context_hint:
        return _normalize_text(user_message)
    merged = " ".join(part for part in [user_message, context_hint] if part.strip())
    return _normalize_text(merged)


def _is_chitchat(msg: str) -> bool:
    if _FOLLOW_UP_RE.search(msg) or _AFFIRMATIVE_RE.match(msg) or _NEGATIVE_RE.match(msg):
        return False
    return len(msg.strip()) <= 20 and bool(_CHITCHAT_RE.match(msg.strip()))


def _detect_route(msg: str) -> RouteName:
    normalized = _normalize_text(msg)
    if _is_chitchat(normalized):
        return "chitchat"
    # Off-topic catches (wifi, hours, directions) before anything food-grounded,
    # so we never hand those to RAG + the small model.
    if _OFFTOPIC_RE.search(normalized):
        return "offtopic"
    # Allergen/ingredient questions must route BEFORE simple, because simple
    # mode strips ingredients from RAG context and can short-circuit into a
    # recommendation — unsafe for allergy phrasing like "فيه مكسرات؟".
    if _ALLERGEN_RE.search(normalized):
        return "allergen"
    if len(normalized) > 45 or _FULL_ROUTE_RE.search(normalized):
        return "full"
    if _SIMPLE_LOOKUP_RE.search(normalized):
        return "simple"
    return "full"


def _history_char_len(history: list[ChatMessage]) -> int:
    return sum(len(msg.content) for msg in history)


def _compact_history(history: list[ChatMessage]) -> list[ChatMessage]:
    budget = max(settings.chat_history_char_budget, 0)
    if budget == 0:
        return []

    kept: list[ChatMessage] = []
    used = 0
    for msg in reversed(history):
        content = _normalize_text(msg.content)
        limit = 120 if msg.role == "assistant" else 160
        if len(content) > limit:
            content = content[: limit - 1].rstrip() + "…"
        remaining = budget - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            if not kept and remaining > 1:
                content = content[: remaining - 1].rstrip() + "…"
            else:
                break
        extra = len(content)
        kept.append(ChatMessage(role=msg.role, content=content))
        used += extra
    kept.reverse()
    return kept


def _format_rag_context(
    results: list[dict[str, Any]],
    *,
    compact: bool,
    include_ingredients: bool = False,
) -> str:
    if not results:
        return "ما في."
    parts: list[str] = []
    for result in results:
        featured_note = " مميز" if result.get("featured") else ""
        pitch = f" {result['sales_pitch_ar']}" if result.get("sales_pitch_ar") and not compact else ""
        if compact and not include_ingredients:
            parts.append(
                f"[{result['id']}] {result['name_ar']} {int(result['price'])}ر{featured_note}"
            )
            continue

        base = (
            f"[{result['id']}] {result['name_ar']} {int(result['price'])}ر "
            f"{result['category']} حار{result['spice_level']}{featured_note}{pitch}"
        )
        if include_ingredients:
            ingredients = result.get("ingredients") or []
            if isinstance(ingredients, list):
                ing_str = "، ".join(str(x) for x in ingredients)
            else:
                ing_str = str(ingredients)
            allergens = result.get("allergens") or []
            if isinstance(allergens, list):
                alg_str = "، ".join(str(x) for x in allergens)
            else:
                alg_str = str(allergens)
            extras: list[str] = []
            if ing_str:
                extras.append(f"مكونات: {ing_str}")
            if alg_str:
                extras.append(f"مسببات حساسية: {alg_str}")
            if extras:
                base = base + " | " + " | ".join(extras)
        parts.append(base)
    return " || ".join(parts) if include_ingredients else " | ".join(parts)


def _format_cart(cart) -> str:
    if not cart.items:
        return "فارغة."
    lines = [
        f"- {i.name_ar} × {i.quantity} = {i.unit_price * i.quantity:.0f} ريال"
        for i in cart.items
    ]
    lines.append(f"الإجمالي: {cart.total:.0f} ريال")
    return "\n".join(lines)


def _select_model_for_route(route: RouteName) -> str:
    if route == "simple" and settings.llm_simple_model_name:
        return settings.llm_simple_model_name
    return settings.llm_model_name


def _max_tokens_for_route(route: RouteName) -> int:
    if route in {"chitchat", "offtopic"}:
        return min(settings.llm_max_tokens, 24)
    if route == "simple":
        return min(settings.llm_max_tokens, 48)
    if route == "allergen":
        # Needs room to enumerate ingredients from RAG context.
        return max(settings.llm_max_tokens, 96)
    return settings.llm_max_tokens


def _build_offtopic_reply(user_message: str) -> str:
    """Scoped deflection for non-menu questions — keeps the waiter in-role."""
    normalized = _normalize_text(user_message).lower()
    if any(w in normalized for w in ["واي فاي", "wifi", "wi-fi", "كلمة السر", "باسورد", "password"]):
        return "هاي المعلومة بتقدر تسأل عنها الكاشير. أنا هون لأساعدك بالمنيو والترشيحات."
    if any(w in normalized for w in ["ساعات", "مفتوح", "تفتح", "تسكر"]):
        return "مواعيد الفرع بتلاقيها عند الاستقبال. أنا معك للمنيو — قلّي ذوقك وبرشّحلك."
    if any(w in normalized for w in ["حجز", "احجز", "reservation", "توصيل", "delivery", "ديليفري"]):
        return "هاد بيتولّاه الكاشير. بس إذا بدك ترشيح أكلة من عنا، أنا جاهز."
    return "أنا نادل المطعم، بساعدك بس بالمنيو والترشيحات. قلّي شو بتحب تاكل اليوم وأنا برشّحلك."


def _build_no_match_reply() -> str:
    """Used when RAG returns nothing above the score floor on a food-grounded route."""
    return (
        "ما لقيت إشي بالقائمة يطابق طلبك بالزبط. بتقدر توضّحلي أكتر — "
        "بتحب مشاوي، مقبلات، حلو، ولا إشي خفيف؟"
    )


def _is_sugary_item(item: dict[str, Any]) -> bool:
    category = str(item.get("category") or "")
    tags = " ".join(item.get("tags") or [])
    description = str(item.get("description_ar") or "")
    name = str(item.get("name_ar") or "")
    combined = _normalize_arabic(f"{name} {category} {tags} {description}")

    if "حلويات" in category:
        return True
    if any(
        word in combined
        for word in [
            "حلو",
            "حلوي",
            "كنافه",
            "بسبوسه",
            "مهلبيه",
            "لقيمات",
            "قطايف",
            "عيش السرايا",
            "ام علي",
            "عسل",
            "شيره",
            "كريمي",
        ]
    ):
        return True
    if "مشروبات" in category and any(
        word in combined for word in ["عصير", "كرك", "عرق سوس"]
    ):
        return True
    return False


def _build_chitchat_reply(user_message: str) -> str:
    normalized = _normalize_text(user_message).lower()
    if any(word in normalized for word in ["شكرا", "شكراً", "مشكور", "تسلم", "يسلمو", "thanks"]):
        return "العفو، هاد من ذوقك. إذا بدك أكمّلك الترشيح أو رتّبلك الطلب أنا جاهز."
    if any(word in normalized for word in ["باي", "مع السلامة", "يلا باي"]):
        return "مع السلامة، بننتظرك مرّة تانية وبشرّفني أخدمك."
    if any(word in normalized for word in ["كيف", "كيفك", "اخبارك", "أخبارك"]):
        return "تمام الحمدلله، دامك بخير. قلّي بس شو بتميل إله، وأنا برشّحلك طبق بيضبط مزاجك."
    return "أهلين فيك، يا هلا وسهلا. قلّي ذوقك، وأنا برشّحلك طبق بيليق فيك اليوم."


def _looks_like_plural_lookup(user_message: str) -> bool:
    normalized = _normalize_text(user_message)
    return any(
        phrase in normalized
        for phrase in [
            "شو عندكم",
            "إيش عندكم",
            "ايش عندكم",
            "وش عندكم",
            "عندكم من",
            "في عندكم",
            "المشاوي",
            "المقبلات",
            "الحلويات",
            "المشروبات",
            "السلطات",
        ]
    )


def _is_recommendation_request(user_message: str) -> bool:
    normalized = _normalize_text(user_message)
    return bool(_RECOMMENDATION_RE.search(normalized))


def _is_broad_recommendation_request(user_message: str) -> bool:
    normalized = _normalize_text(user_message)
    if not _is_recommendation_request(normalized):
        return False
    if _PREFERENCE_CUE_RE.search(normalized):
        return False
    if _lexical_meal_hits(normalized):
        return False
    return True


def _build_broad_recommendation_reply() -> str:
    return "أكيد، اختر من هالخيارات السريعة وأنا أبني لك ترشيحًا أدق."


def _build_broad_recommendation_questions() -> list[ChoiceQuestion]:
    return [
        ChoiceQuestion(
            id="protein",
            label="شو ذوقك أكثر؟",
            options=[
                {"id": "meat", "label": "لحم", "value": "لحم"},
                {"id": "chicken", "label": "دجاج", "value": "دجاج"},
                {"id": "seafood", "label": "بحري", "value": "بحري"},
                {"id": "open", "label": "ما عندي مانع", "value": "أي نوع"},
            ],
        ),
        ChoiceQuestion(
            id="course",
            label="بدك أي نوع طلب؟",
            options=[
                {"id": "main", "label": "طبق رئيسي", "value": "طبق رئيسي"},
                {"id": "appetizer", "label": "مقبلات", "value": "مقبلات"},
                {"id": "dessert", "label": "حلويات", "value": "حلويات"},
                {"id": "drink", "label": "مشروبات", "value": "مشروبات"},
            ],
        ),
        ChoiceQuestion(
            id="style",
            label="كيف تحبه؟",
            options=[
                {"id": "light", "label": "خفيف", "value": "خفيف"},
                {"id": "filling", "label": "مشبع", "value": "مشبع"},
                {"id": "spicy", "label": "حار", "value": "حار"},
                {"id": "healthy", "label": "صحي", "value": "صحي"},
            ],
        ),
        ChoiceQuestion(
            id="budget",
            label="وبالنسبة للسعر؟",
            options=[
                {"id": "budget", "label": "اقتصادي", "value": "اقتصادي"},
                {"id": "normal", "label": "عادي", "value": "سعر عادي"},
                {"id": "premium", "label": "مميز", "value": "مميز"},
            ],
        ),
    ]


def _popular_seed_hits(*, limit: int = 3) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for meal in menu_loader.load_menu().meals:
        payload = _meal_to_rag_payload(meal)
        tags = " ".join(meal.tags)
        popularity = 0
        if "الأكثر طلب" in tags or "الاكثر طلب" in tags:
            popularity += 5
        if meal.featured:
            popularity += 4
        popularity += int(meal.recommendation_rank or 0) * 2
        if popularity <= 0:
            continue
        payload["popularity_score"] = popularity
        ranked.append(payload)
    ranked.sort(
        key=lambda item: (
            int(item.get("popularity_score", 0)),
            int(item.get("featured", False)),
            int(item.get("recommendation_rank", 0)),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _build_popular_reply() -> str:
    top = _popular_seed_hits(limit=3)
    if not top:
        return "عندي أكثر من خيار محبوب، وإذا تحب أحدد لك الأفضل حسب ذوقك قلّي: لحم ولا دجاج، وطبق رئيسي ولا حلو."
    first = top[0]
    if len(top) > 1:
        second = top[1]
        return (
            f"من الأكثر طلبًا عنا {first['name_ar']} [{first['id']}] بـ {int(first['price'])} ريال، "
            f"وكمان {second['name_ar']} [{second['id']}] بـ {int(second['price'])} ريال. "
            "إذا تحب، أرتب لك الترشيح حسب ذوقك: رئيسي، مشاوي، أو حلو."
        )
    return (
        f"من الأكثر طلبًا عنا {first['name_ar']} [{first['id']}] بـ {int(first['price'])} ريال. "
        "إذا تحب، أقدر أيضًا أرشّح لك بديلًا قريبًا حسب ذوقك."
    )


def _asked_safety_terms(user_message: str) -> list[str]:
    normalized = _normalize_arabic(user_message)
    asked: list[str] = []
    for label, aliases in _SAFETY_TERM_ALIASES.items():
        if any(_normalize_arabic(alias) in normalized for alias in aliases):
            asked.append(label)
    return asked


def _item_matches_safety_term(item: dict[str, Any], label: str) -> bool:
    aliases = _SAFETY_TERM_ALIASES.get(label, ())
    haystack_parts: list[str] = []
    for field in ["ingredients", "allergens", "description_ar", "tags", "name_ar"]:
        value = item.get(field)
        if isinstance(value, list):
            haystack_parts.extend(str(v) for v in value)
        elif value:
            haystack_parts.append(str(value))
    haystack = _normalize_arabic(" ".join(haystack_parts))
    return any(_normalize_arabic(alias) in haystack for alias in aliases)


def _build_allergen_direct_reply(user_message: str, rag_results: list[dict[str, Any]]) -> str | None:
    if not rag_results:
        return None

    asked_terms = _asked_safety_terms(user_message)
    named_hits = _lexical_meal_hits(user_message)
    target_items = named_hits[:1] or rag_results[:1]

    if not asked_terms:
        item = target_items[0]
        ingredients = item.get("ingredients") or []
        allergens = item.get("allergens") or []
        ing_text = "، ".join(str(x) for x in ingredients) if isinstance(ingredients, list) else str(ingredients)
        allergen_text = "، ".join(str(x) for x in allergens) if isinstance(allergens, list) else str(allergens)
        if not ing_text and not allergen_text:
            return (
                f"ما عندي تفاصيل دقيقة كفاية عن {item['name_ar']} [{item['id']}]. "
                "إذا بدك أتأكد لك أكثر، أراجع المطبخ أو الكاشير."
            )
        parts = [f"{item['name_ar']} [{item['id']}]"]
        if ing_text:
            parts.append(f"مكوناته: {ing_text}")
        if allergen_text:
            parts.append(f"ومسببات الحساسية فيه: {allergen_text}")
        return "، ".join(parts) + "."

    # If the guest asked an allergy question without naming the dish and we
    # don't have a confident single target, ask a safe clarifier instead of
    # guessing what dish they meant.
    if not named_hits and len(rag_results) > 1 and not any(token in _normalize_arabic(user_message) for token in ["هذا", "هدا", "هالطبق", "هالصنف"]):
        joined = " أو ".join(term for term in asked_terms[:2])
        return (
            f"تقصد أي طبق بالضبط؟ إذا تذكر اسمه أجاوبك بدقة إذا فيه {joined} أو لا."
        )

    replies: list[str] = []
    for item in target_items[:2]:
        present = [term for term in asked_terms if _item_matches_safety_term(item, term)]
        asked_text = " و".join(asked_terms[:2])
        if present:
            found = " و".join(present)
            replies.append(
                f"{item['name_ar']} [{item['id']}] فيه {found} حسب بيانات المنيو"
            )
        else:
            replies.append(
                f"{item['name_ar']} [{item['id']}] ما فيه {asked_text} حسب البيانات الموجودة"
            )
    return "، ".join(replies) + "."


def _recent_query_context(history: list[ChatMessage]) -> str:
    snippets: list[str] = []
    used = 0
    for msg in reversed(history):
        if msg.role not in {"user", "assistant"}:
            continue
        content = _normalize_text(msg.content)
        if not content:
            continue
        remaining = 220 - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            if not snippets and remaining > 1:
                content = content[: remaining - 1].rstrip() + "…"
            else:
                break
        snippets.append(content)
        used += len(content)
        if len(snippets) >= 2:
            break
    snippets.reverse()
    return " ".join(snippets)


def _recent_referenced_meal(history: list[ChatMessage]) -> dict[str, Any] | None:
    for msg in reversed(history):
        if msg.role not in {"user", "assistant"}:
            continue
        hits = _lexical_meal_hits(msg.content)
        if hits:
            return hits[0]
    return None


def _build_rag_query(user_message: str, raw_history: list[ChatMessage]) -> str:
    normalized = _normalize_text(user_message)
    if not (
        _FOLLOW_UP_RE.search(normalized)
        or _AFFIRMATIVE_RE.match(normalized)
        or _NEGATIVE_RE.match(normalized)
    ):
        return normalized
    history_context = _recent_query_context(raw_history)
    if not history_context:
        return normalized
    return f"{history_context} {normalized}"


def _looks_like_named_dish_request(user_message: str) -> bool:
    normalized = _normalize_text(user_message)
    return any(
        phrase in normalized
        for phrase in [
            "أخبرني عن",
            "خبرني عن",
            "احكيلي عن",
            "أريد أن أجرب",
            "اريد أن اجرب",
            "أجرب",
            "اجرب",
            "بدي اجرب",
            "أبي أجرب",
            "ابي اجرب",
        ]
    )


def _looks_like_dish_opinion_request(user_message: str) -> bool:
    return bool(_OPINION_RE.search(_normalize_text(user_message)))


def _is_companion_request(user_message: str) -> bool:
    return bool(_COMPANION_RE.search(_normalize_text(user_message)))


def _is_contextual_compliment(user_message: str) -> bool:
    return bool(_COMPLIMENT_RE.match(_normalize_text(user_message)))


def _looks_like_meal_selection(user_message: str) -> bool:
    normalized = _normalize_text(user_message)
    return any(
        phrase in normalized
        for phrase in [
            "اخترت",
            "أخترت",
            "اختار",
            "أختار",
            "بدي",
            "أبي",
            "ابي",
            "أريد",
            "اريد",
            "هات",
            "جيب",
            "أطلب",
            "اطلب",
            "طلبت",
            "خذ",
            "خد",
        ]
    )


def _extract_preferences(user_message: str) -> dict[str, Any]:
    normalized = _normalize_arabic(user_message)
    prefs: dict[str, Any] = {
        "protein": None,
        "category": None,
        "spicy": False,
        "light": False,
        "healthy": False,
        "filling": False,
        "budget": False,
        "premium": False,
        "low_sugar": False,
        "diabetic": False,
        "child_friendly": False,
    }

    if "لحم" in normalized:
        prefs["protein"] = "لحم"
    elif "دجاج" in normalized:
        prefs["protein"] = "دجاج"
    elif any(word in normalized for word in ["بحري", "سمك", "روبيان", "جمبري"]):
        prefs["protein"] = "بحري"

    if any(word in normalized for word in ["مقبلات", "مقبله"]):
        prefs["category"] = "مقبلات"
    elif any(word in normalized for word in ["حلويات", "حلو", "حلا", "حلوى"]):
        prefs["category"] = "حلويات"
    elif any(word in normalized for word in ["مشروبات", "مشروب"]):
        prefs["category"] = "مشروبات"
    elif any(word in normalized for word in ["سلطات", "سلطه", "شوربه", "شوربة"]):
        prefs["category"] = "خفيف"
    elif any(word in normalized for word in ["طبق رئيسي", "رئيسي", "وجبه", "وجبة"]):
        prefs["category"] = "أطباق رئيسية"

    prefs["spicy"] = any(word in normalized for word in ["حار", "حاره", "حارة"])
    prefs["light"] = any(word in normalized for word in ["خفيف", "خفيفه", "خفيفة"])
    prefs["healthy"] = any(word in normalized for word in ["صحي", "صحية", "healthy"])
    prefs["filling"] = any(word in normalized for word in ["مشبع", "مشبعه", "مشبعة", "يشبع"])
    prefs["budget"] = any(
        word in normalized
        for word in ["غير غالي", "مش غالي", "غير مكلف", "رخيص", "اقتصادي", "ميزانيه", "ميزانية"]
    )
    prefs["premium"] = any(word in normalized for word in ["مميز", "فاخر", "premium"])
    prefs["diabetic"] = any(
        word in normalized for word in ["سكري", "السكري", "مريض سكر", "diabetic", "diabetes"]
    )
    prefs["low_sugar"] = prefs["diabetic"] or any(
        phrase in normalized
        for phrase in ["بدون سكر", "بلا سكر", "قليل السكر", "اقل سكر", "أقل سكر", "من دون سكر"]
    )
    prefs["child_friendly"] = any(
        word in normalized
        for word in ["طفل", "طفله", "طفلة", "اطفال", "أطفال", "صغير", "صغيره", "صغيرة"]
    )
    return prefs


def _preference_seed_hits(user_message: str, *, limit: int = 6) -> list[dict[str, Any]]:
    prefs = _extract_preferences(user_message)
    has_signal = any(
        [
            prefs["protein"],
            prefs["category"],
            prefs["spicy"],
            prefs["light"],
            prefs["healthy"],
            prefs["filling"],
            prefs["budget"],
            prefs["premium"],
            prefs["low_sugar"],
            prefs["diabetic"],
            prefs["child_friendly"],
        ]
    )
    if not has_signal:
        return []

    seeded: list[dict[str, Any]] = []
    for meal in menu_loader.load_menu().meals:
        payload = _meal_to_rag_payload(meal)
        pref_score, _, _, _ = _meal_matches_preferences(payload, prefs)
        if pref_score <= 0:
            continue
        payload["score"] = round(0.75 + min(pref_score, 10) * 0.02, 3)
        payload["pref_score"] = pref_score
        seeded.append(payload)

    seeded.sort(
        key=lambda item: (
            int(item.get("pref_score", 0)),
            int(item.get("featured", False)),
            int(item.get("recommendation_rank", 0)),
            -float(item.get("price", 0)),
        ),
        reverse=True,
    )
    return seeded[:limit]


def _meal_matches_preferences(item: dict[str, Any], prefs: dict[str, Any]) -> tuple[int, float, int, int]:
    score = 0
    tags = " ".join(item.get("tags") or [])
    description = str(item.get("description_ar") or "")
    category = str(item.get("category") or "")
    name = str(item.get("name_ar") or "")
    combined = _normalize_arabic(f"{name} {category} {tags} {description}")
    price = float(item.get("price", 0))
    spice = int(item.get("spice_level", 0))
    calories = int(item.get("calories", 0))

    if prefs["protein"] and prefs["protein"] in combined:
        score += 4
    if prefs["category"]:
        if prefs["category"] == "خفيف":
            if any(word in combined for word in ["سلطه", "سلطات", "شوربه", "شوربة", "خفيف", "صحي"]):
                score += 3
        elif prefs["category"] in category:
            score += 4
    elif category == "مشروبات":
        # For general food recommendations, don't let cheap/light drinks outrank
        # actual dishes unless the guest explicitly asked for a drink.
        score -= 2
    if prefs["spicy"]:
        score += min(spice, 4) * 2
        if "حار" in combined:
            score += 2
    if prefs["light"]:
        if any(word in combined for word in ["خفيف", "صحي", "مشوي"]):
            score += 3
        score += max(0, 3 - calories // 250)
    if prefs["healthy"]:
        if any(word in combined for word in ["صحي", "مشوي", "سلطه", "سلطات", "خفيف"]):
            score += 4
        score += max(0, 3 - calories // 250)
    if prefs["filling"]:
        if any(word in combined for word in ["مشبع", "رز", "أرز", "لحم", "دجاج"]):
            score += 3
        score += min(3, calories // 250)
    if prefs["budget"]:
        if price <= 30:
            score += 5
        elif price <= 40:
            score += 3
    if prefs["premium"]:
        if price >= 45:
            score += 3
    if prefs["low_sugar"]:
        if _is_sugary_item(item):
            score -= 10
        if category == "مشروبات":
            score -= 4
        if any(word in combined for word in ["صحي", "خفيف", "مشوي", "سلطه", "سلطات", "شوربه", "شوربة", "طازج", "بحري"]):
            score += 5
        if calories and calories <= 220:
            score += 4
        elif calories and calories <= 400:
            score += 3
        elif calories and calories <= 550:
            score += 1
        elif calories >= 700:
            score -= 3
    if prefs["diabetic"]:
        if any(word in combined for word in ["مقلي", "كريمي", "عسل"]):
            score -= 3
    if prefs["child_friendly"]:
        if "حلويات" in category:
            score -= 6
        if category == "مشروبات":
            score -= 4
        if category in {"أطباق رئيسية", "مقبلات"}:
            score += 3
        if spice > 1 or "حار" in combined:
            score -= 4
        if any(word in combined for word in ["دجاج", "شوربه", "شوربة", "خفيف", "أبيض", "صحي", "سهل"]):
            score += 5
        if calories and calories <= 650:
            score += 2
        if price and price <= 45:
            score += 1

    return (
        score,
        float(item.get("score", 0)),
        int(item.get("recommendation_rank", 0)),
        int(item.get("featured", False)),
    )


def _build_simple_direct_reply(user_message: str, rag_results: list[dict[str, Any]]) -> str | None:
    if not rag_results:
        return None
    prefs = _extract_preferences(user_message)
    ranked = sorted(rag_results, key=lambda item: _meal_matches_preferences(item, prefs), reverse=True)

    if (_looks_like_plural_lookup(user_message) or _is_recommendation_request(user_message)) and len(ranked) > 1:
        top = ranked[:2]
        parts = []
        for item in top:
            reason = item.get("sales_pitch_ar")
            if not reason:
                if prefs["low_sugar"]:
                    reason = "أميل له إذا بدك خيارًا أخف وأبعد عن الحلويات"
                elif prefs["diabetic"]:
                    reason = "أميل له إذا بدك خيارًا أهدأ وأخف على الأكل"
                elif prefs["child_friendly"]:
                    reason = "طعمه أهدأ وخياره مناسب إذا بدك وجبة مريحة وغير حارة"
                if prefs["spicy"] and int(item.get("spice_level", 0)) > 0:
                    reason = "طعمه فيه حرارة لطيفة وسعره مناسب"
                elif prefs["healthy"] or prefs["light"]:
                    reason = "خفيف على المعدة ومناسب إذا بدك خيارًا متوازنًا"
                elif prefs["budget"]:
                    reason = "سعره مناسب ويعطيك قيمة ممتازة"
                else:
                    reason = "من الخيارات يلي بيحبها كتير من الضيوف"
            parts.append(
                f"{item['name_ar']} [{item['id']}] بـ {int(item['price'])} ريال، {reason}"
            )
        if prefs["low_sugar"]:
            return (
                f"إذا بدك خيارًا أخف وأقل سكرًا، أميل أولًا إلى {parts[0]}. "
                f"وإذا تحب بديل ثاني، عندك كمان {parts[1]}. وبفضّل أبعدك عن الحلويات في هالحالة."
            )
        if prefs["child_friendly"]:
            return (
                f"إذا بدك وجبة أنسب لطفل، أميل أولًا إلى {parts[0]}. "
                f"وإذا تحب بديل ثاني، عندك كمان {parts[1]}."
            )
        return (
            f"يا أهلا، أول ترشيح إلك هو {parts[0]}. "
            f"وإذا بدك بديل تاني، عنا كمان {parts[1]}."
        )

    top = ranked[0]
    pitch = top.get("sales_pitch_ar")
    if not pitch:
        if prefs["low_sugar"]:
            pitch = "أميل له إذا بدك خيارًا أخف وأقل سكرًا من الحلويات والمشروبات الحلوة"
        elif prefs["child_friendly"]:
            pitch = "أميل له إذا بدك وجبة خفيفة نسبيًا وطعمها أهدأ من الخيارات الحارة"
        elif prefs["spicy"] and prefs["budget"]:
            pitch = "طعمه حار بشكل واضح وسعره مناسب"
        elif prefs["spicy"]:
            pitch = "بيعطيك نكهة حارة واضحة وممتعة"
        elif prefs["healthy"] or prefs["light"]:
            pitch = "مناسب إذا بدك خيارًا خفيفًا ومتوازنًا"
        elif prefs["budget"]:
            pitch = "سعره مناسب ويعتبر خيارًا موفقًا"
        else:
            pitch = "وبيعتبر خيار موفّق إذا بدك طلب واضح ومضمون"
    if prefs["low_sugar"]:
        return (
            f"إذا بدك خيارًا أخف وأقل سكرًا، برشّحلك {top['name_ar']} [{top['id']}] بـ {int(top['price'])} ريال، {pitch}. "
            "وإذا تحب، أقدر أعطيك بديل قريب بنفس الفكرة وأبعدك عن الحلويات."
        )
    if prefs["child_friendly"]:
        return (
            f"إذا بدك وجبة أنسب لطفل، برشّحلك {top['name_ar']} [{top['id']}] بـ {int(top['price'])} ريال، {pitch}. "
            "وإذا تحب، أقدر أعطيك بديل ثاني قريب وبنكهة أهدأ."
        )
    return (
        f"برشّحلك {top['name_ar']} [{top['id']}] بـ {int(top['price'])} ريال، {pitch}. "
        "وإذا بدك، بقدر أعطيك بديل قريب حسب السعر أو النوع."
    )


def _build_named_dish_reply(user_message: str, item: dict[str, Any]) -> str:
    description = item.get("description_ar") or "من الأصناف المميزة عندنا"
    pitch = item.get("sales_pitch_ar") or "طعمها مميز وبتنفع إذا بدك شيء واضح ولذيذ"
    price = int(item.get("price", 0))
    meal_id = item["id"]
    name = item["name_ar"]
    if _looks_like_dish_opinion_request(user_message):
        return (
            f"برأيي {name} [{meal_id}] خيار موفق بـ {price} ريال، {pitch or description}. "
            "وإذا تحب، أقدر أرشّح لك معها شيء يكملها."
        )
    if any(phrase in _normalize_text(user_message) for phrase in ["أخبرني عن", "خبرني عن", "احكيلي عن"]):
        return (
            f"{name} [{meal_id}] بـ {price} ريال. {description}. "
            "وإذا تحب، أقدر أرشّح لك معه طبق جانبي أو بديل قريب."
        )
    return (
        f"إذا ودك تجرّب {name} [{meal_id}] فهو بـ {price} ريال، {description}. "
        "وأقدر أيضًا أرشّح لك معه شيء يكمل الطلب إذا تحب."
    )


def _pick_companion(
    *,
    categories: set[str],
    exclude_id: str,
    prefer_light: bool = False,
    prefer_non_sugary: bool = False,
) -> dict[str, Any] | None:
    best: tuple[int, dict[str, Any]] | None = None
    for meal in menu_loader.load_menu().meals:
        if meal.id == exclude_id or meal.category not in categories:
            continue
        payload = _meal_to_rag_payload(meal)
        combined = _normalize_arabic(
            f"{meal.name_ar} {meal.category} {' '.join(meal.tags)} {meal.description_ar}"
        )
        score = int(meal.featured) * 4 + int(meal.recommendation_rank or 0) * 2
        if any(tag in combined for tag in ["الاكثر طلب", "الأكثر طلب", "مشهور"]):
            score += 2
        if prefer_light and any(word in combined for word in ["خفيف", "صحي", "طازج", "منعش", "مشوي"]):
            score += 3
        if prefer_non_sugary and not _is_sugary_item(payload):
            score += 4
        if prefer_non_sugary and _is_sugary_item(payload):
            score -= 6
        candidate = (score, payload)
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best[1] if best else None


def _build_selected_meal_reply(item: dict[str, Any]) -> str:
    name = item["name_ar"]
    meal_id = item["id"]
    price = int(item.get("price", 0))
    category = str(item.get("category") or "")

    if category in {"أطباق رئيسية", "مشاوي"}:
        side = _pick_companion(
            categories={"مقبلات"},
            exclude_id=meal_id,
            prefer_light=True,
        )
        drink = _pick_companion(
            categories={"مشروبات"},
            exclude_id=meal_id,
            prefer_light=True,
            prefer_non_sugary=True,
        )
        if side and drink:
            return (
                f"اختيار موفق، {name} [{meal_id}] بـ {price} ريال. "
                f"إذا تحب أكمّل لك الطلب مثل النادل، أرشّح معه {side['name_ar']} [{side['id']}] "
                f"أو {drink['name_ar']} [{drink['id']}] حتى يطلع الطلب متوازن."
            )
    elif category == "حلويات":
        drink = _pick_companion(
            categories={"مشروبات"},
            exclude_id=meal_id,
            prefer_non_sugary=True,
        )
        if drink:
            return (
                f"اختيار جميل، {name} [{meal_id}] بـ {price} ريال. "
                f"وإذا تحب أكمّلها صح، يناسب معها {drink['name_ar']} [{drink['id']}] كثير."
            )
    elif category == "مقبلات":
        main = _pick_companion(
            categories={"أطباق رئيسية", "مشاوي"},
            exclude_id=meal_id,
            prefer_light=True,
        )
        if main:
            return (
                f"اختيار موفق، {name} [{meal_id}] بـ {price} ريال. "
                f"وإذا بدك نخلي الطلب أكمل، أرشّح بعدها {main['name_ar']} [{main['id']}] كطبق رئيسي."
            )

    return (
        f"اختيار موفق، {name} [{meal_id}] بـ {price} ريال. "
        "إذا تحب، أقدر أكمّل لك الطلب باقتراح مشروب أو طبق جانبي مناسب معه."
    )


def _companion_reason(item: dict[str, Any]) -> str:
    combined = _normalize_arabic(
        f"{item.get('name_ar', '')} {item.get('category', '')} "
        f"{' '.join(item.get('tags') or [])} {item.get('description_ar', '')}"
    )
    if any(word in combined for word in ["خفيف", "صحي", "منعش", "طازج"]):
        return "لأنه يوازن الطلب ويعطيه لمسة أخف"
    if any(word in combined for word in ["مشهور", "الاكثر طلب", "الأكثر طلب"]):
        return "لأنه من الخيارات المحبوبة كثير مع هالنوع من الأطباق"
    if item.get("category") == "مشروبات":
        return "لأنه يمشي معه بشكل مرتب ويخفف الطعم"
    if item.get("category") == "مقبلات":
        return "لأنه يفتح النفس ويكمل الطبق بشكل جميل"
    return "لأنه يكمل الطلب بشكل مرتب"


def _build_companion_reply(anchor_item: dict[str, Any], user_message: str) -> str:
    normalized = _normalize_arabic(user_message)
    anchor_name = anchor_item["name_ar"]
    anchor_id = anchor_item["id"]
    wants_drink = any(word in normalized for word in ["مشروب", "عصير", "شاي", "قهوه", "قهوة"])
    wants_side = any(word in normalized for word in ["جانبي", "مقبلات", "سلطه", "سلطة", "سلطات"])
    wants_main = any(word in normalized for word in ["رئيسي", "وجبه", "وجبة", "طبق"])

    category = str(anchor_item.get("category") or "")
    if category in {"أطباق رئيسية", "مشاوي"}:
        drink = _pick_companion(
            categories={"مشروبات"},
            exclude_id=anchor_id,
            prefer_light=True,
            prefer_non_sugary=True,
        )
        side = _pick_companion(
            categories={"مقبلات"},
            exclude_id=anchor_id,
            prefer_light=True,
        )
        if wants_drink and drink:
            return (
                f"إذا بدك مشروبًا يكمل {anchor_name}، أرشّح لك {drink['name_ar']} [{drink['id']}] "
                f"بـ {int(drink['price'])} ريال، {_companion_reason(drink)}."
            )
        if wants_side and side:
            return (
                f"إذا بدك طبقًا جانبيًا مع {anchor_name}، أرشّح لك {side['name_ar']} [{side['id']}] "
                f"بـ {int(side['price'])} ريال، {_companion_reason(side)}."
            )
        if side and drink:
            return (
                f"إذا بدك شيء يكمل {anchor_name}، أميل أولًا إلى {side['name_ar']} [{side['id']}] "
                f"بـ {int(side['price'])} ريال، {_companion_reason(side)}. "
                f"وإذا تحب مشروبًا معه، {drink['name_ar']} [{drink['id']}] بـ {int(drink['price'])} ريال مناسب أيضًا."
            )

    if category == "مقبلات":
        if wants_drink:
            drink = _pick_companion(
                categories={"مشروبات"},
                exclude_id=anchor_id,
                prefer_light=True,
                prefer_non_sugary=True,
            )
            if drink:
                return (
                    f"مع {anchor_name}، أرشّح لك {drink['name_ar']} [{drink['id']}] "
                    f"بـ {int(drink['price'])} ريال، {_companion_reason(drink)}."
                )
        main = _pick_companion(
            categories={"أطباق رئيسية", "مشاوي"},
            exclude_id=anchor_id,
            prefer_light=not wants_main,
        )
        if main:
            return (
                f"إذا بدك شيء يكمل {anchor_name}، أرشّح بعدها {main['name_ar']} [{main['id']}] "
                f"بـ {int(main['price'])} ريال، {_companion_reason(main)}."
            )

    if category == "حلويات":
        drink = _pick_companion(
            categories={"مشروبات"},
            exclude_id=anchor_id,
            prefer_non_sugary=True,
        )
        if drink:
            return (
                f"مع {anchor_name}، أرشّح لك {drink['name_ar']} [{drink['id']}] "
                f"بـ {int(drink['price'])} ريال، {_companion_reason(drink)}."
            )

    return (
        f"إذا بدك شيء يكمل {anchor_name}، أقدر أرشّح لك مشروبًا خفيفًا أو طبقًا جانبيًا حسب ذوقك. "
        "إذا تحب، قلّي تفضّلها مع مشروب ولا مع طبق جانبي."
    )


def _build_contextual_compliment_reply(anchor_item: dict[str, Any] | None) -> str:
    if anchor_item is None:
        return "يسعدني إنه عجبك. إذا بدك أكمل لك الترشيح أو أضيف لك شيء مناسب معه أنا جاهز."
    return (
        f"يسعدني إنه عجبك ترشيح {anchor_item['name_ar']}. "
        "إذا تحب، أقدر الآن أرشّح لك شيء يكمل الطلب أو أنقلنا للخطوة الجاية."
    )


def _strip_internal_prompt_leak(text: str) -> str:
    cleaned = text.strip()
    for prefix in _PROMPT_LEAK_PREFIXES:
        if cleaned.startswith(prefix):
            for marker in [
                "برشّح",
                "برشح",
                "بنصحك",
                "بنصح",
                "برأيي",
                "أكيد",
                "يا أهلا",
                "إذا بدك",
                "اختيار موفق",
                "اختيار جميل",
                "من الأكثر",
            ]:
                pos = cleaned.find(marker)
                if pos > 0:
                    cleaned = cleaned[pos:].strip()
                    break
            else:
                return ""
    return cleaned


def build_turn(
    session_id: str,
    user_message: str,
    *,
    include_history: bool = True,
    follow_up_context: str | None = None,
) -> TurnBuildResult:
    t_start = time.perf_counter()
    analysis_message = _merge_context_hint(user_message, follow_up_context)
    route = _detect_route(analysis_message)
    rag_used = route in {"simple", "full", "allergen"}
    timings: dict[str, Any] = {
        "backend": settings.llm_backend,
        "route": route,
        "rag_used": rag_used,
    }

    history_t0 = time.perf_counter()
    raw_history = session_store.get_recent_history(session_id) if include_history else []
    timings["history_load_ms"] = round((time.perf_counter() - history_t0) * 1000, 1)

    # History retention policy by route:
    # - chitchat / offtopic: zero (no grounding needed; direct-reply)
    # - simple: keep the last 1 turn compacted — follow-ups like "كم سعره؟"
    #   and "طيب والثاني؟" only work if we remember what was just recommended.
    # - full / allergen: full compacted window (budget-capped).
    if route in {"chitchat", "offtopic"}:
        history: list[ChatMessage] = []
    elif route == "simple":
        history = _compact_history(raw_history)[-1:]
    else:
        history = _compact_history(raw_history)
    history_chars = _history_char_len(history)

    build_t0 = time.perf_counter()
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    rag_results: list[dict[str, Any]] = []
    direct_reply: str | None = None

    if route == "chitchat":
        print("[TIMING] rag.search_menu        =  SKIPPED  (chit-chat fast path)", flush=True)
        messages.append({"role": "user", "content": _normalize_text(user_message)})
        direct_reply = _build_chitchat_reply(user_message)
    elif route == "offtopic":
        print("[TIMING] rag.search_menu        =  SKIPPED  (off-topic deflection)", flush=True)
        messages.append({"role": "user", "content": _normalize_text(user_message)})
        direct_reply = _build_offtopic_reply(user_message)
    elif _POPULAR_RE.search(analysis_message):
        print("[TIMING] rag.search_menu        =  SKIPPED  (popular items reply)", flush=True)
        messages.append({"role": "user", "content": _normalize_text(user_message)})
        direct_reply = _build_popular_reply()
    elif route == "full" and _is_broad_recommendation_request(analysis_message):
        print("[TIMING] rag.search_menu        =  SKIPPED  (guided recommendation)", flush=True)
        messages.append({"role": "user", "content": _normalize_text(user_message)})
        direct_reply = _build_broad_recommendation_reply()
        guided_questions = _build_broad_recommendation_questions()
        timings["prompt_build_ms"] = round((time.perf_counter() - build_t0) * 1000, 1)
        timings["build_total_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
        prompt_chars = sum(len(m["content"]) for m in messages)
        timings["history_chars"] = history_chars
        timings["prompt_chars"] = prompt_chars
        timings["guided_questions"] = len(guided_questions)
        timings["rag_used"] = False
        return TurnBuildResult(
            messages=messages,
            route=route,
            rag_used=False,
            history_chars=history_chars,
            prompt_chars=prompt_chars,
            timings=timings,
            model_name=_select_model_for_route(route),
            rag_results=[],
            direct_reply=direct_reply,
            guided_questions=guided_questions,
            guided_submit_label="أعطني ترشيحًا مناسبًا",
        )
    else:
        rag_query = _build_rag_query(analysis_message, raw_history)
        timings["retrieval_query_chars"] = len(rag_query)
        rag_t0 = time.perf_counter()
        rag_results = rag.search_menu(
            rag_query,
            top_k=2 if route == "simple" else settings.rag_top_k,
            metrics=timings,
        )
        timings["rag_search_ms"] = round((time.perf_counter() - rag_t0) * 1000, 1)
        print(f"[TIMING] rag.search_menu        = {timings['rag_search_ms']:7.1f} ms", flush=True)

        # Lexical override: if the guest typed a dish name literally (e.g. from
        # a suggestion chip "احكيلي عن مندي لحم"), that exact meal must be the
        # top result. Semantic search alone confused "مندي لحم" with
        # "سمبوسة لحم" on multilingual-MiniLM. Prepend lexical hits and dedup.
        lex_hits = _lexical_meal_hits(analysis_message)
        if lex_hits:
            lex_ids = {h["id"] for h in lex_hits}
            rag_results = lex_hits + [r for r in rag_results if r["id"] not in lex_ids]
            # Cap total context size — keep lexical hits + enough semantic
            # neighbors to support "alternatives" follow-ups.
            max_ctx = max(settings.rag_top_k, len(lex_hits) + 2)
            rag_results = rag_results[:max_ctx]
            timings["lexical_hits"] = [h["id"] for h in lex_hits]
            print(
                f"[TIMING] lexical override      =   {len(lex_hits)} hit(s) "
                f"({', '.join(h['id'] for h in lex_hits)})",
                flush=True,
            )

        pref_hits = _preference_seed_hits(analysis_message)
        if pref_hits:
            pref_ids = {h["id"] for h in pref_hits}
            rag_results = pref_hits + [r for r in rag_results if r["id"] not in pref_ids]
            max_ctx = max(settings.rag_top_k, len(pref_hits))
            rag_results = rag_results[:max_ctx]
            timings["preference_hits"] = [h["id"] for h in pref_hits[:4]]

        # No-match guard: Qdrant always returned *something* before we added the
        # score floor in rag.py. Now an empty list means "nothing above floor" —
        # i.e. the query is likely off-domain or too vague. Return a scoped ask
        # instead of letting the model hallucinate a grounded answer.
        if not rag_results:
            messages.append({"role": "user", "content": _normalize_text(user_message)})
            direct_reply = _build_no_match_reply()
        else:
            include_ings = route == "allergen"
            rag_context = _format_rag_context(
                rag_results,
                compact=route == "simple",
                include_ingredients=include_ings,
            )
            allowed_ids = ", ".join(r["id"] for r in rag_results)
            constraint = (
                "القائمة (اختر بس من هدول الأصناف بحرفيتهم. ممنوع تذكر أي اسم "
                f"أو سعر مش موجود هون): {rag_context}"
            )
            user_parts = [constraint, f"معرفات مسموحة فقط: [{allowed_ids}]"]

            if route == "allergen":
                user_parts.append(
                    "تعليمات: الضيف بيسأل عن مكوّنات أو حساسية. جاوبه بالضبط من "
                    "المكوّنات ومسببات الحساسية المذكورة فوق. إذا المعلومة مش "
                    "موجودة، قلّه صراحة إنك بدك تتأكد من الكاشير. ممنوع تخمّن."
                )

            # Inject cart on any grounded route where it's non-empty — follow-ups
            # like "ضيف نفس الطبق" must see what's already ordered.
            cart = session_store.get_cart(session_id)
            if cart.items:
                user_parts.append(f"سلة: {_format_cart(cart)}")

            if follow_up_context:
                user_parts.append(f"سياق متابعة: {_normalize_text(follow_up_context)}")
            user_parts.append(f"سؤال: {_normalize_text(user_message)}")
            messages.append({"role": "user", "content": "\n".join(user_parts)})

            # simple route only: canned deterministic reply to skip LLM entirely.
            # Never used for allergen (that needs real model reasoning over
            # ingredients) or full (that needs richer phrasing). Also suppressed
            # when the guest literally named a dish — the canned template
            # ("برشّحلك X") is wrong when they asked "احكيلي عن X"; the LLM must
            # describe that specific dish instead.
            if route == "allergen":
                direct_reply = _build_allergen_direct_reply(analysis_message, rag_results)
            elif len(lex_hits) == 1 and _looks_like_meal_selection(analysis_message):
                direct_reply = _build_selected_meal_reply(lex_hits[0])
            elif len(lex_hits) == 1 and (
                _looks_like_named_dish_request(analysis_message)
                or _looks_like_dish_opinion_request(analysis_message)
            ):
                direct_reply = _build_named_dish_reply(user_message, lex_hits[0])
            elif route == "simple" and not lex_hits:
                direct_reply = _build_simple_direct_reply(analysis_message, rag_results)
            elif route == "full" and _is_recommendation_request(analysis_message) and not lex_hits:
                direct_reply = _build_simple_direct_reply(analysis_message, rag_results)

    timings["prompt_build_ms"] = round((time.perf_counter() - build_t0) * 1000, 1)
    timings["build_total_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
    prompt_chars = sum(len(m["content"]) for m in messages)
    timings["history_chars"] = history_chars
    timings["prompt_chars"] = prompt_chars
    model_name = _select_model_for_route(route)
    timings["model"] = model_name
    return TurnBuildResult(
        messages=messages,
        route=route,
        rag_used=rag_used and bool(rag_results),
        history_chars=history_chars,
        prompt_chars=prompt_chars,
        timings=timings,
        model_name=model_name,
        rag_results=rag_results,
        direct_reply=direct_reply,
    )


def _resolve_cards(
    meal_ids: list[str],
    *,
    allowed_ids: set[str] | None = None,
) -> list[MealCard]:
    seen: set[str] = set()
    cards: list[MealCard] = []
    for mid in meal_ids:
        norm = mid.upper()
        if norm in seen:
            continue
        seen.add(norm)
        # Guardrail: if an RAG-allowed set is provided, reject any tag the model
        # invented that wasn't in the retrieved menu slice. Prevents the small
        # model from surfacing a real-but-off-context meal card.
        if allowed_ids is not None and norm not in allowed_ids:
            continue
        meal = menu_loader.get_meal_by_id(norm)
        if meal:
            cards.append(
                MealCard(
                    meal_id=meal.id,
                    name_ar=meal.name_ar,
                    price=meal.price,
                    currency=meal.currency,
                    image_url=meal.image_url,
                    spice_level=meal.spice_level,
                    calories=meal.calories,
                )
            )
    return cards


def _log_profile(profile: dict[str, Any]) -> None:
    print(
        "[PROFILE] " + json.dumps(profile, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


async def collect_benchmark(
    session_id: str,
    user_message: str,
    *,
    include_history: bool = True,
    follow_up_context: str | None = None,
) -> dict[str, Any]:
    t_start = time.perf_counter()
    build = build_turn(
        session_id,
        user_message,
        include_history=include_history,
        follow_up_context=follow_up_context,
    )
    metrics = dict(build.timings)
    reply_parts: list[str] = []

    allowed_id_set: set[str] | None = (
        {r["id"].upper() for r in build.rag_results} if build.rag_used else None
    )

    if build.direct_reply:
        full_reply = build.direct_reply
        metrics["llm_skipped"] = True
        metrics["llm_ttft_ms"] = 0.0
        metrics["llm_decode_ms"] = 0.0
        metrics["llm_total_ms"] = 0.0
        metrics["llm_chunks"] = 0
        metrics["llm_chars"] = 0
        metrics["rag_used"] = build.rag_used
        visible_reply = _strip_internal_prompt_leak(MEAL_TAG_RE.sub("", full_reply).strip()) or full_reply
        metrics["reply_chars"] = len(visible_reply)
        metrics["meal_card_count"] = len(
            _resolve_cards(
                [m.group(1) for m in MEAL_TAG_RE.finditer(full_reply)],
                allowed_ids=allowed_id_set,
            )
        )
        metrics["total_request_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
        return metrics

    async for chunk in llm_client.stream_text(
        build.messages,
        model_name=build.model_name,
        max_tokens=_max_tokens_for_route(build.route),
        metrics=metrics,
    ):
        if chunk:
            reply_parts.append(chunk)

    full_reply = "".join(reply_parts)
    visible_reply = _strip_internal_prompt_leak(MEAL_TAG_RE.sub("", full_reply).strip())
    if not visible_reply and len(build.rag_results) == 1:
        visible_reply = _strip_internal_prompt_leak(
            MEAL_TAG_RE.sub("", _build_named_dish_reply(user_message, build.rag_results[0])).strip()
        ) or _build_named_dish_reply(user_message, build.rag_results[0])
    metrics["llm_skipped"] = False
    metrics["rag_used"] = build.rag_used
    metrics["reply_chars"] = len(visible_reply)
    metrics["meal_card_count"] = len(
        _resolve_cards(
            [m.group(1) for m in MEAL_TAG_RE.finditer(full_reply)],
            allowed_ids=allowed_id_set,
        )
    )
    metrics["total_request_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
    return metrics


async def run_stream(
    session_id: str,
    user_message: str,
    *,
    follow_up_context: str | None = None,
) -> AsyncIterator[dict]:
    """
    Async generator yielding events:
      {"event": "text", "delta": "..."}
      {"event": "meal_cards", "cards": [...]}
      {"event": "done", "session_id": "..."}
    """
    t_start = time.perf_counter()
    build = build_turn(session_id, user_message, follow_up_context=follow_up_context)
    metrics = dict(build.timings)
    print(
        f"[TIMING] prompt built            = {metrics['build_total_ms']:7.1f} ms  "
        f"({build.prompt_chars} chars, {len(build.messages)} msgs, route={build.route})",
        flush=True,
    )

    allowed_id_set: set[str] | None = (
        {r["id"].upper() for r in build.rag_results} if build.rag_used else None
    )

    reply_parts: list[str] = []
    if build.direct_reply:
        full_reply = build.direct_reply
        visible_reply = _strip_internal_prompt_leak(MEAL_TAG_RE.sub("", full_reply).strip()) or full_reply
        yield {"event": "text", "delta": visible_reply}
        if build.guided_questions:
            yield {
                "event": "choices",
                "questions": [question.model_dump() for question in build.guided_questions],
                "submit_label": build.guided_submit_label or "رشّح لي الآن",
            }
        meal_ids = [match.group(1) for match in MEAL_TAG_RE.finditer(full_reply)]
        cards = _resolve_cards(meal_ids, allowed_ids=allowed_id_set)
        if cards:
            yield {"event": "meal_cards", "cards": [c.model_dump() for c in cards]}
        session_store.save_message(session_id, ChatMessage(role="user", content=user_message))
        session_store.save_message(
            session_id, ChatMessage(role="assistant", content=visible_reply or "…")
        )
        metrics["llm_skipped"] = True
        metrics["llm_ttft_ms"] = 0.0
        metrics["llm_decode_ms"] = 0.0
        metrics["llm_total_ms"] = 0.0
        metrics["llm_chunks"] = 0
        metrics["llm_chars"] = 0
        metrics["rag_used"] = build.rag_used
        metrics["reply_chars"] = len(visible_reply)
        metrics["meal_card_count"] = len(cards)
        metrics["total_request_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
        _log_profile(metrics)
        yield {"event": "done", "session_id": session_id}
        return

    # Hold back up to MAX_TAG_LEN chars in case a [MEAL_xxx] tag straddles chunks.
    carry = ""
    max_tag_len = 16  # "[MEAL_0000]" is 11 chars; 16 is comfortable slack

    async for chunk in llm_client.stream_text(
        build.messages,
        model_name=build.model_name,
        max_tokens=_max_tokens_for_route(build.route),
        metrics=metrics,
    ):
        if not chunk:
            continue
        combined = carry + chunk

        # Repeatedly strip complete [MEAL_xxx] tags from the front.
        while True:
            match = MEAL_TAG_RE.search(combined)
            if not match:
                break
            pre = combined[: match.start()]
            if pre:
                reply_parts.append(pre)
                yield {"event": "text", "delta": pre}
            reply_parts.append(match.group(0))
            combined = combined[match.end() :]

        if len(combined) > max_tag_len:
            emit = combined[:-max_tag_len]
            carry = combined[-max_tag_len:]
            last_bracket = emit.rfind("[")
            if last_bracket != -1 and "]" not in emit[last_bracket:]:
                carry = emit[last_bracket:] + carry
                emit = emit[:last_bracket]
            if emit:
                reply_parts.append(emit)
                yield {"event": "text", "delta": emit}
        else:
            carry = combined

    if carry:
        final = carry
        while True:
            match = MEAL_TAG_RE.search(final)
            if not match:
                break
            pre = final[: match.start()]
            if pre:
                reply_parts.append(pre)
                yield {"event": "text", "delta": pre}
            reply_parts.append(match.group(0))
            final = final[match.end() :]
        if final:
            reply_parts.append(final)
            yield {"event": "text", "delta": final}

    full_reply = "".join(reply_parts)
    meal_ids = [match.group(1) for match in MEAL_TAG_RE.finditer(full_reply)]
    cards = _resolve_cards(meal_ids, allowed_ids=allowed_id_set)
    if cards:
        yield {"event": "meal_cards", "cards": [c.model_dump() for c in cards]}

    visible_reply = _strip_internal_prompt_leak(MEAL_TAG_RE.sub("", full_reply).strip())
    if not visible_reply and len(build.rag_results) == 1:
        fallback_reply = _build_named_dish_reply(user_message, build.rag_results[0])
        visible_reply = _strip_internal_prompt_leak(MEAL_TAG_RE.sub("", fallback_reply).strip()) or fallback_reply
    session_store.save_message(session_id, ChatMessage(role="user", content=user_message))
    session_store.save_message(
        session_id, ChatMessage(role="assistant", content=visible_reply or "…")
    )

    metrics["llm_skipped"] = False
    metrics["rag_used"] = build.rag_used
    metrics["reply_chars"] = len(visible_reply)
    metrics["meal_card_count"] = len(cards)
    metrics["total_request_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
    _log_profile(metrics)
    yield {"event": "done", "session_id": session_id}
