#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True, help="CSV/TSV with rows = (contract_id, section_id, text[, title, order])")
    ap.add_argument("--titles_map", required=True, help="section_titles_map.csv with columns: section_id,title[,count]")
    ap.add_argument("--out", required=True, help="Output JSONL path, e.g. data/segmented_contracts.jsonl")
    ap.add_argument("--sep", default=",", help="Delimiter for segments file (default ','). Use '\\t' for TSV.")
    args = ap.parse_args()

    # 1) read inputs
    seg = pd.read_csv(args.segments, sep=args.sep, dtype=str).fillna("")
    title_map = pd.read_csv(args.titles_map, dtype=str).fillna("")

    required_cols = {"contract_id", "section_id", "text"}
    missing = required_cols - set(seg.columns)
    if missing:
        raise SystemExit(f"segments file missing required columns: {sorted(missing)}")

    if "title" not in seg.columns:
        seg["title"] = ""

    # optional ordering column
    if "order" not in seg.columns:
        # if you have page/line indices, you can use them here instead
        seg["order"] = "0"

    # 2) join titles map (fills empty titles)
    title_map = title_map.rename(columns={"title": "mapped_title"})
    seg = seg.merge(title_map[["section_id", "mapped_title"]], on="section_id", how="left")
    seg["mapped_title"] = seg["mapped_title"].fillna("")
    seg["final_title"] = seg["title"].where(seg["title"].str.strip() != "", seg["mapped_title"])

    # 3) sort and group by contract
    # order can be numeric-like; try to sort safely
    def safe_int(x):
        try:
            return int(float(x))
        except Exception:
            return 0

    seg["order_key"] = seg["order"].apply(safe_int)
    seg = seg.sort_values(["contract_id", "order_key", "section_id"], ascending=True)

    # 4) write JSONL: one line per contract
    with open(args.out, "w", encoding="utf-8") as f:
        for contract_id, grp in seg.groupby("contract_id", sort=False):
            sections = []
            for _, r in grp.iterrows():
                sections.append({
                    "section_id": r["section_id"],
                    "title": r["final_title"],
                    "text": r["text"]
                })
            obj = {"contract_id": contract_id, "sections": sections}
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"OK: wrote {seg['contract_id'].nunique()} contracts to {args.out}")


if __name__ == "__main__":
    main()
