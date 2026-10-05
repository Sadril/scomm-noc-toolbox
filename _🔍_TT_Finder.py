# pages/3_🔍_TT_Finder.py
import streamlit as st

st.set_page_config(page_title="TT Finder",
                   page_icon="🔍", layout="wide")

from tools.phoenix_tt_finder import render
render()
