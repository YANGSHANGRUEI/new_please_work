import unittest
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
from tempfile import TemporaryDirectory
from pathlib import Path

import utils.session as session


class _FakeSt:
    def __init__(self):
        self.secrets = {
            "APP_SESSION_SECRET": "test-secret",
            "BROWSE_LINK_TTL_SEC": 1800,
        }
        self.query_params = {}
        self.session_state = {}


class BrowseAccessSessionTests(unittest.TestCase):
    def _set_temp_consumed_store(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        patcher = patch.object(
            session,
            "_CONSUMED_BROWSE_TOKENS_FILE",
            Path(tempdir.name) / "consumed.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_restore_browse_access_from_valid_token(self):
        self._set_temp_consumed_store()
        st = _FakeSt()
        url = session.build_browse_entry_url(
            st,
            email="test@example.com",
            base_url="https://example.com/app",
            ttl_sec=600,
        )
        token = parse_qs(urlparse(url).query)["browse"][0]
        st.query_params["browse"] = token

        session.restore_browse_access(st)

        self.assertTrue(st.session_state.get("browse_access"))
        self.assertEqual(st.session_state.get("browse_email"), "test@example.com")
        self.assertIsInstance(st.session_state.get("browse_exp"), int)

    def test_restore_browse_access_rejects_invalid_token(self):
        self._set_temp_consumed_store()
        st = _FakeSt()
        st.query_params["browse"] = "invalid.token"

        session.restore_browse_access(st)

        self.assertFalse(st.session_state.get("browse_access"))
        self.assertIsNone(st.session_state.get("browse_email"))

    def test_restore_browse_access_rejects_expired_token(self):
        self._set_temp_consumed_store()
        st = _FakeSt()
        with patch("utils.session.time.time", return_value=1000):
            token = session._make_browse_token(st, "exp@example.com", ttl_sec=120)
        st.query_params["browse"] = token

        with patch("utils.session.time.time", return_value=1000 + 3600):
            session.restore_browse_access(st)

        self.assertFalse(st.session_state.get("browse_access"))
        self.assertIsNone(st.session_state.get("browse_email"))

    def test_restore_browse_access_is_one_time_only(self):
        self._set_temp_consumed_store()
        st1 = _FakeSt()
        url = session.build_browse_entry_url(
            st1,
            email="once@example.com",
            base_url="https://example.com/app",
            ttl_sec=180,
        )
        token = parse_qs(urlparse(url).query)["browse"][0]

        st1.query_params["browse"] = token
        session.restore_browse_access(st1)
        self.assertTrue(st1.session_state.get("browse_access"))

        st2 = _FakeSt()
        st2.query_params["browse"] = token
        session.restore_browse_access(st2)
        self.assertFalse(st2.session_state.get("browse_access"))


if __name__ == "__main__":
    unittest.main()