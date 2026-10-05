# tools/phoenix_stl_pending.py
"""
Tool 6 — Phoenix Pending Task Scraper.

Two search portions:
  1. STL Pending Task         → company=STL, status=not_closed
  2. Both Company · Client    → company="", client_id = Info-Sarkar-Ph3
                                (status=not_closed)

Extras per portion:
  * Per-row  ✏️ Open  link
  * 🚀 Open All      (opens every TT in a new tab)
  * 📋 Copy all URLs (copies all edit URLs to clipboard)
"""
from __future__ import annotations

import json as _json
import re
from urllib.parse import urljoin

import certifi
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup


BASE_URL     = "https://phoenix.summitcommunications.net/"
LOGIN_PAGE   = BASE_URL
AUTH_URL     = urljoin(BASE_URL, "authenticate")
PENDING_URL  = urljoin(BASE_URL, "ViewTT?dashboard_value=pending_task")
VIEW_TT_URL  = urljoin(BASE_URL, "ViewTT")
EDIT_TT_URL  = urljoin(BASE_URL, "EditTT")   # + "?ticket_id=<id>"

CA_BUNDLE = certifi.where()

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

USER_TYPES = ["default", "IIG", "ITC", "ICX"]

# Fixed values
STATUS = "not_closed"       # Not Closed

# Portion 1
STL_COMPANY = "STL"

# Portion 2
BOTH_COMPANY       = ""                    # "" = Both
INFO_SARKAR_CLIENT = "384"                 # numeric ID for Info-Sarkar-Ph3
INFO_SARKAR_LABEL  = "Info-Sarkar-Ph3"     # shown in the UI

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
# Pending page + hidden fields
# ----------------------------------------------------------------------
def fetch_pending_page(session: requests.Session) -> str:
    r = session.get(PENDING_URL, timeout=20)
    r.raise_for_status()
    return r.text


def _extract_hidden_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    out = {}
    for tag in soup.find_all("input", {"type": "hidden"}):
        n = tag.get("name")
        if n:
            out[n] = tag.get("value", "")
    return out


# ----------------------------------------------------------------------
# HTML table parser
# ----------------------------------------------------------------------
def _parse_ticket_table(html: str) -> list[dict]:
    """
    Parse <table id="ticket_table_view"> into a list of dicts:
        {"tt_id": ..., "problem_category": ..., "open_url": ...}
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id="ticket_table_view")
    if table is None:
        return []

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

        open_url = ""
        pencil = tr.find("i", id="edit_icon") or \
                 tr.find("i", class_=lambda c: c and "pencil-square-o" in c)
        if pencil:
            a = pencil.find_parent("a")
            if a and a.get("href"):
                open_url = urljoin(BASE_URL, a["href"])
        if not open_url:
            open_url = f"{EDIT_TT_URL}?ticket_id={tt_id}"

        rows.append({
            "tt_id": tt_id,
            "problem_category": cell(pc_idx),
            "open_url": open_url,
        })

    return rows


# ----------------------------------------------------------------------
# Generic multi-page search
# ----------------------------------------------------------------------
def _search_paged(session: requests.Session,
                  base_params: dict,
                  endpoint: str = PENDING_URL,
                  fetch_all_pages: bool = True,
                  max_pages: int = 50,
                  page_size: int = 20) -> list[dict]:
    if not fetch_all_pages:
        r = session.get(endpoint, params=base_params, timeout=30)
        r.raise_for_status()
        return _parse_ticket_table(r.text)

    all_rows: list[dict] = []
    seen_ids: set[str] = set()
    page = 1

    while page <= max_pages:
        params = {**base_params, "page": page}
        r = session.get(endpoint, params=params, timeout=30)
        r.raise_for_status()
        page_rows = _parse_ticket_table(r.text)

        if not page_rows:
            break

        new_count = 0
        for row in page_rows:
            if row["tt_id"] not in seen_ids:
                seen_ids.add(row["tt_id"])
                all_rows.append(row)
                new_count += 1

        if len(page_rows) < page_size or new_count == 0:
            break
        page += 1

    return all_rows


# ----------------------------------------------------------------------
# Portion 1 — STL pending (company=STL, no keyword)
# ----------------------------------------------------------------------
def search_stl_pending(session: requests.Session,
                       base_html: str | None = None,
                       fetch_all_pages: bool = True) -> list[dict]:
    if base_html is None:
        base_html = fetch_pending_page(session)

    hidden = _extract_hidden_fields(base_html)

    base_params = {
        **hidden,
        "company":            STL_COMPANY,
        "ticket_id":          "",
        "ticket_title":       "",
        "dashboard_value":    "pending_task",
        "ticket_status":      STATUS,
        "assigned_dept":      "",
        "assigned_subcenter": "",
        "client_id":          "",
        "problem_category":   "",
        "Search":             "Search",
    }
    return _search_paged(session, base_params,
                         endpoint=PENDING_URL,
                         fetch_all_pages=fetch_all_pages)


# ----------------------------------------------------------------------
# Portion 2 — Both Company · Client = Info-Sarkar-Ph3
# ----------------------------------------------------------------------
def search_both_info_sarkar(session: requests.Session,
                            base_html: str | None = None,
                            fetch_all_pages: bool = True) -> list[dict]:
    if base_html is None:
        base_html = fetch_pending_page(session)

    hidden = _extract_hidden_fields(base_html)

    base_params = {
        **hidden,
        "company":            BOTH_COMPANY,             # "" = Both
        "ticket_id":          "",
        "ticket_title":       "",
        "dashboard_value":    "pending_task",
        "ticket_status":      STATUS,
        "assigned_dept":      "",
        "assigned_subcenter": "",
        "client_id":          INFO_SARKAR_CLIENT,       # Info-Sarkar-Ph3
        "problem_category":   "",
        "Search":             "Search",
    }
    return _search_paged(session, base_params,
                         endpoint=PENDING_URL,
                         fetch_all_pages=fetch_all_pages)


# ----------------------------------------------------------------------
# Self-contained HTML buttons
# ----------------------------------------------------------------------
def _build_open_all_html(urls: list[str], label: str, cap: int) -> str:
    to_open = urls[:cap]
    urls_js = _json.dumps(to_open)

    js = (
        "const urls = " + urls_js + ";\n"
        "let opened = 0;\n"
        "for (const u of urls) {\n"
        "  const w = window.open(u, '_blank');\n"
        "  if (w) opened++;\n"
        "}\n"
        "const btn = this;\n"
        "const original = btn.innerText;\n"
        "btn.innerText = '\\u2705 Opened ' + opened + '/' + urls.length;\n"
        "setTimeout(() => btn.innerText = original, 2000);\n"
    )

    return (
        '<div style="display:flex;align-items:center;gap:8px;">'
        '<button '
        'onclick="' + js.replace('"', '&quot;') + '" '
        'style="padding:10px 18px;border-radius:8px;border:none;'
        'background:#0b7fd0;color:white;font-weight:700;'
        'cursor:pointer;font-size:14px;">'
        + label +
        '</button>'
        '<span style="color:#888;font-size:12px;">'
        '(If tabs don\'t open, allow popups for this page)'
        '</span>'
        '</div>'
    )


def open_all_button(urls: list[str], label: str = "🚀 Open All TTs",
                    cap: int = 50):
    if not urls:
        return
    components.html(_build_open_all_html(urls, label, cap),
                    height=60, scrolling=False)


def _build_copy_html(text: str, label: str) -> str:
    text_js = _json.dumps(text)
    label_js = _json.dumps(label)

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

    return (
        '<div style="display:flex;align-items:center;height:100%;">'
        '<button '
        'onclick="' + js.replace('"', '&quot;') + '" '
        'style="padding:8px 14px;border-radius:6px;border:none;'
        'background:#ff4b4b;color:white;font-weight:600;'
        'cursor:pointer;font-size:13px;white-space:nowrap;">'
        + label +
        '</button></div>'
    )


def copy_button(label: str, text: str, height: int = 46):
    components.html(_build_copy_html(text, label),
                    height=height, scrolling=False)


# ----------------------------------------------------------------------
# Reusable results renderer
# ----------------------------------------------------------------------
def _render_results(rows: list[dict], section_key: str):
    """
    Given a list of ticket dicts, render:
      * Open All + Copy all URLs buttons
      * One row per ticket with ✏️ Open
    `section_key` is used to make widget keys unique.
    """
    all_urls = [r["open_url"] for r in rows if r["open_url"]]

    colA, colB, colC = st.columns([2, 2, 3])
    with colA:
        cap = st.number_input(
            "Max tabs at once",
            min_value=1, max_value=300,
            value=min(50, max(1, len(all_urls))),
            step=5,
            key=f"cap_{section_key}",
        )
    with colB:
        st.write("")
        st.write("")
        open_all_button(
            all_urls,
            label=f"🚀 Open All ({len(all_urls)})",
            cap=int(cap),
        )
    with colC:
        st.write("")
        st.write("")
        copy_button("📋 Copy all URLs",
                    "\n".join(all_urls),
                    height=46)

    st.caption("First click may ask you to allow popups. "
               "Allow popups for `localhost:8501` once and this "
               "button will open every ticket in a new tab.")

    st.markdown("---")

    for r in rows:
        tt  = r["tt_id"]
        pc  = r["problem_category"] or "—"
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


# ----------------------------------------------------------------------
# Streamlit render
# ----------------------------------------------------------------------
def render():
    st.header("📨 Phoenix — Pending Task Scraper")
    st.caption("Fetch pending tickets from Phoenix. Two search options "
               "below.")

    # ---------- credentials ----------
    with st.sidebar.expander("🔐 Phoenix Credentials", expanded=False):
        username  = st.text_input("Username / Email", key="pt_user")
        password  = st.text_input("Password", type="password", key="pt_pass")
        user_type = st.selectbox("User Type", USER_TYPES,
                                 index=0, key="pt_utype")

    # ---------- two portions via tabs ----------
    tab1, tab2 = st.tabs([
        "📨 STL Pending Task",
        "👥 Both · Info-Sarkar-Ph3",
    ])

    # ================= Portion 1 =================
    with tab1:
        st.subheader("STL Pending Task")
        st.caption("Company = **STL**  ·  Status = **Not Closed**  ·  "
                   "No keyword needed.")

        run1 = st.button("🚀 Fetch STL Pending TTs",
                         type="primary", key="pt_stl_run")

        if run1:
            if not username or not password:
                st.error("Enter your Phoenix credentials in the sidebar.")
            else:
                session = _new_session()
                with st.spinner("Logging in…"):
                    try:
                        login(session, username, password, user_type)
                    except Exception as e:
                        st.error(f"❌ Login failed: {e}")
                        st.stop()

                with st.spinner("Opening Pending Task page…"):
                    try:
                        base_html = fetch_pending_page(session)
                    except Exception as e:
                        st.error(f"❌ Could not open Pending Task: {e}")
                        st.stop()

                with st.spinner("Fetching STL pending tickets…"):
                    try:
                        rows = search_stl_pending(session,
                                                  base_html=base_html,
                                                  fetch_all_pages=True)
                    except Exception as e:
                        st.error(f"❌ Search failed: {e}")
                        st.stop()

                st.session_state["pt_stl_rows"] = rows

        rows = st.session_state.get("pt_stl_rows")
        if rows is not None:
            if not rows:
                st.warning("No STL pending TT found.")
            else:
                st.success(f"✅ {len(rows)} STL pending TT(s) found")
                _render_results(rows, section_key="stl")

    # ================= Portion 2 =================
    with tab2:
        st.subheader("Both Company · Client = Info-Sarkar-Ph3")
        st.caption("Company = **Both**  ·  Client = **Info-Sarkar-Ph3**  ·  "
                   "Status = **Not Closed**  ·  No keyword needed.")

        run2 = st.button("🚀 Fetch Info-Sarkar-Ph3 TTs",
                         type="primary", key="pt_info_run")

        if run2:
            if not username or not password:
                st.error("Enter your Phoenix credentials in the sidebar.")
            else:
                session = _new_session()
                with st.spinner("Logging in…"):
                    try:
                        login(session, username, password, user_type)
                    except Exception as e:
                        st.error(f"❌ Login failed: {e}")
                        st.stop()

                with st.spinner("Opening Pending Task page…"):
                    try:
                        base_html = fetch_pending_page(session)
                    except Exception as e:
                        st.error(f"❌ Could not open Pending Task: {e}")
                        st.stop()

                with st.spinner("Fetching Info-Sarkar-Ph3 tickets…"):
                    try:
                        rows = search_both_info_sarkar(
                            session,
                            base_html=base_html,
                            fetch_all_pages=True,
                        )
                    except Exception as e:
                        st.error(f"❌ Search failed: {e}")
                        st.stop()

                st.session_state["pt_info_rows"] = rows

        rows = st.session_state.get("pt_info_rows")
        if rows is not None:
            if not rows:
                st.warning("No Info-Sarkar-Ph3 pending TT found.")
            else:
                st.success(f"✅ {len(rows)} Info-Sarkar-Ph3 TT(s) found")
                _render_results(rows, section_key="info")
