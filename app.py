"""Streamlit entry point for the Arabic 12-week fitness plan."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="خطة التنشيف وبناء العضلات - 12 أسبوع",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent

# Accept the intended project layout and common alternative upload layouts.
HTML_CANDIDATES = [
    BASE_DIR / "templates" / "index.html",
    BASE_DIR / "index.html",
    BASE_DIR / "fitness_flask_app" / "templates" / "index.html",
    BASE_DIR / "gem_1" / "templates" / "index.html",
]
HTML_PATH = next((path for path in HTML_CANDIDATES if path.is_file()), None)

st.markdown(
    """
    <style>
      #MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
      header {visibility: hidden;}
      .block-container {padding: 0 !important; max-width: 100% !important;}
      [data-testid="stAppViewContainer"] > .main {padding: 0 !important;}
      iframe {border: 0 !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

if HTML_PATH is None:
    st.error("ملف واجهة التطبيق index.html مش موجود في ملفات GitHub.")
    st.markdown(
        "تأكد إنك رفعت مجلد **templates** ومعاه ملف **index.html**، بحيث يكون المسار "
        "`templates/index.html` بجانب `app.py` في نفس مستوى المشروع."
    )
    st.code(
        "gem_1/\n"
        "├── app.py\n"
        "├── requirements.txt\n"
        "└── templates/\n"
        "    └── index.html",
        language="text",
    )
    st.stop()

html = HTML_PATH.read_text(encoding="utf-8")
components.html(html, height=6000, scrolling=True)
