# db_loader.py
"""
Parses the DWDM OMS Threshold Excel into a flat list of link records.

Strategy:
  * A block starts every time we see a header row
        'S/N | Node A | Node B | Threshold'
    (or 'From Site A | To Site B | ...').
  * A block ends at the next header row OR at a fully blank row.
  * The section title is the last non-empty text cell in column B
    *before* the header. If no title is available we generate
        '<sheet> #N'   (N = block index inside the sheet).
  * Free-standing rows after a block (no header) get their own section.
  * 'OLP Threshold' sheet has its own column layout and is handled
    separately.
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

# Anchor to the folder that contains THIS file — never depends on
# where Streamlit was launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = _PROJECT_ROOT / "data" / "DWDM links OMS Threshold Database.xlsx"

# --------------------------------------------------------------
# Optional spell-fix layer. Extend this dict if you find typos.
# Keys are lowercase, values are the canonical spelling.
# --------------------------------------------------------------
SPELL_FIXES: dict[str, str] = {
    # "dhptnc0l": "DHPTNC01",
    # "nssdrdso1": "NSSDRDS01",
}

def _apply_spell_fix(name: str) -> str:
    if not name:
        return name
    return SPELL_FIXES.get(name.strip().lower(), name)


# --------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------
_TAG_RE = re.compile(r"\(.*?\)")
_TRAIL_NUM_RE = re.compile(r"_\d+$")
_WS_RE = re.compile(r"\s+")


def normalise_node(name: str) -> str:
    """
    Lower-case, strip (...) tags, drop Working/Protection/OH/UG/BR/PGCB,
    drop trailing _N, collapse whitespace. Used for cross-sheet matching.
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    s = str(name).lower().strip()
    s = _TAG_RE.sub("", s)
    s = re.sub(r"\b(working|protection|oh|ug|br|pgcb)\b", "", s)
    s = _TRAIL_NUM_RE.sub("", s)
    return _WS_RE.sub(" ", s).strip()


def _clean(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return _WS_RE.sub(" ", str(s)).strip()


def _to_float(x):
    """Return float if convertible, else the original string (e.g. 'Not Found')."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return s


# --------------------------------------------------------------
# Sheet priority (lower index wins on duplicate links)
# --------------------------------------------------------------
SHEET_PRIORITY = [
    "Dhaka-Sylhet",
    "DHK-CTG-COX",
    "DHAKA-BENAPOLE",
    "DHAKA-KUAKATA",
    "DHK-MYM",
    "DHK-BOGURA-RANGPUR",
    "OLP Threshold",
]


def sheet_rank(sheet_name: str) -> int:
    return SHEET_PRIORITY.index(sheet_name) if sheet_name in SHEET_PRIORITY \
           else len(SHEET_PRIORITY)


# --------------------------------------------------------------
# Row / header / blank detection
# --------------------------------------------------------------
_HEADER_TOKENS = {"s/n", "sn", "from site a", "node a"}


def _is_header_row(row) -> bool:
    return _clean(row.iloc[0]).lower() in _HEADER_TOKENS


def _is_blank_row(row) -> bool:
    return all(_clean(c) == "" for c in row.tolist())


def _row_title(row) -> str:
    """Best-effort section title: first non-empty text cell in cols B/C/A."""
    for idx in (1, 2, 0):
        if idx < len(row):
            v = _clean(row.iloc[idx])
            if v and not v.isdigit():
                # skip the header words themselves
                if v.lower() in _HEADER_TOKENS:
                    continue
                return v
    return ""


# --------------------------------------------------------------
# Row parser
# --------------------------------------------------------------
def _parse_row(row):
    """
    Extract (node_a, node_b, threshold, rsl, extra) or None.
    Handles:
      * standard:  [SN?] NodeA | NodeB | Threshold | RSL | extra
      * header-less rows (no SN)
    """
    if _is_header_row(row) or _is_blank_row(row):
        return None

    cells = [_clean(c) for c in row.tolist()]
    while len(cells) < 5:
        cells.append("")

    col0 = cells[0]
    if col0 == "" or col0.isdigit():
        a, b = cells[1], cells[2]
        thr, rsl = cells[3], cells[4]
        extra = cells[5] if len(cells) > 5 else ""
    else:
        a, b = cells[0], cells[1]
        thr, rsl = cells[2], cells[3]
        extra = cells[4] if len(cells) > 4 else ""

    if not a or not b:
        return None

    # reject rows that are actually headers
    if a.lower() in _HEADER_TOKENS or b.lower() in _HEADER_TOKENS:
        return None

    return dict(node_a=a, node_b=b,
                threshold=_to_float(thr),
                current_rsl=_to_float(rsl) if rsl else None,
                extra=extra)


# --------------------------------------------------------------
# Main loader
# --------------------------------------------------------------
def load_database(path: Path = DB_PATH):
    xls = pd.ExcelFile(path)
    records = []

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet_name, header=None)

        # ---------------- OLP sheet (different layout) ----------------
        if sheet_name.lower().startswith("olp"):
            for _, row in df.iterrows():
                cells = [_clean(c) for c in row.tolist()]
                if not cells or not cells[0]:
                    continue
                if cells[0].lower().startswith("from site"):
                    continue
                a = cells[0]
                b = cells[1] if len(cells) > 1 else ""
                fiber = cells[2] if len(cells) > 2 else ""
                thr = cells[3] if len(cells) > 3 else ""
                if a and b:
                    records.append(dict(
                        sheet=sheet_name, section="OLP Threshold",
                        node_a=a, node_b=b,
                        threshold=_to_float(thr),
                        current_rsl=None,
                        fiber_path=fiber,
                        extra="",
                    ))
            continue

        # ---------------- Generic sheets ----------------
        current_title = ""     # title of the block we are inside (or about to enter)
        block_idx = 0          # counts blocks inside this sheet
        in_block = False       # True after a header row has been seen

        for _, row in df.iterrows():
            # -- new block header --
            if _is_header_row(row):
                block_idx += 1
                if not current_title:
                    current_title = f"{sheet_name} #{block_idx}"
                in_block = True
                continue

            # -- blank row = end of block --
            if _is_blank_row(row):
                in_block = False
                current_title = ""      # reset, next block starts fresh
                continue

            parsed = _parse_row(row)

            # -- non-link row: maybe a title --
            if parsed is None:
                if not in_block:
                    t = _row_title(row)
                    if t:
                        current_title = t
                continue

            # -- free-standing link (no preceding header) --
            if not in_block:
                block_idx += 1
                if not current_title:
                    current_title = f"{sheet_name} #{block_idx}"
                in_block = True

            records.append(dict(
                sheet=sheet_name,
                section=current_title,
                node_a=_apply_spell_fix(parsed["node_a"]),
                node_b=_apply_spell_fix(parsed["node_b"]),
                threshold=parsed["threshold"],
                current_rsl=parsed["current_rsl"],
                fiber_path="",
                extra=parsed["extra"],
            ))

    # attach normalised keys
    for r in records:
        r["_norm_a"] = normalise_node(r["node_a"])
        r["_norm_b"] = normalise_node(r["node_b"])

    return records


# --------------------------------------------------------------
# Index
# --------------------------------------------------------------
def build_index(records):
    by_path, by_link, by_node = {}, {}, {}
    for r in records:
        by_path.setdefault(r["section"], []).append(r)

        key = (r["_norm_a"], r["_norm_b"])
        by_link.setdefault(key, []).append(r)

        by_node.setdefault(r["_norm_a"], []).append(r)
        by_node.setdefault(r["_norm_b"], []).append(r)

    return by_path, by_link, by_node
