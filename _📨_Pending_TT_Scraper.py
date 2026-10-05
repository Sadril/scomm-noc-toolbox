# pages/2_📨_Pending_TT_Scraper.py
import streamlit as st

st.set_page_config(page_title="Pending TT Scraper",
                   page_icon="📨", layout="wide")

from tools.phoenix_tt import render
render()
