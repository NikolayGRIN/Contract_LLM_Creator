from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


# ---------------------------
# helpers
# ---------------------------
def normalize_title(title: str) -> str:
    """
    Normalize section titles for statistics.
    """
    if not title:
        return ""

    title = title.strip()
    title = re.sub(r"№\s*(\d+)", r"№ \1", title)
    return title


def first_word_after_numbering(title: str) -> str:
    """
    Extract first word after numbering like:
    '1. Replace goods' -> 'replace'
    '2) Deliver goods' -> 'deliver'
    """
    if not title:
        return ""

    s = title.strip().lower()
    s = re.sub(r"^\d+(\.\d+)*[.)]\s*", "", s)
    return s.split(" ", 1)[0] if s else ""


# ---------------------------
# main analysis
# ---------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Analyze segmentation results produced by clean_and_segment.py"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Folder with *.json files produced by segmentation",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Top N section titles to display",
    )
    parser.add_argument(
        "--export-csv",
        default="",
        help="Optional path to export CSV with section title frequencies",
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input folder not found: {input_dir}")

    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in: {input_dir}")

    docs_count = 0
    total_sections = 0
    empty_sections = 0
    full_text_fallback = 0

    sections_per_doc = []
    title_counter = Counter()
    title_upper_counter = Counter()
    suspicious_first_words = Counter()

    docs_with_few_sections = []
    docs_with_many_sections = []

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Cannot read {fp.name}: {e}")
            continue

        sections = data.get("sections", [])
        n_sections = 0

        for sec in sections:
            title = normalize_title(sec.get("section", ""))
            text = (sec.get("text") or "").strip()

            if not text:
                empty_sections += 1
                continue

            n_sections += 1
            title_counter[title] += 1
            title_upper_counter[title.upper()] += 1

            if title.upper() == "FULL_TEXT":
                full_text_fallback += 1

            # collect suspicious first words for numbered titles
            if re.match(r"^\d+(\.\d+)*[.)]\s+", title):
                w = first_word_after_numbering(title)
                if w:
                    suspicious_first_words[w] += 1

        docs_count += 1
        total_sections += n_sections
        sections_per_doc.append(n_sections)

        if n_sections <= 2:
            docs_with_few_sections.append((fp.name, n_sections))
        if n_sections >= 40:
            docs_with_many_sections.append((fp.name, n_sections))

    sections_per_doc.sort()
    avg = total_sections / docs_count if docs_count else 0
    median = sections_per_doc[len(sections_per_doc) // 2] if sections_per_doc else 0
    min_n = sections_per_doc[0] if sections_per_doc else 0
    max_n = sections_per_doc[-1] if sections_per_doc else 0

    # ---------------------------
    # report
    # ---------------------------
    print("\n=== SEGMENTATION QUALITY REPORT ===")
    print(f"Input folder: {input_dir}")
    print(f"Documents analyzed: {docs_count}")
    print(f"Total non-empty sections: {total_sections}")
    print(f"Average sections / doc: {avg:.2f}")
    print(f"Median sections / doc: {median}")
    print(f"Min sections / doc: {min_n}")
    print(f"Max sections / doc: {max_n}")
    print(f"FULL_TEXT fallback sections: {full_text_fallback}")
    print(f"Empty sections skipped: {empty_sections}")

    print(f"\nTop {args.top} section titles (as-is):")
    for title, cnt in title_counter.most_common(args.top):
        print(f"{cnt:>5}  {title}")

    print(f"\nTop {args.top} section titles (UPPER normalized):")
    for title, cnt in title_upper_counter.most_common(args.top):
        print(f"{cnt:>5}  {title}")

    print("\nTop first words of numbered titles (candidates for ACTION_VERBS):")
    for word, cnt in suspicious_first_words.most_common(30):
        print(f"{cnt:>5}  {word}")

    if docs_with_few_sections:
        print("\nDocuments with <= 2 sections (possible segmentation failure):")
        for name, n in docs_with_few_sections[:20]:
            print(f"  {n:>2}  {name}")
        if len(docs_with_few_sections) > 20:
            print(f"  ... and {len(docs_with_few_sections) - 20} more")

    if docs_with_many_sections:
        print("\nDocuments with >= 40 sections (possible over-segmentation):")
        for name, n in docs_with_many_sections[:20]:
            print(f"  {n:>2}  {name}")
        if len(docs_with_many_sections) > 20:
            print(f"  ... and {len(docs_with_many_sections) - 20} more")

    # ---------------------------
    # CSV export
    # ---------------------------
    if args.export_csv:
        out_csv = Path(args.export_csv)
        lines = ["section_title,count\n"]
        for title, cnt in title_upper_counter.most_common():
            safe = title.replace('"', '""')
            lines.append(f"\"{safe}\",{cnt}\n")

        out_csv.write_text("".join(lines), encoding="utf-8")
        print(f"\nSaved CSV report to: {out_csv}")


if __name__ == "__main__":
    main()
