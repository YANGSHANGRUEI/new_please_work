import re
import smtplib
from email.message import EmailMessage


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def send_browse_link_email(st, recipient_email: str, link: str, ttl_minutes: int):
    host = str(st.secrets.get("SMTP_HOST", "")).strip()
    port = int(st.secrets.get("SMTP_PORT", 587))
    username = str(st.secrets.get("SMTP_USER", "")).strip()
    password = str(st.secrets.get("SMTP_PASSWORD", "")).strip()
    sender = str(st.secrets.get("SMTP_FROM", username)).strip()
    use_tls = bool(st.secrets.get("SMTP_USE_TLS", True))

    if not (host and username and password and sender):
        return {
            "ok": False,
            "code": "smtp_not_configured",
            "message": "未設定 SMTP，無法自動寄信。",
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