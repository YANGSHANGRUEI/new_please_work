import os
import smtplib
from email.message import EmailMessage


def _read_config(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return str(value)
    try:
        import streamlit as st

        secret_value = st.secrets.get(name)
        if secret_value:
            return str(secret_value)
    except Exception:
        pass
    return default


def send_magic_link_email(to_email: str, link: str, expire_minutes: int = 30) -> None:
    host = _read_config("SMTP_HOST").strip()
    port = int(_read_config("SMTP_PORT", "587").strip())
    username = _read_config("SMTP_USERNAME").strip()
    password = _read_config("SMTP_PASSWORD").strip()
    from_email = _read_config("SMTP_FROM_EMAIL", username).strip()

    if not host or not username or not password or not from_email:
        raise ValueError("SMTP 設定不完整，請先設定 SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM_EMAIL")

    msg = EmailMessage()
    msg["Subject"] = "法律申論題平台訪客登入連結"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(
        "您好，\n\n"
        "請點擊以下連結進入公開題目瀏覽（僅限訪客模式）：\n"
        f"{link}\n\n"
        f"此連結有效時間約 {expire_minutes} 分鐘，逾時請重新申請。\n"
    )

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
