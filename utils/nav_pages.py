import streamlit as st

# 功能頁：登入後才顯示
home_page = st.Page("views/home.py", title="首頁")
upload_page = st.Page("pages/upload.py", title="上傳作答")
browse_page = st.Page("pages/browse.py", title="瀏覽題庫")
profile_page = st.Page("pages/profile.py", title="個人頁面")


def build_pages(auth_mode: str) -> dict:
    if auth_mode == "member":
        return {
            "": [st.Page("views/home.py", title="首頁", default=True)],
            "功能": [upload_page, browse_page, profile_page],
        }
    if auth_mode == "guest":
        return {
            "": [st.Page("pages/browse.py", title="瀏覽題庫", default=True)],
        }
    return {
        "": [st.Page("pages/login.py", title="登入／註冊", default=True)],
    }
