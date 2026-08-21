import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from utils.nav_pages import build_pages
from utils.session import auth_mode, restore_login

st.set_page_config(page_title="法律申論題眾包平台")
hide_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    a[data-testid="stDeployButton"] {display:none;}
    [data-testid="stToolbar"] {display:none;}
    [data-testid="stHeader"] {display:none;}
    [data-testid="stDecoration"] {display:none;}
    [data-testid="stStatusWidget"] {display:none;}
    button[kind="header"] {display:none;}
    button[kind="headerNoPadding"] {display:none;}
    button[title="View app menu"] {display:none;}
    button[aria-label="View app menu"] {display:none;}
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)


restore_login(st)

pages = build_pages(auth_mode(st))
pg = st.navigation(pages)
pg.run()
