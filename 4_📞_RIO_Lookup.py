# pages/4_📞_RIO_Lookup.py
import streamlit as st

st.set_page_config(page_title="RIO Lookup",
                   page_icon="📞", layout="wide")

from tools.rio_lookup import render
render()
