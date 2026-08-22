import re
import smtplib
from email.message import EmailMessage


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_NTU_STUDENT_EMAIL_RE = re.compile(r"^b[1-9]{2}a01[123][1-9]{2}@ntu\.edu\.tw$")


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def is_valid_ntu_student_email(email: str) -> bool:
    return bool(_NTU_STUDENT_EMAIL_RE.match(email.strip().lower()))


def send_browse_link_email(st, recipient_email: str, link: str, ttl_minutes: int):
    host = str(st.secrets.get("SMTP_HOST", "")).strip()
    port = int(st.secrets.get("SMTP_PORT", 587))
    username = str(st.secrets.get("SMTP_USER", "")).strip()
    password = str(st.secrets.get("SMTP_PASSWORD", "")).strip()
    sender = str(st.secrets.get("SMTP_FROM", username)).strip()
    use_tls = bool(st.secrets.get("SMTP_USE_TLS", True))

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