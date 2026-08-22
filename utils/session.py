import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from utils.users_store import load_users

_AUTH_QUERY_KEY = "auth"
_BROWSE_QUERY_KEY = "browse"
_TOKEN_TTL_SEC = 60 * 60 * 24 * 7  # 7 days
_BROWSE_TOKEN_TTL_SEC = 60 * 3  # 3 minutes
_CONSUMED_BROWSE_TOKENS_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "consumed_browse_tokens.json"
)


def _signing_secret(st) -> str:
    # Prefer explicit app secret; fall back to other configured secrets in dev.
    return (
        st.secrets.get("APP_SESSION_SECRET")
        or st.secrets.get("OPENAI_API_KEY")
        or "dev-insecure-session-secret"
    )


def _make_token(st, username: str, user_id: str) -> str:
    payload = {
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


def _read_query_auth(st) -> str:
    raw = st.query_params.get(_AUTH_QUERY_KEY)
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw or "")


def _read_query_browse(st) -> str:
    raw = st.query_params.get(_BROWSE_QUERY_KEY)
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


def _set_query_browse(st, token: str) -> None:
    st.query_params[_BROWSE_QUERY_KEY] = token


def _clear_query_browse(st) -> None:
    try:
        st.query_params.pop(_BROWSE_QUERY_KEY)
    except Exception:
        st.query_params[_BROWSE_QUERY_KEY] = ""


def _clear_browse_session(st) -> None:
    st.session_state["browse_access"] = False
    st.session_state["browse_email"] = None
    st.session_state["browse_exp"] = None
    st.session_state["browse_token_hash"] = None


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
        username = str(payload.get("u", "")).strip()
        user_id = str(payload.get("id", "")).strip()
        if not username or not user_id:
            return None
        return {"username": username, "user_id": user_id}
    except Exception:
        return None


def _browse_ttl_seconds(st) -> int:
    # Product requirement: browse links are fixed to 3-minute validity.
    return _BROWSE_TOKEN_TTL_SEC


def _load_consumed_browse_tokens() -> dict:
    _CONSUMED_BROWSE_TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _CONSUMED_BROWSE_TOKENS_FILE.exists():
        return {}
    try:
        with open(_CONSUMED_BROWSE_TOKENS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): int(v) for k, v in data.items()}


def _save_consumed_browse_tokens(tokens: dict) -> None:
    _CONSUMED_BROWSE_TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONSUMED_BROWSE_TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def _consume_browse_token_once(token: str, exp: int) -> bool:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(time.time())
    consumed = _load_consumed_browse_tokens()

    # Keep file compact by dropping expired token records.
    consumed = {k: v for k, v in consumed.items() if int(v) >= now}

    if token_hash in consumed:
        return False

    consumed[token_hash] = int(exp)
    _save_consumed_browse_tokens(consumed)
    return True


def _make_browse_token(st, email: str, ttl_sec: Optional[int] = None) -> str:
    ttl = _browse_ttl_seconds(st) if ttl_sec is None else max(60, int(ttl_sec))
    payload = {
        "scope": "browse",
        "email": email,
        "nonce": secrets.token_urlsafe(16),
        "exp": int(time.time()) + ttl,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    sig = hmac.new(
        _signing_secret(st).encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def _parse_browse_token(st, token: str) -> Optional[dict]:
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
        exp = int(payload.get("exp", 0))
        if exp < int(time.time()):
            return None
        if payload.get("scope") != "browse":
            return None
        email = str(payload.get("email", "")).strip()
        nonce = str(payload.get("nonce", "")).strip()
        if not email or not nonce:
            return None
        return {"email": email, "exp": exp, "nonce": nonce}
    except Exception:
        return None


def build_browse_entry_url(st, email: str, base_url: str, ttl_sec: Optional[int] = None) -> str:
    token = _make_browse_token(st, email, ttl_sec=ttl_sec)
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[_BROWSE_QUERY_KEY] = token
    new_query = urlencode(query)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def restore_login(st):
    if st.session_state.get("logged_in"):
        return

    token = _read_query_auth(st)
    if not token:
        return

    parsed = _parse_token(st, token)
    if not parsed:
        _clear_query_auth(st)
        return

    users = load_users()
    username = parsed["username"]
    if username not in users:
        _clear_query_auth(st)
        return

    st.session_state["logged_in"] = True
    st.session_state["username"] = username
    st.session_state["user_id"] = parsed["user_id"]


def restore_browse_access(st):
    st.session_state["_browse_jump_to_browse"] = False
    now = int(time.time())
    token = _read_query_browse(st)

    if not token:
        exp = int(st.session_state.get("browse_exp") or 0)
        if st.session_state.get("browse_access") and exp >= now:
            st.session_state["browse_access_reason"] = "active"
            return
        _clear_browse_session(st)
        st.session_state["browse_access_reason"] = "missing_or_expired"
        return

    parsed = _parse_browse_token(st, token)
    if not parsed:
        _clear_browse_session(st)
        st.session_state["browse_access_reason"] = "invalid_or_expired"
        _clear_query_browse(st)
        return

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    st.session_state["browse_access_reason"] = "granted"

    if not _consume_browse_token_once(token, parsed["exp"]):
        _clear_browse_session(st)
        st.session_state["browse_access_reason"] = "already_used"
        _clear_query_browse(st)
        return

    st.session_state["browse_access"] = True
    st.session_state["browse_email"] = parsed["email"]
    st.session_state["browse_exp"] = parsed["exp"]
    st.session_state["browse_token_hash"] = token_hash
    st.session_state["_browse_jump_to_browse"] = True
    _clear_query_browse(st)


def save_login(st, username, user_id):
    st.session_state["logged_in"] = True
    st.session_state["username"] = username
    st.session_state["user_id"] = user_id
    _set_query_auth(st, _make_token(st, username, user_id))


def clear_login(st):
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = None
    _clear_query_auth(st)
