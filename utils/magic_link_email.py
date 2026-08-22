import re
import smtplib
from email.message import EmailMessage


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_NTU_STUDENT_EMAIL_RE = re.compile(r"^b[1-9]{2}a01[123][1-9]{2}@ntu\.edu\.tw$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def is_valid_ntu_student_email(email: str) -> bool:
    return bool(_NTU_STUDENT_EMAIL_RE.match(email.strip().lower()))


def _lookup_secret(st, key: str, default=""):
    # 1) Exact top-level key, e.g. SMTP_HOST
    value = st.secrets.get(key)
    if value not in (None, ""):
        return value

    # 2) Common lowercase top-level key, e.g. smtp_host
    lower_key = key.lower()
    value = st.secrets.get(lower_key)
    if value not in (None, ""):
        return value

    # 3) Nested style, e.g. [smtp] host = "..."
    smtp_section = st.secrets.get("smtp") or st.secrets.get("SMTP")
    if smtp_section:
        short_key = lower_key.replace("smtp_", "", 1)
        value = smtp_section.get(short_key)
        if value not in (None, ""):
            return value
        value = smtp_section.get(key)
        if value not in (None, ""):
            return value

    return default


def _lookup_secret_bool(st, key: str, default: bool) -> bool:
    raw = _lookup_secret(st, key, default)
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def send_browse_link_email(st, recipient_email: str, link: str, ttl_minutes: int):
    host = str(_lookup_secret(st, "SMTP_HOST", "")).strip()
    try:
        port = int(_lookup_secret(st, "SMTP_PORT", 587))
    except Exception:
        port = 587
    username = str(_lookup_secret(st, "SMTP_USER", "")).strip()
    password = str(_lookup_secret(st, "SMTP_PASSWORD", "")).strip()
    sender = str(st.secrets.get("SMTP_FROM", username)).strip()
    if not sender:
        sender = str(_lookup_secret(st, "SMTP_FROM", username)).strip()
    use_tls = _lookup_secret_bool(st, "SMTP_USE_TLS", True)

    missing = []
    if not host:
        missing.append("SMTP_HOST")
    if not username:
        missing.append("SMTP_USER")
    if not password:
        missing.append("SMTP_PASSWORD")
    if not sender:
        missing.append("SMTP_FROM")

    if missing:
        return {
            "ok": False,
            "code": "smtp_not_configured",
            "message": "未設定 SMTP，無法自動寄信。缺少欄位：" + ", ".join(missing),
        }

    msg = EmailMessage()
    msg["Subject"] = "法律申論題平台：考古題限時連結"
    msg["From"] = sender
    msg["To"] = recipient_email
    msg.set_content(
        "您好，\n\n"
        "以下是您的考古題限時連結：\n"
        f"{link}\n\n"
        f"此連結有效時間為 {ttl_minutes} 分鐘。\n"
        "若非您本人操作，請忽略此信件。\n"
    )

    try:
        with smtplib.SMTP(host=host, port=port, timeout=20) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
            server.send_message(msg)
    except Exception as err:
        return {
            "ok": False,
            "code": "smtp_send_failed",
            "message": f"寄信失敗：{err}",
        }

    return {"ok": True, "code": "sent", "message": "連結已寄出"}