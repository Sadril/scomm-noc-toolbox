# pages/5_📝_Alarm_Formatter.py
import streamlit as st

st.set_page_config(page_title="Alarm Report Formatter",
                   page_icon="📝", layout="wide")

from tools.alarm_formatter import render
render()
