# tools/alarm_formatter.py
"""
Tool 5 — Alarm Report Formatter.

Portion 1 — Comment library (two sections):
    A) Acknowledgement comments
    B) Comments for TT or Group
Portion 2 — Alarm details form → produces two formatted output blocks.
"""
from __future__ import annotations

import json

import streamlit as st

# ----------------------------------------------------------------------
# Portion 1 — Comment library
# ----------------------------------------------------------------------
ACK_COMMENTS = [
    "Ignore",
    "No service",
    "As per COS, ignore",
    "Switching,NA",
    "Team is present",
    "RMS",
    "Canceled as per OPUS",
    "No trail found",
]

TT_COMMENTS = [
    {
        "label": "For Ambient temperature",
        "text": (
            "AMBIENT_TEMP_FLUCT alarm is not cleared yet.\n\n"
            "This is a sub-rack ambient temperature fluctuation alarm. "
            "It is generated when the ambient temperature of the sub-rack "
            "varies beyond 15°C. Please clean the fan and filter associated "
            "with the sub-rack and wait at least 24 hours for the alarm to clear."
        ),
    },
    {
        "label": "For High Temperature",
        "text": (
            "Please reduce the Room Temperature to avoid unwanted outages."
        ),
    },
    {
        "label": "For Door open without site access",
        "text": (
            "bhai observing door open alarm but not found any Site Access "
            "request in our Site Access portal. Requesting to give access "
            "request in Site Access Portal."
        ),
    },
]


# ----------------------------------------------------------------------
# Formatters
# ----------------------------------------------------------------------
def build_output_1(name: str, location_info: str) -> str:
    return "\n".join([
        name.strip() or "(Name)",
        f"Location Info: {location_info.strip() or '(Location Info)'}",
    ])


def build_output_2(name: str, alarm_source: str,
                   trail_name: str, location_info: str) -> str:
    return "\n".join([
        name.strip() or "(Name)",
        "",
        alarm_source.strip() or "(Alarm Source)",
        "",
        "Trail Name:",
        trail_name.strip() or "(Trail Name)",
        "",
        "Location Info:",
        location_info.strip() or "(Location Info)",
    ])


def build_output_3_compact(name: str, alarm_source: str,
                           trail_name: str, location_info: str) -> str:
    return (
        f"{name.strip()} | "
        f"Alarm Source: {alarm_source.strip()} | "
        f"Trail Name: {trail_name.strip()} | "
        f"Location Info: {location_info.strip()}"
    )


# ----------------------------------------------------------------------
# Copy button (JS clipboard)
# ----------------------------------------------------------------------


import json as _json
import streamlit.components.v1 as components


def copy_button(label: str, text: str, key: str, height: int = 46):
    """
    Self-contained copy-to-clipboard button.

    The JS is built with plain string concatenation to avoid
    f-string brace-escape problems, and is injected via
    components.html so it survives Streamlit reruns.
    """
    label_js = _json.dumps(label)
    text_js  = _json.dumps(text)

    # --- the JS body, built as a plain string (no f-string) ---
    js = (
        "const btn = this;\n"
        "const original = " + label_js + ";\n"
        "const t = " + text_js + ";\n"
        "const done = function() {\n"
        "  btn.innerText = '\\u2705 Copied!';\n"
        "  setTimeout(function() { btn.innerText = original; }, 1200);\n"
        "};\n"
        "const fail = function() {\n"
        "  btn.innerText = '\\u26A0 Failed';\n"
        "  setTimeout(function() { btn.innerText = original; }, 1200);\n"
        "};\n"
        "if (navigator.clipboard && navigator.clipboard.writeText) {\n"
        "  navigator.clipboard.writeText(t).then(done, fail);\n"
        "} else {\n"
        "  const ta = document.createElement('textarea');\n"
        "  ta.value = t;\n"
        "  document.body.appendChild(ta);\n"
        "  ta.select();\n"
        "  try { document.execCommand('copy'); done(); }\n"
        "  catch(e) { fail(); }\n"
        "  document.body.removeChild(ta);\n"
        "}\n"
    )

    # --- the HTML, assembled with concatenation ---
    html = (
        '<div style="display:flex;align-items:center;height:100%;">'
        '<button '
        'onclick="' + js.replace('"', '&quot;') + '" '
        'style="padding:8px 14px;border-radius:6px;border:none;'
        'background:#ff4b4b;color:white;font-weight:600;'
        'cursor:pointer;font-size:13px;white-space:nowrap;">'
        + label +
        '</button></div>'
    )

    components.html(html, height=height, scrolling=False)
# ----------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------
def render():
    st.header("📝 Alarm Report Formatter")
    st.caption("Copy a comment, fill the alarm details, and grab the "
               "formatted output.")

    # ================= Portion 1 — Comment library ==================
    st.subheader("📚 Comment Library")

    tab_ack, tab_tt = st.tabs([
        "🅰️ Acknowledgement comments",
        "📝 Comments for TT or Group",
    ])

    # ---------- A. Acknowledgement comments ----------
    with tab_ack:
        st.caption("Short one-liners. Click a button to copy it.")
        cols = st.columns(len(ACK_COMMENTS))
        for i, c in enumerate(ACK_COMMENTS):
            with cols[i]:
                copy_button(c, c, key=f"ack_{i}")

    # ---------- B. Comments for TT or Group ----------
    with tab_tt:
        st.caption("Long paragraphs. Click **📋 Copy** next to any one.")
        for i, item in enumerate(TT_COMMENTS):
            st.markdown(f"**{item['label']}**")
            c1, c2 = st.columns([6, 1])
            with c1:
                st.code(item["text"], language="text")
            with c2:
                copy_button("📋 Copy", item["text"], key=f"tt_{i}")
            st.markdown("")  # spacer

    st.markdown("---")

    # ================= Portion 2 — Alarm form =======================
    st.subheader("🔧 Alarm Details")

    for k in ("alm_name", "alm_src", "alm_trail", "alm_loc"):
        if k not in st.session_state:
            st.session_state[k] = ""

    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Name", key="alm_name",
                             placeholder="e.g. BEFFEC_EXC")
        trail = st.text_input("Trail Name", key="alm_trail",
                              placeholder="e.g. BOSDRC01HTD01-MYSDRC01HTD01-OTU4-454995")
    with c2:
        src = st.text_input("Alarm Source", key="alm_src",
                            placeholder="e.g. MYSDRDS01 / MYSDRC01HTD01")
        loc = st.text_input("Location Info", key="alm_loc",
                            placeholder="0-MYSDRDS01_1-D:MYSDRC01HTD01-1-…")

    b1, b2, _ = st.columns([1, 1, 4])
    with b1:
        generate = st.button("⚡ Generate", type="primary",
                             key="alm_generate")
    with b2:
        if st.button("🧹 Clear", key="alm_clear"):
            for k in ("alm_name", "alm_src", "alm_trail", "alm_loc"):
                st.session_state[k] = ""
            st.session_state["alm_generated"] = False
            st.rerun()

    if generate:
        st.session_state["alm_generated"] = True

    if not st.session_state.get("alm_generated"):
        st.info("Fill in the fields above and click **⚡ Generate**.")
        return

    if not name.strip() or not loc.strip():
        st.warning("Please fill in at least **Name** and **Location Info**.")
        return

    out1 = build_output_1(name, loc)
    out2 = build_output_2(name, src, trail, loc)
    out3 = build_output_3_compact(name, src, trail, loc)

    st.markdown("---")
    st.subheader("📤 Outputs")

    st.markdown("#### Output 1")
    c1, c2 = st.columns([6, 1])
    with c1:
        st.code(out1, language="text")
    with c2:
        copy_button("📋 Copy", out1, key="copy_out1")

    st.markdown("#### Output 2")
    c1, c2 = st.columns([6, 1])
    with c1:
        st.code(out2, language="text")
    with c2:
        copy_button("📋 Copy", out2, key="copy_out2")

    st.markdown("#### Output 3 — Single line (for chat)")
    c1, c2 = st.columns([6, 1])
    with c1:
        st.code(out3, language="text")
    with c2:
        copy_button("📋 Copy", out3, key="copy_out3")
