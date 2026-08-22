import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from utils.auth_ui import render_login_register
from utils.magic_link_email import (
    is_valid_ntu_student_email,
    send_browse_link_email,
    smtp_presence_map,
)
from utils.session import build_browse_entry_url
from utils.session import clear_login


def _resolve_magic_link_base_url(st) -> str:
    configured = str(st.secrets.get("APP_BASE_URL", "")).strip()

    current_origin = ""
    try:
        headers = getattr(st.context, "headers", {})
        host = headers.get("host") or headers.get("Host")
        if host:
            proto = headers.get("x-forwarded-proto") or headers.get("X-Forwarded-Proto")
            if not proto:
                proto = "http" if host.startswith("localhost") or host.startswith("127.0.0.1") else "https"
            current_origin = f"{proto}://{host}"
    except Exception:
        current_origin = ""

    # Local debugging should prefer the live local app origin to avoid linking to stale cloud deployments.
    if current_origin.startswith("http://localhost") or current_origin.startswith("http://127.0.0.1"):
        return current_origin

    return configured or current_origin

st.title("法律申論題交流平台")
st.markdown("歡迎使用法律申論題交流平台，這裡的運作模式是上傳自己的作答換取代幣以解鎖他人作答，希望可以促進法律系同學的交流學習。")

reason = st.session_state.get("browse_access_reason")
if reason == "already_used":
    st.warning("此限時連結已使用過，請重新輸入信箱取得新連結。")
elif reason in {"invalid_or_expired", "missing_or_expired"}:
    if st.session_state.get("browse_access") is False:
        st.info("限時連結無效或已過期，請重新取得新連結。")

if st.session_state.get("logged_in"):
    st.success("已登入")
    st.markdown("請用左側 **功能** 選單進入上傳、瀏覽或個人頁面。")
else:
    st.subheader("看考古題（免註冊）")
    st.caption("僅接受 NTU 學號信箱：前九碼需符合 bxxa01yzz（第七碼 y 需為 1/2/3，x/z 為 1-9），後綴 @ntu.edu.tw。")
    browse_email = st.text_input("信箱", key="browse_email_input", placeholder="you@example.com")

    if st.button("寄送限時連結", key="send_browse_link"):
        normalized_email = browse_email.strip().lower()
        if not is_valid_ntu_student_email(normalized_email):
            st.warning("信箱格式不符。請使用符合 bxxa01yzz@ntu.edu.tw 的 NTU 學號信箱（y=1/2/3，x/z=1-9）。")
        else:
            base_url = _resolve_magic_link_base_url(st)
            if not base_url:
                st.error("尚未設定 APP_BASE_URL，請先在 secrets 設定網站網址")
            else:
                ttl_sec = 180
                ttl_minutes = 3
                link = build_browse_entry_url(st, normalized_email, base_url, ttl_sec=ttl_sec)
                result = send_browse_link_email(st, normalized_email, link, ttl_minutes)
                if result["ok"]:
                    st.success(f"連結已寄到 {normalized_email}，請於 {ttl_minutes} 分鐘內使用")
                else:
                    st.error(result["message"])
                    if result.get("code") == "smtp_not_configured":
                        presence = smtp_presence_map(st)
                        with st.expander("SMTP 設定診斷（不含敏感值）"):
                            st.write("以下僅顯示欄位是否被目前執行環境讀到：")
                            for key, exists in presence.items():
                                st.write(f"- {key}: {'OK' if exists else 'MISSING'}")
                            st.caption("若全部顯示 MISSING，通常是雲端 App Secrets 尚未成功儲存或你目前開的是另一個 App。")
                    allow_debug_link = bool(st.secrets.get("ALLOW_DEBUG_MAGIC_LINK", True))
                    if allow_debug_link:
                        st.info("目前為除錯模式，請直接使用下列連結測試：")
                        st.code(link)

    if st.session_state.get("browse_access") and st.session_state.get("browse_exp"):
        exp_ts = int(st.session_state["browse_exp"])
        exp_str = datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d %H:%M:%S")
        st.success("已啟用限時瀏覽權限")
        st.caption(f"驗證信箱：{st.session_state.get('browse_email')}｜有效至：{exp_str}")

    st.markdown("---")
    st.subheader("參與代幣系統（需註冊登入）")
    st.caption("上傳作答可獲得代幣，並用代幣解鎖他人作答。")
    render_login_register(st, section_key="home_login", show_title=False)

if st.session_state.get("logged_in"):
    if st.button("登出"):
        clear_login(st)
        st.rerun()
