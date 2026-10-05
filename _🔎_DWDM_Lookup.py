# pages/1_🔎_DWDM_Lookup.py
import streamlit as st

st.set_page_config(page_title="DWDM Lookup",
                   page_icon="🔎", layout="wide")

from tools.dwdm_lookup import render
render()
