import hashlib

from utils.session import clear_login, restore_login, save_login
from utils.users_store import load_users, save_users


def render_login_register(st, *, section_key: str = "auth", show_title: bool = True):
    if show_title:
        st.title("登入／註冊")

    restore_login(st)
    users = load_users()

    if st.session_state.get("logged_in") and st.session_state.get("username"):
        username_logged = st.session_state["username"]
        balance = users[username_logged]["tokens"]
        st.info("你已登入")
        st.metric("我的代幣", balance)
        if st.button("登出", key=f"{section_key}_logout"):
            clear_login(st)
            st.rerun()
        return

    st.write(f"目前已註冊 {len(users)} 個帳號")
    tab_login, tab_register = st.tabs(["登入", "註冊"])

    with tab_login:
        login_username = st.text_input("帳號", key=f"{section_key}_login_username")
        login_password = st.text_input(
            "密碼", type="password", key=f"{section_key}_login_password"
        )

        if st.button("登入", key=f"{section_key}_login_submit"):
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
        reg_username = st.text_input("請輸入帳號", key=f"{section_key}_register_username")
        reg_password = st.text_input(
            "請輸入密碼", type="password", key=f"{section_key}_register_password"
        )

        if st.button("註冊", key=f"{section_key}_register_submit"):
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