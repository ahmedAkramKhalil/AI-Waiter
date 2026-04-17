"""
OpenAI-compatible tool schema definitions.
These are embedded in the system prompt so the LLM knows what tools exist
and when to call them (Falcon H1 doesn't reliably use the native tools param).
"""

TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_menu",
            "description": (
                "ابحث في قائمة الطعام بناءً على وصف المستخدم. "
                "استخدم هذه الأداة دائماً عند ذكر أي نوع طعام أو مزاج أو تفضيل."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "نص البحث بالعربية، مثل: 'حار', 'مشاوي', 'كبسة', 'نباتي', 'رخيص'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_meal_details",
            "description": "احصل على التفاصيل الكاملة لوجبة محددة بمعرّفها مثل MEAL_001.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meal_id": {
                        "type": "string",
                        "description": "معرّف الوجبة، مثل: MEAL_001",
                    }
                },
                "required": ["meal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "أضف وجبة إلى سلة الضيف. استخدمها فقط عند طلب الضيف الإضافة صراحةً.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meal_id": {
                        "type": "string",
                        "description": "معرّف الوجبة المراد إضافتها",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "الكمية (افتراضياً 1)",
                        "default": 1,
                    },
                },
                "required": ["meal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_cart",
            "description": "اعرض محتويات سلة الضيف الحالية والإجمالي.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

# Compact Arabic description injected into the system prompt
TOOLS_DESCRIPTION = """
## الأدوات المتاحة:
- search_menu(query: str) — ابحث في القائمة
- get_meal_details(meal_id: str) — تفاصيل وجبة
- add_to_cart(meal_id: str, quantity: int=1) — أضف للسلة
- view_cart() — اعرض السلة
"""
