import streamlit as st

# 功能頁：登入後才顯示
home_page = st.Page("views/home.py", title="首頁")
upload_page = st.Page("pages/upload.py", title="上傳作答")
browse_page = st.Page("pages/browse.py", title="瀏覽題庫")
profile_page = st.Page("pages/profile.py", title="個人頁面")


def build_pages(logged_in: bool, browse_access: bool = False) -> dict:
    if logged_in:
        return {
            "": [st.Page("views/home.py", title="首頁", default=True)],
            "功能": [upload_page, browse_page, profile_page],
        }
    if browse_access:
        return {
            "": [st.Page("pages/browse.py", title="瀏覽題庫", default=True)],
            "功能": [home_page],
        }
    return {
        "": [st.Page("views/home.py", title="首頁", default=True)],
    }
