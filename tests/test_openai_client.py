import os
import unittest
from pathlib import Path

from utils.openai_client import resolve_openai_api_key


class ResolveOpenAIKeyTests(unittest.TestCase):
    def test_prefers_explicit_api_key(self):
        self.assertEqual(resolve_openai_api_key("custom-key"), "custom-key")

    def test_reads_from_environment(self):
        os.environ["OPENAI_API_KEY"] = "env-key"
        try:
            self.assertEqual(resolve_openai_api_key(), "env-key")
        finally:
            os.environ.pop("OPENAI_API_KEY", None)

    def test_reads_from_local_secrets_file(self):
        repo_root = Path(__file__).resolve().parents[1]
        secrets_path = repo_root / ".streamlit" / "secrets.toml"
        self.assertTrue(secrets_path.exists())
        key = resolve_openai_api_key()
        self.assertTrue(key)
        self.assertIn("sk-", key)


if __name__ == "__main__":
    unittest.main()
