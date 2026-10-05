# pages/6_📨_Pending_Task.py
import streamlit as st

st.set_page_config(page_title="Pending Task Scraper",
                   page_icon="📨", layout="wide")

from tools.phoenix_stl_pending import render
render()
