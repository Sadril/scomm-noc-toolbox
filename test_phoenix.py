import streamlit as st
st.set_page_config(page_title="Phoenix TT", layout="wide")
from tools.phoenix_tt import render
render()
