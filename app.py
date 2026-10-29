"""Streamlit entry point for the Arabic fitness plan.

The original interface is HTML/CSS/JavaScript. Streamlit hosts it in an iframe so
its SVG animations, interactive controls, and browser localStorage can run client-side.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="خطة التنشيف وبناء العضلات - 12 أسبوع",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

HTML_PATH = Path(__file__).parent / "templates" / "index.html"
html = HTML_PATH.read_text(encoding="utf-8")

# Hide Streamlit's default chrome for a closer fit to the original landing page.
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

# components.html renders the full document in a browser iframe; JavaScript,
# SVG animation, CSS, and localStorage remain client-side.
components.html(html, height=6000, scrolling=True)
