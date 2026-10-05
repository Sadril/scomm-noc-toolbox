# tools/phoenix_tt.py
"""
Tool 2 — Phoenix Pending TT Scraper.

Logs into https://phoenix.summitcommunications.net/ via POST to
/authenticate with:
    username, password, user_type

Then opens the Pending Task page and runs three searches:
    * 'HTD'      → Company = Both
    * 'Huawei'   → Company = Both
    * 'Contains' → Company = SCOMM

Extracts every TT ID from <td class="hidden-xs">NNNNNNNNNN</td>
on the result page.
"""
from __future__ import annotations

import io
import os
import re
from urllib.parse import urljoin

import certifi
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


BASE_URL   = "https://phoenix.summitcommunications.net/"
LOGIN_PAGE = BASE_URL
AUTH_URL   = urljoin(BASE_URL, "authenticate")
PENDING_URL = urljoin(BASE_URL, "ViewTT?dashboard_value=pending_task")
EDIT_TT_URL = urljoin(BASE_URL, "EditTT")   # + "?ticket_id=<id>"

CA_BUNDLE = certifi.where()

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

SEARCHES = [
    {"keyword": "HTD",      "company": "",      "label": "HTD (Both)"},
    {"keyword": "Huawei",   "company": "",      "label": "Huawei (Both)"},
    {"keyword": "Contains", "company": "SCOMM", "label": "Contains (SComm)"},
]

USER_TYPES = ["default", "IIG", "ITC", "ICX"]

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
    """
    POST credentials to /authenticate.
    Returns the final URL after login. Raises on failure.
    """
    # Hit the login page first to set any cookies the site may need
    # (e.g. a Laravel session cookie — even without a CSRF token).
    r = session.get(LOGIN_PAGE, timeout=20)
    r.raise_for_status()

    payload = {
        "username":  username,
        "password":  password,
        "user_type": user_type,
    }

    r2 = session.post(AUTH_URL, data=payload,
                      timeout=20, allow_redirects=True)

    if r2.status_code >= 400:
        raise RuntimeError(
            f"Login POST to /authenticate returned HTTP {r2.status_code}. "
            f"URL after redirect: {r2.url}"
        )

    # Success test: the final URL should NOT contain 'login' or 'authenticate'.
    final_url_lower = r2.url.lower()
    if "login" in final_url_lower or "authenticate" in final_url_lower:
        raise RuntimeError(
            "Login rejected — still on login/authenticate page. "
            "Check username, password, and user_type. "
            f"Final URL: {r2.url}"
        )

    return r2.url


def fetch_pending_page(session: requests.Session) -> str:
    r = session.get(PENDING_URL, timeout=20)
    r.raise_for_status()
    return r.text


# ----------------------------------------------------------------------
# Search / extract
# ----------------------------------------------------------------------
def _extract_hidden_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    out = {}
    for tag in soup.find_all("input", {"type": "hidden"}):
        n = tag.get("name")
        if n:
            out[n] = tag.get("value", "")
    return out


def extract_tt_ids(html: str) -> list[dict]:
    """
    Return one dict per row:
        {"tt_id": "...", "problem_category": "...", "open_url": "..."}
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

    out: list[dict] = []
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

        out.append({
            "tt_id": tt_id,
            "problem_category": cell(pc_idx),
            "open_url": open_url,
        })

    return out


def search_pending(session: requests.Session,
                   keyword: str, company: str,
                   base_html: str | None = None) -> list[str]:
    """
    Submit the Pending Task search as a GET request, matching exactly
    what the browser sends:

      /ViewTT?company=&ticket_id=&ticket_title=HTD&dashboard_value=pending_task
              &ticket_status=not_closed&assigned_dept=&assigned_subcenter=
              &client_id=&problem_category=&Search=Search
    """
    params = {
        "company":            company or "",       # "" = Both, or SCOMM, or STL
        "ticket_id":          "",
        "ticket_title":       keyword,
        "dashboard_value":    "pending_task",
        "ticket_status":      "not_closed",
        "assigned_dept":      "",
        "assigned_subcenter": "",
        "client_id":          "",
        "problem_category":   "",
        "Search":             "Search",
    }

    r = session.get(PENDING_URL, params=params, timeout=20)
    r.raise_for_status()
    return extract_tt_ids(r.text)


# ----------------------------------------------------------------------
# Streamlit render
# ----------------------------------------------------------------------
def render():
    st.header("📨 Phoenix — Pending TT Scraper")
    st.caption(
        "Logs into phoenix.summitcommunications.net, opens Pending Task, "
        "and runs the three predefined searches: "
        "**HTD** (Both), **Huawei** (Both), **Contains** (SComm)."
    )

    # ---------- credentials ----------
    with st.sidebar.expander("🔐 Phoenix Credentials", expanded=False):
        username = st.text_input("Username / Email", key="phx_user")
        password = st.text_input("Password", type="password", key="phx_pass")
        user_type = st.selectbox("User Type", USER_TYPES,
                                 index=0, key="phx_utype")
        st.caption("Credentials stay in this browser session only — "
                   "never written to disk.")

    # ---------- info ----------
    with st.sidebar.expander("🔍 Searches", expanded=True):
        for s in SEARCHES:
            st.write(f"• **{s['keyword']}** — Company: "
                     f"`{s['company'] or 'Both'}`")

    # ---------- run ----------
    run = st.button("🚀 Fetch Pending TTs", type="primary", key="phx_run")

    if not run:
        st.info("Enter your Phoenix credentials in the sidebar and "
                "click **Fetch Pending TTs**.")
        return

    if not username or not password:
        st.error("Please enter your Phoenix username and password.")
        return

    session = _new_session()

    with st.spinner("Logging in…"):
        try:
            final_url = login(session, username, password, user_type)
        except Exception as e:
            st.error(f"❌ Login failed: {e}")
            return
    st.success(f"✅ Logged in. (redirected to {final_url})")

    with st.spinner("Opening Pending Task page…"):
        try:
            base_html = fetch_pending_page(session)
        except Exception as e:
            st.error(f"❌ Could not open Pending Task: {e}")
            return

    # ---------- searches ----------
    results: dict[str, list[str]] = {}
    for s in SEARCHES:
        with st.spinner(f"Searching: {s['label']}…"):
            try:
                ids = search_pending(session,
                                     s["keyword"], s["company"],
                                     base_html=base_html)
            except Exception as e:
                st.warning(f"⚠️ '{s['label']}' failed: {e}")
                ids = []
        results[s["label"]] = ids

    # ---------------- results by search ----------------
    st.subheader("Results by search")
    for label, rows in results.items():
        if not rows:
            st.markdown(f"**{label}** — *(no TT IDs found)*")
            continue

        st.markdown(f"**{label}** — {len(rows)} TT(s)")
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

    # ---------------- combined summary ----------------
    all_rows: list[dict] = []
    seen_all: set[str] = set()
    for label, rows in results.items():
        for r in rows:
            tt_id = r["tt_id"]
            if tt_id not in seen_all:
                seen_all.add(tt_id)
                all_rows.append({
                    "Search": label,
                    "TT ID": tt_id,
                    "Problem Category": r["problem_category"],
                    "Open URL": r["open_url"],
                })

    st.subheader(f"📋 All unique TT IDs ({len(all_rows)})")
    if all_rows:
        st.code(", ".join(r["TT ID"] for r in all_rows))

        df = pd.DataFrame(all_rows)

        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        xlsx_buf = io.BytesIO()
        with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="PendingTTs")
        xlsx_buf.seek(0)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ Download CSV", csv_bytes,
                               "phoenix_pending_tts.csv",
                               key="phx_dl_csv")
        with c2:
            st.download_button("⬇️ Download Excel", xlsx_buf,
                               "phoenix_pending_tts.xlsx",
                               key="phx_dl_xlsx")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Open URL": st.column_config.LinkColumn(
                    "Open", display_text="✏️ Open"
                ),
            },
        )
    else:
        st.warning("No TT IDs found in any search.")
