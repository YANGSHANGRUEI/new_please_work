import builtins
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import utils.questions_store as questions_store
from utils.questions_store import combo_key, _get_supabase_config


class QuestionsStoreTests(unittest.TestCase):
    def test_combo_key_is_stable(self):
        self.assertEqual(
            combo_key("民法", "債法", "王老師", "112-1"),
            "民法::債法::王老師::112-1",
        )

    def test_reads_local_secrets_when_streamlit_runtime_is_unavailable(self):
        repo_root = Path(__file__).resolve().parents[1]
        secrets_path = repo_root / ".streamlit" / "secrets.toml"
        self.assertTrue(secrets_path.exists())

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "streamlit":
                raise ImportError("streamlit unavailable")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            url, key, table = _get_supabase_config()

        self.assertIn("supabase.co", url)
        self.assertTrue(key.startswith("sb_"))
        self.assertEqual(table, "subject_and_url")

    def test_queries_supabase_with_wildcard_columns(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = [
            {
                "field": "民法",
                "subject": "債法",
                "teacher": "王老師",
                "year": "112-1",
                "question": "請問這是什麼？",
                "url": "https://example.com/q1",
            }
        ]

        with patch("utils.questions_store._get_supabase_config", return_value=("https://example.supabase.co", "test-key", "subject_and_url")), patch("utils.questions_store.requests.get", return_value=response) as mock_get:
            questions, error = questions_store._load_from_supabase()

        self.assertIsNone(error)
        self.assertIn("民法::債法::王老師::112-1", questions)
        self.assertEqual(questions["民法::債法::王老師::112-1"]["question_text"], "請問這是什麼？")
        self.assertIn("select=*", mock_get.call_args.args[0])

    def test_returns_clear_error_when_supabase_has_no_rows(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = []

        with patch("utils.questions_store._get_supabase_config", return_value=("https://example.supabase.co", "test-key", "subject_and_url")), patch("utils.questions_store.requests.get", return_value=response):
            questions, error = questions_store._load_from_supabase()

        self.assertEqual(questions, {})
        self.assertIn("沒有任何資料", error)


if __name__ == "__main__":
    unittest.main()
