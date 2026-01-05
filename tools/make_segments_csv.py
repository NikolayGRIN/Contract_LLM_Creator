#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build segments.csv from:
- DOCX contracts (heading-based segmentation)
- JSON contracts (tries to detect existing segmentation structures)

Outputs: data/segments.csv with columns:
contract_id, order, section_title, section_id, text, source, confidence

PowerShell run:
python tools/make_segments_csv.py --docx_dir data/contracts_docx --json_dir data/contracts_json --titles_map data/section_titles_map.csv --out data/segments.csv
"""

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from docx import Document  # python-docx


# ---------------------------
# Helpers
# ---------------------------

def norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    # убираем типичные "1.", "1.1", "SECTION 1" в начале
    s = re.sub(r"^(\(?\s*(section|раздел)\s*)?\s*\d+(\.\d+)*[\)\.\-:]?\s*", "", s, flags=re.IGNORECASE)
    return s.strip()

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def looks_like_heading_text(text: str) -> bool:
    """Fallback heading heuristic for DOCX when styles are not reliable."""
    t = norm(text)
    if not t:
        return False
    if len(t) > 120:
        return False
    # must contain letters
    if not re.search(r"[A-Za-zА-Яа-я]", t):
        return False
    # typical heading keywords
    if re.search(r"\b(предмет|оплата|поставка|ответственност|арбитраж|споры|право|гаранти|форс|реквизит|definitions|subject|payment|delivery|liability|arbitration|governing law|warranty|force majeure|signatures)\b", t, re.IGNORECASE):
        return True
    # all caps short lines often headings
    if t.isupper() and len(t) <= 80:
        return True
    return False

def docx_paragraph_is_heading(p) -> bool:
    """Prefer Word styles (Heading 1/2/3 etc.)."""
    style_name = (p.style.name or "") if p.style else ""
    if style_name:
        if "Heading" in style_name or "Заголовок" in style_name:
            return True
    # fallback: bold + short
    txt = p.text.strip()
    if not txt:
        return False
    if len(txt) <= 120:
        # if most runs are bold
        runs = [r for r in p.runs if r.text and r.text.strip()]
        if runs:
            bold_ratio = sum(1 for r in runs if r.bold) / len(runs)
            if bold_ratio >= 0.7 and looks_like_heading_text(txt):
                return True
    return looks_like_heading_text(txt)

# ---------------------------
# Title map (section_titles_map.csv)
# ---------------------------

@dataclass
class TitleMap:
    title_to_id: Dict[str, str]
    id_to_title: Dict[str, str]

def load_titles_map(path: str) -> TitleMap:
    """
    Expect CSV with at least columns: section_id,title
    (your file also has count - ok)
    """
    title_to_id: Dict[str, str] = {}
    id_to_title: Dict[str, str] = {}

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("titles_map: empty CSV header")
        if "section_id" not in reader.fieldnames or "title" not in reader.fieldnames:
            raise ValueError(f"titles_map must contain columns section_id,title. Found: {reader.fieldnames}")

        for row in reader:
            sid = (row.get("section_id") or "").strip()
            title = norm(row.get("title") or "")
            if not sid or not title:
                continue
            title_to_id[title.lower()] = sid
            # keep the first seen title as canonical display
            if sid not in id_to_title:
                id_to_title[sid] = title

    return TitleMap(title_to_id=title_to_id, id_to_title=id_to_title)

_MAP_CACHE: Dict[str, Tuple[Optional[str], float]] = {}

def map_title_to_section_id(title: str, tmap: TitleMap, min_sim: float = 0.78) -> Tuple[Optional[str], float]:
    """
    Fast mapping heading/title -> section_id using:
    1) exact normalized match
    2) cached fuzzy match with candidate filtering (by first char + length window)
    """
    nt = norm(title)
    if not nt:
        return None, 0.0

    key = nt.lower()
    cached = _MAP_CACHE.get(key)
    if cached:
        return cached

    # 1) exact
    exact = tmap.title_to_id.get(key)
    if exact:
        _MAP_CACHE[key] = (exact, 1.0)
        return exact, 1.0

    # 2) filtered candidates for fuzzy
    first = key[0]
    L = len(key)

    # Build candidates list once per call by filtering keys
    # Filter rules:
    # - same first character
    # - length within +- 40%
    cand_keys = []
    lo = int(L * 0.6)
    hi = int(L * 1.4)

    for known_title_lower in tmap.title_to_id.keys():
        if not known_title_lower:
            continue
        if known_title_lower[0] != first:
            continue
        lk = len(known_title_lower)
        if lk < lo or lk > hi:
            continue
        cand_keys.append(known_title_lower)

    # If too few candidates, relax first-char constraint
    if len(cand_keys) < 20:
        cand_keys = []
        for known_title_lower in tmap.title_to_id.keys():
            lk = len(known_title_lower)
            if lk < lo or lk > hi:
                continue
            cand_keys.append(known_title_lower)

    best_sid, best_score = None, 0.0
    for known_title_lower in cand_keys:
        sc = similarity(nt, known_title_lower)
        if sc > best_score:
            best_score = sc
            best_sid = tmap.title_to_id[known_title_lower]

    if best_score >= min_sim:
        out = (best_sid, float(best_score))
    else:
        out = (None, float(best_score))

    _MAP_CACHE[key] = out
    return out

# ---------------------------
# DOCX segmentation
# ---------------------------

def segment_docx(path: str) -> List[Tuple[str, str]]:
    """
    Returns list of (section_title, section_text) extracted from DOCX.
    Heuristic: treat headings as boundaries.
    """
    doc = Document(path)
    segments: List[Tuple[str, str]] = []

    current_title: Optional[str] = None
    buf: List[str] = []

    def flush():
        nonlocal current_title, buf
        text = "\n".join([b.strip() for b in buf if b.strip()]).strip()
        if current_title and text:
            segments.append((current_title.strip(), text))
        buf = []

    for p in doc.paragraphs:
        txt = (p.text or "").strip()
        if not txt:
            continue

        if docx_paragraph_is_heading(p):
            flush()
            current_title = txt
        else:
            # if no title yet, treat as preface/body before first heading
            if current_title is None:
                current_title = "PREFACE"
            buf.append(txt)

    flush()
    return segments

# ---------------------------
# JSON parsing
# ---------------------------

def try_extract_segments_from_json(obj) -> Optional[List[Tuple[str, str]]]:
    """
    Attempts common structures:
    1) {"sections":[{"title":...,"text":...}, ...]}
    2) {"segments":[{"title":...,"text":...}, ...]}
    3) list of sections directly
    4) {"clauses":[{"heading":...,"content":...}]}
    Returns list of (title, text) or None if can't detect.
    """
    candidates = None
    if isinstance(obj, dict):
        for key in ["sections", "segments", "clauses", "items"]:
            if key in obj and isinstance(obj[key], list):
                candidates = obj[key]
                break
    elif isinstance(obj, list):
        candidates = obj

    if not isinstance(candidates, list):
        return None

    out: List[Tuple[str, str]] = []
    for it in candidates:
        if not isinstance(it, dict):
            continue
        title = it.get("title") or it.get("section_title") or it.get("heading") or it.get("name") or ""
        text = it.get("text") or it.get("content") or it.get("body") or ""
        title = str(title).strip()
        text = str(text).strip()
        if title and text:
            out.append((title, text))

    return out or None

# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx_dir", required=True)
    ap.add_argument("--json_dir", required=True)
    ap.add_argument("--titles_map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min_similarity", type=float, default=0.78)
    args = ap.parse_args()

    tmap = load_titles_map(args.titles_map)

    rows = []
    report = []
    total_attempted = 0

    def add_contract(contract_id: str, segments: List[Tuple[str, str]], source: str):
        nonlocal rows
        for idx, (title, text) in enumerate(segments, start=1):
            sid, conf = map_title_to_section_id(title, tmap, min_sim=args.min_similarity)
            rows.append({
                "contract_id": contract_id,
                "order": idx,
                "section_title": norm(title),
                "section_id": sid or "",
                "text": text,
                "source": source,
                "confidence": f"{conf:.3f}" if sid else f"{conf:.3f}"
            })

    # DOCX
    if os.path.isdir(args.docx_dir):
        for fn in sorted(os.listdir(args.docx_dir)):
            if not fn.lower().endswith(".docx"):
                continue

            total_attempted += 1
            path = os.path.join(args.docx_dir, fn)
            contract_id = os.path.splitext(fn)[0]

            try:
                segs = segment_docx(path)
            except Exception as e:
                report.append({
                    "contract_id": contract_id,
                    "source": "docx",
                    "status": "parse_error",
                    "segments_count": 0,
                    "error": str(e)
                })
                continue

            if segs:
                add_contract(contract_id, segs, "docx")
                report.append({
                    "contract_id": contract_id,
                    "source": "docx",
                    "status": "ok",
                    "segments_count": len(segs),
                    "error": ""
                })
            else:
                report.append({
                    "contract_id": contract_id,
                    "source": "docx",
                    "status": "zero_segments",
                    "segments_count": 0,
                    "error": "No headings detected"
                })

    # JSON
    if os.path.isdir(args.json_dir):
        for fn in sorted(os.listdir(args.json_dir)):
            if not fn.lower().endswith(".json"):
                continue

            total_attempted += 1
            path = os.path.join(args.json_dir, fn)
            contract_id = os.path.splitext(fn)[0]

            try:
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
            except Exception as e:
                report.append({
                    "contract_id": contract_id,
                    "source": "json",
                    "status": "parse_error",
                    "segments_count": 0,
                    "error": str(e)
                })
                continue

            segs = try_extract_segments_from_json(obj)
            if segs:
                add_contract(contract_id, segs, "json")
                report.append({
                    "contract_id": contract_id,
                    "source": "json",
                    "status": "ok",
                    "segments_count": len(segs),
                    "error": ""
                })
            else:
                report.append({
                    "contract_id": contract_id,
                    "source": "json",
                    "status": "unsupported_json_structure",
                    "segments_count": 0,
                    "error": "No sections/segments/clauses list found"
                })

    # Write CSV
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    fieldnames = ["contract_id", "order", "section_title", "section_id", "text", "source", "confidence"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    report_path = os.path.join(os.path.dirname(args.out) or ".", "segments_report.csv")
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["contract_id", "source", "status", "segments_count", "error"], delimiter=";", quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in report:
            w.writerow(r)

    print(f"Attempted files (docx+json): {total_attempted}")
    print(f"Segments written: {len(rows)}")
    print(f"Output: {args.out}")
    print("Note: rows with empty section_id were not mapped by section_titles_map (see confidence).")
    print(f"Attempted files (docx+json): {total_attempted}")
    print(f"Report: {report_path}")

if __name__ == "__main__":
    main()
