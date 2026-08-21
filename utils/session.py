import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from utils.users_store import load_users

_AUTH_QUERY_KEY = "auth"
_TOKEN_TTL_SEC = 60 * 60 * 24 * 7  # 7 days
_GUEST_TOKEN_TTL_SEC = 60 * 30  # 30 mins


def _signing_secret(st) -> str:
    # Prefer explicit app secret; fall back to other configured secrets in dev.
    return (
        st.secrets.get("APP_SESSION_SECRET")
        or st.secrets.get("OPENAI_API_KEY")
        or "dev-insecure-session-secret"
    )


def _make_token(st, username: str, user_id: str) -> str:
    payload = {
        "t": "member",
        "u": username,
        "id": user_id,
        "exp": int(time.time()) + _TOKEN_TTL_SEC,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    sig = hmac.new(
        _signing_secret(st).encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def _make_guest_token(st, email: str, ttl_sec: int = _GUEST_TOKEN_TTL_SEC) -> str:
    payload = {
        "t": "guest",
        "email": email,
        "exp": int(time.time()) + int(ttl_sec),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    sig = hmac.new(
        _signing_secret(st).encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def _read_query_auth(st) -> str:
    raw = st.query_params.get(_AUTH_QUERY_KEY)
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw or "")


def _set_query_auth(st, token: str) -> None:
    st.query_params[_AUTH_QUERY_KEY] = token


def _clear_query_auth(st) -> None:
    try:
        st.query_params.pop(_AUTH_QUERY_KEY)
    except Exception:
        # Some Streamlit versions expose query params as a limited mapping.
        st.query_params[_AUTH_QUERY_KEY] = ""


def _parse_token(st, token: str) -> Optional[dict]:
    try:
        payload_b64, sig = token.split(".", 1)
        expected = hmac.new(
            _signing_secret(st).encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        token_type = str(payload.get("t", "member")).strip() or "member"
        if token_type == "guest":
            email = str(payload.get("email", "")).strip()
            if not email:
                return None
            return {"type": "guest", "email": email}

        username = str(payload.get("u", "")).strip()
        user_id = str(payload.get("id", "")).strip()
        if not username or not user_id:
            return None
        return {"type": "member", "username": username, "user_id": user_id}
    except Exception:
        return None


def restore_login(st):
    if st.session_state.get("auth_mode") in ("member", "guest"):
        return

    token = _read_query_auth(st)
    if not token:
        return

    parsed = _parse_token(st, token)
    if not parsed:
        _clear_query_auth(st)
        return

    if parsed.get("type") == "guest":
        st.session_state["logged_in"] = False
        st.session_state["auth_mode"] = "guest"
        st.session_state["guest_email"] = parsed["email"]
        st.session_state["username"] = None
        st.session_state["user_id"] = None
        return

    users = load_users()
    username = parsed["username"]
    if username not in users:
        _clear_query_auth(st)
        return

    st.session_state["logged_in"] = True
    st.session_state["auth_mode"] = "member"
    st.session_state["guest_email"] = None
    st.session_state["username"] = username
    st.session_state["user_id"] = parsed["user_id"]


def save_login(st, username, user_id):
    st.session_state["logged_in"] = True
    st.session_state["auth_mode"] = "member"
    st.session_state["guest_email"] = None
    st.session_state["username"] = username
    st.session_state["user_id"] = user_id
    _set_query_auth(st, _make_token(st, username, user_id))


def save_guest_login(st, email: str):
    st.session_state["logged_in"] = False
    st.session_state["auth_mode"] = "guest"
    st.session_state["guest_email"] = email
    st.session_state["username"] = None
    st.session_state["user_id"] = None
    _set_query_auth(st, _make_guest_token(st, email=email))


def create_guest_magic_link(
    st, email: str, base_url: str | None = None, ttl_sec: int = _GUEST_TOKEN_TTL_SEC
) -> str:
    token = _make_guest_token(st, email=email, ttl_sec=ttl_sec)
    resolved_base = (base_url or os.getenv("APP_BASE_URL") or st.secrets.get("APP_BASE_URL") or "").strip()
    if not resolved_base:
        raise ValueError("APP_BASE_URL 未設定，無法建立訪客登入連結")
    sep = "&" if "?" in resolved_base else "?"
    return f"{resolved_base}{sep}{_AUTH_QUERY_KEY}={token}"


def auth_mode(st) -> str:
    mode = st.session_state.get("auth_mode")
    if mode in ("member", "guest"):
        return mode
    if st.session_state.get("logged_in"):
        return "member"
    return "anonymous"


def clear_login(st):
    st.session_state["logged_in"] = False
    st.session_state["auth_mode"] = "anonymous"
    st.session_state["guest_email"] = None
    st.session_state["user_id"] = None
    st.session_state["username"] = None
    _clear_query_auth(st)
