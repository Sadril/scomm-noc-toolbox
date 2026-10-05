# search.py
from __future__ import annotations
from rapidfuzz import process, fuzz
from db_loader import (
    load_database, build_index, normalise_node, sheet_rank, DB_PATH,
)


class DWDMDB:
    def __init__(self, path=None):
        self.records = load_database(path) if path else load_database()
        self.by_path, self.by_link, self.by_node = build_index(self.records)
        self.path_names = sorted(self.by_path.keys())
        self.node_names = sorted({r["node_a"] for r in self.records} |
                                 {r["node_b"] for r in self.records})

    # ---------------- PATH ----------------
    def search_path(self, query, limit=10, min_score=70):
        """
        Precise path search:
          1. exact case-insensitive match
          2. substring match
          3. strict fuzzy (ratio >= min_score)
        """
        q = query.strip().lower()
        if not q:
            return []

        exact = [p for p in self.path_names if p.lower() == q]
        if exact:
            return exact

        contains = [p for p in self.path_names if q in p.lower()]
        if contains:
            return contains

        matches = process.extract(query, self.path_names,
                                  scorer=fuzz.ratio, limit=limit)
        return [m[0] for m in matches if m[1] >= min_score]

    def get_path_links(self, path_name):
        """Case-insensitive section lookup."""
        if path_name in self.by_path:
            return self.by_path[path_name]
        pl = path_name.lower()
        for k, v in self.by_path.items():
            if k.lower() == pl:
                return v
        return []

    # ---------------- LINK ----------------
    def search_link(self, query, limit=20, min_score=70):
        """
        Search by 'A-B' or 'A B' or 'A→B' or a single node name.
        """
        q = query.replace("->", "-").replace("→", "-")
        parts = [p.strip() for p in q.split("-") if p.strip()]
        if len(parts) == 2:
            a, b = normalise_node(parts[0]), normalise_node(parts[1])
            hits = self.by_link.get((a, b), []) + self.by_link.get((b, a), [])
            if hits:
                # dedupe while preserving order
                seen, out = set(), []
                for r in hits:
                    key = (r["sheet"], r["section"],
                           r["_norm_a"], r["_norm_b"])
                    if key not in seen:
                        seen.add(key)
                        out.append(r)
                return out

        matches = process.extract(query, self.node_names,
                                  scorer=fuzz.partial_ratio, limit=limit)
        best = {normalise_node(m[0]) for m in matches if m[1] >= min_score}
        return [r for r in self.records
                if r["_norm_a"] in best or r["_norm_b"] in best]


# --------------------------------------------------------------
# Cross-sheet fallback lookup
# --------------------------------------------------------------
def find_threshold(db: DWDMDB, node_a: str, node_b: str,
                   prefer_sheet: str | None = None,
                   prefer_section: str | None = None):
    """
    Resolution order:
      1. Exact match in (prefer_sheet, prefer_section)
      2. Exact match in prefer_sheet (any section)
      3. Exact match in any sheet, ordered by SHEET_PRIORITY
      4. Fuzzy match on node names across all sheets
      5. Not found
    """
    na, nb = normalise_node(node_a), normalise_node(node_b)
    hits = db.by_link.get((na, nb), [])

    def sort_key(rec):
        sheet_pen = 0 if (prefer_sheet and rec["sheet"] == prefer_sheet) else 1
        sec_pen = 0 if (prefer_section and rec["section"] == prefer_section) else 1
        return (sheet_pen, sec_pen, sheet_rank(rec["sheet"]))

    if hits:
        hits_sorted = sorted(hits, key=sort_key)
        best = hits_sorted[0]
        mt = ("exact-preferred"
              if (prefer_sheet and best["sheet"] == prefer_sheet)
              else "exact-any")
        return {
            "threshold": best["threshold"],
            "sheet": best["sheet"],
            "section": best["section"],
            "match_type": mt,
            "alternatives": [
                {"sheet": h["sheet"], "section": h["section"],
                 "threshold": h["threshold"]}
                for h in hits_sorted[1:]
            ],
        }

    # fuzzy fallback
    ma = process.extractOne(node_a, db.node_names, scorer=fuzz.ratio)
    mb = process.extractOne(node_b, db.node_names, scorer=fuzz.ratio)
    if ma and mb and ma[1] >= 80 and mb[1] >= 80:
        fkey = (normalise_node(ma[0]), normalise_node(mb[0]))
        fhits = db.by_link.get(fkey, [])
        if fhits:
            best = sorted(fhits, key=lambda r: sheet_rank(r["sheet"]))[0]
            return {
                "threshold": best["threshold"],
                "sheet": best["sheet"],
                "section": best["section"],
                "match_type": "fuzzy",
                "alternatives": [
                    {"sheet": h["sheet"], "section": h["section"],
                     "threshold": h["threshold"]}
                    for h in fhits[1:]
                ],
            }

    return {"threshold": None, "sheet": None, "section": None,
            "match_type": "not-found", "alternatives": []}


# --------------------------------------------------------------
# Ordered-node → two rows per link (Excel layout)
# --------------------------------------------------------------
def lookup_ordered_links(db: DWDMDB, ordered_nodes,
                         fuzzy_threshold: int = 80,
                         prefer_sheet: str | None = None,
                         prefer_section: str | None = None):
    """
    Given an ordered list of node names, emit TWO rows per hop
    (A→B and B→A) with columns: Node A, Node B, Threshold.
    """
    canonical = []
    for tok in ordered_nodes:
        m = process.extractOne(tok, db.node_names, scorer=fuzz.ratio)
        canonical.append(m[0] if m and m[1] >= fuzzy_threshold
                         else f"<UNMATCHED:{tok}>")

    rows = []
    for a, b in zip(canonical, canonical[1:]):
        fwd = find_threshold(db, a, b,
                             prefer_sheet=prefer_sheet,
                             prefer_section=prefer_section)
        rows.append({"Node A": a, "Node B": b,
                     "Threshold": "" if fwd["threshold"] is None
                                  else fwd["threshold"],
                     "_sheet": fwd["sheet"] or "",
                     "_match": fwd["match_type"]})

        rev = find_threshold(db, b, a,
                             prefer_sheet=prefer_sheet,
                             prefer_section=prefer_section)
        rows.append({"Node A": b, "Node B": a,
                     "Threshold": "" if rev["threshold"] is None
                                  else rev["threshold"],
                     "_sheet": rev["sheet"] or "",
                     "_match": rev["match_type"]})
    return rows
