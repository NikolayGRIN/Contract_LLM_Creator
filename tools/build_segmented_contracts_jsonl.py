import argparse
import json
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments_csv", required=True)
    ap.add_argument("--out_jsonl", required=True)
    ap.add_argument("--segments_delim", default=",")
    ap.add_argument("--source", default="docx", help="docx|json|any")
    args = ap.parse_args()

    seg = pd.read_csv(
        args.segments_csv,
        sep=args.segments_delim,
        dtype=str,
        engine="python",
        quoting=3,
        on_bad_lines="skip"
    ).fillna("")

    required_cols = {"contract_id", "order", "section_title", "section_id", "text", "source"}
    missing = required_cols - set(seg.columns)
    if missing:
        raise SystemExit(f"segments_csv missing columns: {sorted(missing)}. Found: {list(seg.columns)}")

    if args.source != "any":
        seg = seg[seg["source"] == args.source]

    eligible_contracts = set(seg["contract_id"].astype(str).unique())
    if not eligible_contracts:
        raise SystemExit("No contracts found in segments.csv after filtering.")

    def safe_int(x: str) -> int:
        try:
            return int(float(x))
        except Exception:
            return 0

    seg["order_key"] = seg["order"].astype(str).apply(safe_int)
    seg = seg.sort_values(["contract_id", "order_key"], ascending=True)

    out_count = 0
    with open(args.out_jsonl, "w", encoding="utf-8") as f:
        for cid, grp in seg.groupby("contract_id", sort=False):
            sections = [
                {"section_id": r["section_id"], "title": r["section_title"], "text": r["text"]}
                for _, r in grp.iterrows()
            ]
            f.write(json.dumps({"contract_id": str(cid), "source": args.source, "sections": sections}, ensure_ascii=False) + "\n")
            out_count += 1

    print(f"OK. Eligible contracts: {len(eligible_contracts)}")
    print(f"Wrote JSONL contracts: {out_count}")
    print(f"Output: {args.out_jsonl}")


if __name__ == "__main__":
    main()
