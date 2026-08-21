import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import hashlib
import re
import streamlit as st

from utils.email_client import send_magic_link_email
from utils.session import auth_mode, create_guest_magic_link, restore_login, save_login, clear_login
from utils.users_store import load_users, save_users


st.title("登入／註冊")

restore_login(st)
mode = auth_mode(st)

users = load_users()

if mode == "member" and st.session_state.get("username"):
    username_logged = st.session_state["username"]
    balance = users[username_logged]["tokens"]
    st.info("你已登入")
    st.metric("我的代幣", balance)
    if st.button("登出"):
        clear_login(st)
        st.rerun()

elif mode == "guest":
    guest_email = st.session_state.get("guest_email", "")
    st.info(f"你目前是訪客模式（{guest_email}）")
    st.caption("訪客僅可瀏覽公開題目；若要上傳作答與使用代幣，請註冊帳號。")
    if st.button("離開訪客模式"):
        clear_login(st)
        st.rerun()

else:
    st.write(f"目前已註冊 {len(users)} 個帳號")
    tab_guest, tab_login, tab_register = st.tabs(["訪客看題目", "登入", "註冊"])

    with tab_guest:
        st.caption("輸入本系信箱，系統會寄送短效登入連結（僅可瀏覽公開題目）。")
        guest_email = st.text_input("系所信箱", key="guest_email")
        email_pattern = st.secrets.get("GUEST_EMAIL_REGEX") or r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if st.button("寄送訪客連結", key="guest_send_link"):
            normalized = guest_email.strip().lower()
            if not normalized:
                st.warning("請輸入信箱")
            elif not re.fullmatch(email_pattern, normalized):
                st.warning("信箱格式不符合規定")
            else:
                try:
                    link = create_guest_magic_link(st, email=normalized)
                    send_magic_link_email(normalized, link, expire_minutes=30)
                    st.success("連結已寄出，請到信箱收信。")
                except Exception as e:
                    st.error(f"寄送失敗：{e}")

    with tab_login:
        login_username = st.text_input("帳號", key="login_username")
        login_password = st.text_input("密碼", type="password", key="login_password")

        if st.button("登入", key="login_submit"):
            hashed = hashlib.sha256(login_password.encode("utf-8")).hexdigest()
            if login_username not in users:
                st.error("帳號或密碼錯誤")
            elif hashed != users[login_username]["password_hash"]:
                st.error("帳號或密碼錯誤")
            else:
                st.success("登入成功！")
                user_id = hashlib.sha256(login_username.encode("utf-8")).hexdigest()[:12]
                save_login(st, login_username, user_id)
                st.rerun()

    with tab_register:
        reg_username = st.text_input("請輸入帳號", key="register_username")
        reg_password = st.text_input("請輸入密碼", type="password", key="register_password")

        if st.button("註冊", key="register_submit"):
            if reg_username == "":
                st.warning("請輸入帳號")
            elif reg_password == "":
                st.warning("請輸入密碼")
            elif reg_username in users:
                st.warning("此帳號已存在")
            else:
                hashed = hashlib.sha256(reg_password.encode("utf-8")).hexdigest()
                users[reg_username] = {
                    "password_hash": hashed,
                    "tokens": 3,
                    "unlocked": [],
                }
                save_users(users)
                user_id = hashlib.sha256(reg_username.encode("utf-8")).hexdigest()[:12]
                save_login(st, reg_username, user_id)
                st.success(
                    f"帳號「{reg_username}」註冊成功！先給你三代幣體驗壹下，"
                    "可以拿去解別人的作答看看"
                )
                st.rerun()
