import builtins
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
