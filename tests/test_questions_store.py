import os
import unittest
from pathlib import Path

from utils.questions_store import combo_key


class QuestionsStoreTests(unittest.TestCase):
    def test_combo_key_is_stable(self):
        self.assertEqual(
            combo_key("民法", "債法", "王老師", "112-1"),
            "民法::債法::王老師::112-1",
        )


if __name__ == "__main__":
    unittest.main()
