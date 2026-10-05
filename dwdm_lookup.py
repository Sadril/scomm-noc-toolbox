# tools/dwdm_lookup.py
"""
Tool 1 — DWDM RSL Threshold Lookup.
Everything is inside render(); nothing runs at import time.
"""
import os
import tempfile
import pandas as pd
import streamlit as st

from db_loader import DB_PATH
from search import DWDMDB, find_threshold, lookup_ordered_links
from ocr_reader import extract_ordered_nodes


@st.cache_resource(show_spinner="Loading DWDM database…")
def _get_db(path: str):
    return DWDMDB(path)


def render():
    """Tool 1: DWDM RSL Threshold Lookup."""
    st.header("🔎 DWDM Links — RSL Threshold Lookup")

    # ---- database path control ----
    with st.sidebar.expander("⚙️ DWDM Database", expanded=False):
        db_path = st.text_input(
            "Excel file path",
            value=str(DB_PATH),
            key="dwdm_db_path",
        )
        if st.button("🔄 Reload DWDM database", key="dwdm_reload"):
            st.cache_resource.clear()

    try:
        db = _get_db(db_path)
        st.success(
            f"✅ {len(db.records)} link records · "
            f"{len(db.path_names)} paths · "
            f"{len(db.node_names)} nodes"
        )
    except Exception as e:
        st.error(f"Failed to load DB: {e}")
        return

    tab1, tab2, tab3 = st.tabs(
        ["📂 By Path", "🔗 By Link", "🖼️ By Snapshot (OCR)"]
    )

    # ---------- TAB 1 — PATH ----------
    with tab1:
        q = st.text_input(
            "Enter path name",
            placeholder="e.g. DHK-SYL (UG), PGCB, DHK-KUAKATA PGCB path",
            key="dwdm_path_q",
        )
        if q:
            matches = db.search_path(q)
            if not matches:
                st.warning("No matching path.")
            else:
                chosen = st.selectbox("Matching paths", matches,
                                      key="dwdm_path_sel")
                links = db.get_path_links(chosen)
                df = pd.DataFrame([{
                    "Node A": r["node_a"],
                    "Node B": r["node_b"],
                    "Threshold": r["threshold"] if r["threshold"] is not None else "",
                    "Sheet": r["sheet"],
                } for r in links])
                st.subheader(f"{chosen} — {len(df)} rows")
                st.dataframe(df, use_container_width=True, hide_index=True)

    # ---------- TAB 2 — LINK ----------
    with tab2:
        q = st.text_input(
            "Enter node or link",
            placeholder="DHPTNC01  or  DHPTNC01-NSSDRDS01",
            key="dwdm_link_q",
        )
        if q:
            results = db.search_link(q)
            if not results:
                st.warning("No matching link.")
            else:
                df = pd.DataFrame([{
                    "Node A": r["node_a"],
                    "Node B": r["node_b"],
                    "Threshold": r["threshold"] if r["threshold"] is not None else "",
                    "Path": r["section"],
                    "Sheet": r["sheet"],
                } for r in results])
                st.subheader(f"{len(df)} match(es)")
                st.dataframe(df, use_container_width=True, hide_index=True)

    # ---------- TAB 3 — SNAPSHOT ----------
    with tab3:
        st.write("Upload a topology diagram. Nodes are read **left → right**, "
                 "then **both directions** are looked up.")
        up = st.file_uploader(
            "Upload image",
            type=["png", "jpg", "jpeg", "bmp"],
            key="dwdm_img",
        )
        if up:
            with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=os.path.splitext(up.name)[1]) as f:
                f.write(up.read())
                tmp = f.name

            st.image(tmp, use_container_width=True)

            try:
                with st.spinner("Running OCR…"):
                    nodes, raw = extract_ordered_nodes(tmp)
            except Exception as e:
                st.error(f"OCR failed: {e}")
                st.info("Check that Tesseract is installed and "
                        "pytesseract.pytesseract.tesseract_cmd is set.")
                return

            st.markdown("**Detected node order (left → right)**")
            st.code(" → ".join(nodes) if nodes else "(none detected)")
            with st.expander("Raw OCR text"):
                st.code(raw)

            if len(nodes) >= 2:
                prefer_sheet = st.selectbox(
                    "Prefer this sheet (fallback still searches all others)",
                    ["(auto)"] + sorted({r["sheet"] for r in db.records}),
                    key="dwdm_prefer",
                )
                prefer_sheet = None if prefer_sheet == "(auto)" else prefer_sheet

                rows = lookup_ordered_links(db, nodes,
                                            prefer_sheet=prefer_sheet)
                df = pd.DataFrame(rows)

                def colour(row):
                    mt = row.get("_match", "")
                    if mt == "not-found":
                        return ["background-color:#ffd6d6"] * len(row)
                    if mt == "exact-any":
                        return ["background-color:#fff5cc"] * len(row)
                    if mt == "fuzzy":
                        return ["background-color:#e0d6ff"] * len(row)
                    return [""] * len(row)

                display = df[["Node A", "Node B", "Threshold",
                              "_sheet", "_match"]].rename(
                    columns={"_sheet": "Source Sheet",
                             "_match": "Match Type"})

                st.subheader(f"{len(df)} rows "
                             f"({len(df)//2} links × 2 directions)")
                st.dataframe(display.style.apply(colour, axis=1),
                             use_container_width=True, hide_index=True)
                st.caption("⬜ exact-preferred  🟨 exact-any  "
                           "🟪 fuzzy  🟥 not-found")

                csv = df[["Node A", "Node B", "Threshold"]] \
                        .to_csv(index=False).encode()
                st.download_button("⬇️ Download CSV", csv,
                                   "link_thresholds.csv",
                                   key="dwdm_csv")

                with st.expander("Show as Path-style (single row per hop)"):
                    path_rows = []
                    for a, b in zip(nodes, nodes[1:]):
                        pa = find_threshold(db, a, b,
                                            prefer_sheet=prefer_sheet)
                        pb = find_threshold(db, b, a,
                                            prefer_sheet=prefer_sheet)
                        path_rows.append({
                            "Node A": a,
                            "Node B": b,
                            "Threshold (A→B)": pa["threshold"]
                                if pa["threshold"] is not None else "",
                            "Threshold (B→A)": pb["threshold"]
                                if pb["threshold"] is not None else "",
                            "Path (A→B)": pa["section"] or "",
                            "Path (B→A)": pb["section"] or "",
                        })
                    st.dataframe(pd.DataFrame(path_rows),
                                 use_container_width=True,
                                 hide_index=True)
