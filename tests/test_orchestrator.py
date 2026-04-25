import unittest
from unittest.mock import patch

from apps.api.services import menu_loader, orchestrator, session_store


class OrchestratorSafetyTests(unittest.TestCase):
    def test_diabetic_and_child_recommendations_diverge(self) -> None:
        diabetic_query = "أنا مريض سكري وأحتاج شيئًا يناسبني"
        child_query = "أنا طفل بعمر 12 وأحتاج طعامًا يناسبني"

        diabetic_hits = orchestrator._preference_seed_hits(diabetic_query)
        child_hits = orchestrator._preference_seed_hits(child_query)

        diabetic_reply = orchestrator._build_simple_direct_reply(diabetic_query, diabetic_hits)
        child_reply = orchestrator._build_simple_direct_reply(child_query, child_hits)

        self.assertIsNotNone(diabetic_reply)
        self.assertIsNotNone(child_reply)
        self.assertNotEqual(diabetic_reply, child_reply)
        self.assertNotIn("بسبوسة", diabetic_reply)
        self.assertNotIn("كنافة", diabetic_reply)

    def test_allergen_reply_uses_menu_facts(self) -> None:
        meal = menu_loader.get_meal_by_id("MEAL_030")
        assert meal is not None
        payload = orchestrator._meal_to_rag_payload(meal)

        reply = orchestrator._build_allergen_direct_reply(
            "هل كنافة نابلسية فيها مكسرات؟",
            [payload],
        )

        self.assertIsNotNone(reply)
        self.assertIn("كنافة نابلسية", reply)
        self.assertIn("مكسرات", reply)

    def test_ambiguous_allergen_question_asks_for_specific_dish(self) -> None:
        first = menu_loader.get_meal_by_id("MEAL_019")
        second = menu_loader.get_meal_by_id("MEAL_022")
        assert first is not None and second is not None

        reply = orchestrator._build_allergen_direct_reply(
            "فيه سمسم؟",
            [
                orchestrator._meal_to_rag_payload(first),
                orchestrator._meal_to_rag_payload(second),
            ],
        )

        self.assertIsNotNone(reply)
        self.assertIn("أي طبق", reply)

    def test_affirmative_reply_uses_recent_context_in_rag_query(self) -> None:
        history = [
            orchestrator.ChatMessage(
                role="assistant",
                content="تمت إضافة مندي لحم إلى السلة. تحب أرشّح لك معه الآن مشروبًا أو طبقًا جانبيًا يكمل الطلب؟",
            )
        ]

        query = orchestrator._build_rag_query("نعم", history)

        self.assertIn("مندي لحم", query)
        self.assertIn("نعم", query)

    def test_broad_recommendation_returns_guided_questions(self) -> None:
        session = session_store.create_session()

        turn = orchestrator.build_turn(session.session_id, "شو أفضل وجبة عندكم؟", include_history=False)

        self.assertEqual(turn.route, "full")
        self.assertIsNotNone(turn.guided_questions)
        self.assertGreater(len(turn.guided_questions or []), 0)
        self.assertTrue(turn.direct_reply)

    def test_single_dish_opinion_question_is_direct_and_grounded(self) -> None:
        session = session_store.create_session()
        meal = menu_loader.get_meal_by_id("MEAL_026")
        assert meal is not None
        payload = orchestrator._meal_to_rag_payload(meal)

        with patch("apps.api.services.orchestrator.rag.search_menu", return_value=[payload]):
            turn = orchestrator.build_turn(session.session_id, "ما رأيك بمحمرة؟", include_history=False)

        self.assertTrue(turn.direct_reply)
        self.assertIn("محمرة", turn.direct_reply or "")
        self.assertNotIn("القائمة (", turn.direct_reply or "")

    def test_prompt_leak_is_stripped_from_visible_reply(self) -> None:
        leaked = (
            "القائمة (اختر بس من هدول الأصناف بحرفيتهم. ممنوع تذكر أي اسم أو سعر مش موجود هون): "
            "محمرة 16ر | جمبري مشوي 95ر. برأيي محمرة خيار موفق."
        )

        cleaned = orchestrator._strip_internal_prompt_leak(leaked)

        self.assertEqual(cleaned, "برأيي محمرة خيار موفق.")


if __name__ == "__main__":
    unittest.main()
