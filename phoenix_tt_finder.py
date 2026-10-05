# tools/phoenix_tt_finder.py
"""
Tool 3 — Phoenix TT Finder (ID + Problem Category + Open link).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

import certifi
import requests
import streamlit as st
from bs4 import BeautifulSoup


BASE_URL    = "https://phoenix.summitcommunications.net/"
LOGIN_PAGE  = BASE_URL
AUTH_URL    = urljoin(BASE_URL, "authenticate")
VIEW_TT_URL = urljoin(BASE_URL, "ViewTT")
EDIT_TT_URL = urljoin(BASE_URL, "EditTT")   # + "?ticket_id=<id>"

CA_BUNDLE = certifi.where()

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

USER_TYPES = ["default", "IIG", "ITC", "ICX"]

STATUS_OPTIONS = [
    ("Not Closed",                   "not_closed"),
    ("Any status",                   ""),
    ("New",                          "New"),
    ("Acknowledged",                 "Acknowledged"),
    ("Ongoing",                      "Ongoing"),
    ("Request for Closing",          "Request for Closing"),
    ("Request for Time Extension",   "Request for Time Extension"),
    ("Access Required",              "Access Required"),
    ("Information Required",         "Information Required"),
    ("Closed",                       "Closed"),
]

TT_ID_RE = re.compile(r"^\d{6,}$")


# ----------------------------------------------------------------------
# Session / login
# ----------------------------------------------------------------------
def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    s.verify = CA_BUNDLE
    return s


def login(session: requests.Session,
          username: str, password: str,
          user_type: str = "default") -> str:
    session.get(LOGIN_PAGE, timeout=20).raise_for_status()

    r = session.post(
        AUTH_URL,
        data={"username": username,
              "password": password,
              "user_type": user_type},
        timeout=20, allow_redirects=True,
    )
    r.raise_for_status()

    u = r.url.lower()
    if "login" in u or "authenticate" in u:
        raise RuntimeError(
            "Login rejected — still on login/authenticate page. "
            "Check username, password, and user_type."
        )
    return r.url


# ----------------------------------------------------------------------
# Search + extract
# ----------------------------------------------------------------------
def search_tt_id(session: requests.Session,
                 keyword: str,
                 status: str = "not_closed") -> list[dict]:
    """
    Return one dict per matching TT row:
        {
          "tt_id": "2026247319",
          "problem_category": "Link Down",
          "open_url": "https://phoenix.summitcommunications.net/EditTT?ticket_id=2026247319",
        }
    """
    params = {
        "company":            "",
        "ticket_id":          "",
        "ticket_title":       keyword,
        "dashboard_value":    "",
        "ticket_status":      status,
        "assigned_dept":      "",
        "assigned_subcenter": "",
        "client_id":          "",
        "problem_category":   "",
        "Search":             "Search",
    }
    r = session.get(VIEW_TT_URL, params=params, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    table = soup.find("table", id="ticket_table_view")
    if table is None:
        return []

    # ---- header → index ----
    headers = [th.get_text(" ", strip=True).lower()
               for th in table.find_all("th")]

    def col_index(*cands, default):
        for c in cands:
            for i, h in enumerate(headers):
                if c.lower() == h:
                    return i
        for c in cands:
            for i, h in enumerate(headers):
                if c.lower() in h:
                    return i
        return default

    tt_idx = col_index("tt id", "ticket id", default=0)
    pc_idx = col_index("problem category", "problem", default=3)

    rows: list[dict] = []
    seen: set[str] = set()
    tbody = table.find("tbody") or table

    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        def cell(i):
            return tds[i].get_text(" ", strip=True) if i < len(tds) else ""

        tt_id = cell(tt_idx)
        if not TT_ID_RE.match(tt_id) or tt_id in seen:
            continue
        seen.add(tt_id)

        # ---- build the open URL ----
        # Preferred: read the href from the pencil icon anchor.
        open_url = ""
        pencil = tr.find("i", id="edit_icon") or \
                 tr.find("i", class_=lambda c: c and "pencil-square-o" in c)
        if pencil:
            a = pencil.find_parent("a")
            if a and a.get("href"):
                open_url = urljoin(BASE_URL, a["href"])

        # Fallback: construct it from the TT ID pattern we know.
        if not open_url:
            open_url = f"{EDIT_TT_URL}?ticket_id={tt_id}"

        rows.append({
            "tt_id": tt_id,
            "problem_category": cell(pc_idx),
            "open_url": open_url,
        })

    return rows


# ----------------------------------------------------------------------
# Streamlit render
# ----------------------------------------------------------------------
def render():
    st.header("🔍 Phoenix — TT Finder")
    st.caption("Enter a ticket-title keyword, pick a status, and get "
               "the matching **TT ID** with a link to open it.")

    with st.sidebar.expander("🔐 Phoenix Credentials", expanded=False):
        username  = st.text_input("Username / Email", key="phxf_user")
        password  = st.text_input("Password", type="password", key="phxf_pass")
        user_type = st.selectbox("User Type", USER_TYPES,
                                 index=0, key="phxf_utype")

    col1, col2 = st.columns([3, 2])
    with col1:
        keyword = st.text_input(
            "Ticket Title contains…",
            placeholder="e.g. HTD, Huawei, DCDB-01, Rajshahi",
            key="phxf_kw",
        )
    with col2:
        status_label, status_value = st.selectbox(
            "Status",
            STATUS_OPTIONS,
            format_func=lambda x: x[0],
            index=0,
            key="phxf_status",
        )

    run = st.button("🚀 Find TT ID", type="primary", key="phxf_run")

    if not run:
        return

    if not username or not password:
        st.error("Enter your Phoenix credentials in the sidebar.")
        return
    if not keyword.strip():
        st.error("Type a ticket-title keyword.")
        return

    session = _new_session()

    with st.spinner("Logging in…"):
        try:
            login(session, username, password, user_type)
        except Exception as e:
            st.error(f"❌ Login failed: {e}")
            return

    with st.spinner("Searching…"):
        try:
            rows = search_tt_id(session, keyword, status_value)
        except Exception as e:
            st.error(f"❌ Search failed: {e}")
            return

    if not rows:
        st.warning("No TT found for that title/status.")
        return

    st.success(f"✅ {len(rows)} TT ID(s) found")

    # ---- one line per TT:  "TT_ID - Problem Category"  [✏️ Open] ----
    for r in rows:
        tt = r["tt_id"]
        pc = r["problem_category"] or "—"
        url = r["open_url"]

        c1, c2 = st.columns([6, 1])
        with c1:
            st.code(f"{tt} - {pc}")
        with c2:
            st.markdown(
                f'<a href="{url}" target="_blank" '
                f'style="display:inline-block;padding:6px 12px;'
                f'background:#ff4b4b;color:white;border-radius:6px;'
                f'text-decoration:none;font-weight:600;">✏️ Open</a>',
                unsafe_allow_html=True,
            )
