# app.py — Home / landing page
import streamlit as st

st.set_page_config(
    page_title="SComm NOC Portal",
    page_icon="🌐",
    layout="wide",
)

st.markdown(
    """
    <div style="
        background: linear-gradient(135deg,#0a4d8c,#0b7fd0);
        padding: 40px;
        border-radius: 14px;
        color: white;
        margin-bottom: 30px;">
        <h1 style="margin:0;">🌐 SComm NOC Portal</h1>
        <p style="margin:6px 0 0 0; font-size:1.1em;">
            Welcome back, Md. Sadril! Ready to work?
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### 🚀 Available Tools")
st.markdown(
    """
    Click any tool in the left sidebar to open it. All tools share the
    same login session and the same DWDM database.
    """
)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 🔎 DWDM Lookup")
    st.write("Search DWDM links by path, node, or OCR snapshot.")
    st.page_link("pages/1_🔎_DWDM_Lookup.py",
                 label="Open DWDM Lookup →")

with col2:
    st.markdown("#### 📨 Pending TT Scraper")
    st.write("Fetch pending TT IDs for HTD / Huawei / Contains.")
    st.page_link("pages/2_📨_Pending_TT_Scraper.py",
                 label="Open Pending TT Scraper →")

with col3:
    st.markdown("#### 🔍 TT Finder")
    st.write("Find any TT ID by ticket-title keyword + status.")
    st.page_link("pages/3_🔍_TT_Finder.py",
                 label="Open TT Finder →")

st.markdown("---")
st.caption("SComm NOC Internal Tools — built with Streamlit")
