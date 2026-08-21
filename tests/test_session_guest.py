import unittest

from utils.session import (
    auth_mode,
    clear_login,
    create_guest_magic_link,
    restore_login,
    save_guest_login,
)


class _DummySecrets(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _DummySt:
    def __init__(self):
        self.session_state = {}
        self.query_params = {}
        self.secrets = _DummySecrets(
            {
                "APP_SESSION_SECRET": "test-secret",
                "APP_BASE_URL": "https://example.com",
            }
        )


class SessionGuestTests(unittest.TestCase):
    def test_save_guest_login_sets_guest_mode(self):
        st = _DummySt()
        save_guest_login(st, "student@example.com")
        self.assertEqual(auth_mode(st), "guest")
        self.assertEqual(st.session_state.get("guest_email"), "student@example.com")
        self.assertTrue(st.query_params.get("auth"))

    def test_restore_login_from_guest_token(self):
        st = _DummySt()
        link = create_guest_magic_link(st, "student@example.com", ttl_sec=1800)
        token = link.split("auth=", 1)[1]

        st2 = _DummySt()
        st2.query_params["auth"] = token
        restore_login(st2)

        self.assertEqual(auth_mode(st2), "guest")
        self.assertEqual(st2.session_state.get("guest_email"), "student@example.com")
        self.assertFalse(st2.session_state.get("logged_in"))

    def test_clear_login_resets_guest_mode(self):
        st = _DummySt()
        save_guest_login(st, "student@example.com")
        clear_login(st)
        self.assertEqual(auth_mode(st), "anonymous")


if __name__ == "__main__":
    unittest.main()
