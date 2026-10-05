import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import get_user_memory
from services.ai_extractor import answer_question_about_document, generate_chat_response


class TestChatQNA(unittest.TestCase):
    def test_answer_question_about_document(self):
        document_text = """
        Driving Licence
        Name: Varun Prasath
        Licence Number: TN45 20200002199
        """
        extracted = {
            "document_type": "driving_licence",
            "name": "Varun Prasath",
            "licence_number": "TN45 20200002199",
            "confidence": 0.94,
        }

        answer = answer_question_about_document(
            "What is the licence number?",
            document_text,
            extracted,
        )

        self.assertIn("TN45", answer.upper())
        self.assertIn("LICENCE", answer.upper())

    def test_generate_chat_response_uses_document_context(self):
        response = generate_chat_response(
            "What is the licence number?",
            "Driving Licence\nLicence Number: TN45 20200002199",
            {"document_type": "driving_licence", "licence_number": "TN45 20200002199"},
        )
        self.assertIn("TN45", response.upper())

    def test_user_memory_is_isolated(self):
        user_one = type("Context", (), {"user_data": {}})()
        user_two = type("Context", (), {"user_data": {}})()

        get_user_memory(user_one)["last_document_text"] = "First user doc"
        get_user_memory(user_two)["last_document_text"] = "Second user doc"

        self.assertEqual(get_user_memory(user_one)["last_document_text"], "First user doc")
        self.assertEqual(get_user_memory(user_two)["last_document_text"], "Second user doc")


if __name__ == "__main__":
    unittest.main()
