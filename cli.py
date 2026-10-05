# cli.py
import sys
from db_loader import DB_PATH
from search import DWDMDB


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    db = DWDMDB(path)
    print(f"Loaded {len(db.records)} records from {path}\n")

    while True:
        q = input("Enter path / link / node (q to quit): ").strip()
        if q.lower() in ("q", "quit", "exit"):
            break

        # 1) try as a path
        paths = db.search_path(q)
        printed = False
        for p in paths:
            links = db.get_path_links(p)
            if not links:
                continue
            printed = True
            print(f"\n=== {p} ===")
            print(f"{'Node A':<25}{'Node B':<25}{'Threshold':>10}")
            for r in links:
                thr = r["threshold"] if r["threshold"] is not None else ""
                print(f"{r['node_a']:<25}{r['node_b']:<25}{str(thr):>10}")

        if printed:
            continue

        # 2) fall back to link / node search
        results = db.search_link(q)
        if not results:
            print("  (no match)\n")
            continue
        print(f"\n{'Node A':<25}{'Node B':<25}{'Threshold':>10}   Sheet / Section")
        for r in results:
            thr = r["threshold"] if r["threshold"] is not None else ""
            print(f"{r['node_a']:<25}{r['node_b']:<25}{str(thr):>10}   "
                  f"[{r['sheet']} / {r['section']}]")


if __name__ == "__main__":
    main()
