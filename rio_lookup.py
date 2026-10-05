# tools/rio_lookup.py
"""
Tool 4 — RIO Escalation Matrix Lookup.

Two modes:
  A) User types an SC name (Banani, Savar, Sylhet, Cox'sBazar, …)
     → shows RIO #, SC Head, STL 2nd level, 2nd level (HOD), RIO Head
  B) User types a fixed keyword:
        'STL CTO'   → STL CTO details
        'SCOMM CTO' → SCOMM CTO details
        'MD&CEO'    → MD & CEO details

Data source:
    data/DWDM Escalation Matrix_RIO Updated_V4252025.xlsx
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = _PROJECT_ROOT / "data" / \
    "DWDM Escalation Matrix_RIO Updated_V4252025.xlsx"


# ----------------------------------------------------------------------
# Phone / name parsing
# ----------------------------------------------------------------------
_PHONE_RE = re.compile(r"\(?(\+?88)?0?1\d{9}\)?")
_EMAIL_RE = re.compile(r"[\w\.\-\+]+@[\w\.\-]+\.\w+")


def split_name_phone(cell) -> tuple[str, str]:
    """
    Return (name, phone) from a free-text cell like:
      'Mohammad Faruq Azam\\nfaruq.azam@summit-towers.net\\n(01827550901)'
      'Saleh Uddin Md. Joni \\n(01611050509) (HOD+Successor)'
    """
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return "", ""
    text = str(cell).strip()
    if not text:
        return "", ""

    # phone — first match
    m = _PHONE_RE.search(text)
    phone = m.group(0).strip("()") if m else ""

    # name — cut off at first email and first phone
    name = _EMAIL_RE.split(text)[0]
    name = _PHONE_RE.split(name)[0]
    # remove parenthetical notes like (HOD+Successor)
    name = re.sub(r"\(.*?\)", "", name)
    # collapse whitespace/newlines
    name = re.sub(r"\s+", " ", name).strip(" ,-")

    return name, phone


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------
@st.cache_data(show_spinner="Loading escalation matrix…")
def load_matrix(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=0, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    # Forward-fill the RIO group (Excel merges cells — only the first
    # row of each group carries the RIO label).
    df["RIO"] = df["RIO"].ffill()

    # ─── NEW ─────────────────────────────────────────────────────
    # Same trick for the leadership columns: STL 2nd level,
    # 2nd level (HOD), and Rio Head are also only filled on the first
    # row of each RIO group. Fill them down so every SC inherits the
    # contacts of its RIO group.
    for col in ("STL 2nd level", "2nd level", "Rio Head"):
        if col in df.columns:
            df[col] = df[col].ffill()
    # ─────────────────────────────────────────────────────────────

    # Keep only rows with a real SC name
    df = df[df["SC Name"].notna()].copy()
    df["SC Name"] = df["SC Name"].astype(str).str.strip()
    df = df[df["SC Name"] != ""].reset_index(drop=True)
    return df


# ----------------------------------------------------------------------
# Lookups
# ----------------------------------------------------------------------
def find_sc(df: pd.DataFrame, query: str) -> pd.DataFrame:
    q = query.strip().lower()
    exact = df[df["SC Name"].str.lower() == q]
    if not exact.empty:
        return exact
    return df[df["SC Name"].str.lower().str.contains(re.escape(q), na=False)]


def get_fixed_contact(df: pd.DataFrame, keyword: str) -> dict | None:
    """
    Return {'title':..., 'name':..., 'phone':..., 'email':...} for one
    of the fixed leadership roles:
        'STL CTO'  → column 'STL CTO'
        'SCOMM CTO'→ column 'SCOMM CTO'
        'MD&CEO'   → column 'MD&CEO'
    """
    key = keyword.strip().upper()
    if key not in {"STL CTO", "SCOMM CTO", "MD&CEO"}:
        return None

    # Real column name (preserve casing from Excel)
    col = None
    for c in df.columns:
        if c.strip().upper() == key:
            col = c
            break
    if col is None:
        return None

    # The value is the same across all RIO groups — take the first
    # non-empty cell in that column.
    for _, row in df.iterrows():
        val = row.get(col)
        if val and str(val).strip():
            name, phone = split_name_phone(val)
            # email might be inside the raw cell
            m = _EMAIL_RE.search(str(val))
            email = m.group(0) if m else ""
            return {
                "title": keyword.upper(),
                "name": name,
                "phone": phone,
                "email": email,
                "raw": str(val).strip(),
            }
    return None


# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------
def _contact_block(title: str, name: str, phone: str):
    st.markdown(f"### {title}")
    st.markdown(f"**Name:** {name or '—'}")
    st.markdown(f"**Contact:** {phone or '—'}")


def render():
    st.header("📞 RIO Escalation Matrix")
    st.caption(
        "Type an **SC name** (e.g. *Banani*, *Savar*, *Sylhet*) — OR — "
        "type **STL CTO**, **SCOMM CTO**, or **MD&CEO** to see that "
        "person's details."
    )

    # ---- file check ----
    if not MATRIX_PATH.exists():
        st.error(f"❌ Excel not found at:\n\n`{MATRIX_PATH}`")
        st.info("Place the escalation matrix file in the `data/` folder.")
        return

    with st.sidebar.expander("⚙️ Escalation Matrix", expanded=False):
        st.caption(f"📁 {MATRIX_PATH.name}")
        if st.button("🔄 Reload matrix", key="rio_reload"):
            st.cache_data.clear()

    try:
        df = load_matrix(str(MATRIX_PATH))
    except Exception as e:
        st.error(f"Failed to load matrix: {e}")
        return

    st.caption(f"✅ {len(df)} SC entries · "
               f"{df['RIO'].nunique()} RIO groups")

    # ---- quick-pick buttons for the fixed roles ----
    st.markdown("**Quick access:**")
    c1, c2, c3 = st.columns(3)
    if c1.button("🏢 STL CTO", key="rio_q_stl", use_container_width=True):
        st.session_state["rio_query"] = "STL CTO"
    if c2.button("📡 SCOMM CTO", key="rio_q_scomm", use_container_width=True):
        st.session_state["rio_query"] = "SCOMM CTO"
    if c3.button("👔 MD&CEO", key="rio_q_md", use_container_width=True):
        st.session_state["rio_query"] = "MD&CEO"

    # ---- main input ----
    query = st.text_input(
        "Search",
        placeholder="SC name  or  STL CTO / SCOMM CTO / MD&CEO",
        key="rio_query",
    )

    if not query.strip():
        with st.expander("📋 Show all SC names"):
            st.write(", ".join(sorted(df["SC Name"].unique().tolist())))
        return

    q_upper = query.strip().upper()

    # ---------- MODE B — fixed leadership roles ----------
    if q_upper in {"STL CTO", "SCOMM CTO", "MD&CEO"}:
        info = get_fixed_contact(df, q_upper)
        if not info:
            st.warning(f"No data found for '{query}'.")
            return

        st.subheader(f"🏛️ {info['title']}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Name:** {info['name'] or '—'}")
            st.markdown(f"**Contact:** {info['phone'] or '—'}")
        with c2:
            if info["email"]:
                st.markdown(f"**Email:** {info['email']}")
        with st.expander("Raw cell"):
            st.code(info["raw"])
        return

    # ---------- MODE A — SC lookup ----------
    hits = find_sc(df, query)
    if hits.empty:
        st.warning(f"No SC found matching '{query}'.")
        return

    if len(hits) > 1:
        chosen = st.selectbox(
            "Multiple matches — choose one",
            hits["SC Name"].tolist(),
            key="rio_choice",
        )
        hits = hits[hits["SC Name"] == chosen]

    row = hits.iloc[0]

    sc_name    = row.get("SC Name", "")
    sc_head    = row.get("SC Head Name", "")
    sc_contact = row.get("Contact", "")
    rio        = row.get("RIO", "")

    # STL 2nd level  → column E
    stl2_name,  stl2_phone  = split_name_phone(row.get("STL 2nd level", ""))

    # 2nd level      → column F (HOD)
    lvl2_name,  lvl2_phone  = split_name_phone(row.get("2nd level", ""))

    # RIO Head       → column G
    rioh_name,  rioh_phone  = split_name_phone(row.get("Rio Head", ""))

    # ---- header ----
    st.subheader(f"📌 {sc_name}  ·  {rio}")

    # ---- SC Head + RIO # ----
    c1, c2 = st.columns(2)
    with c1:
        _contact_block("👤 SC Head", sc_head, sc_contact)
    with c2:
        st.markdown("### 🧭 RIO")
        st.markdown(f"**RIO No:** {rio or '—'}")

    st.markdown("---")

    # ---- 2nd level + RIO Head ----
    c1, c2 = st.columns(2)
    with c1:
        _contact_block("🧑‍💼 STL 2nd Level", stl2_name, stl2_phone)
        _contact_block("👔 2nd Level (Successor)", lvl2_name, lvl2_phone)
    with c2:
        _contact_block("🏢 RIO Head", rioh_name, rioh_phone)

    # ---- raw row ----
    with st.expander("🔍 Show full raw row"):
        st.json({k: v for k, v in row.to_dict().items()
                 if pd.notna(v)})
