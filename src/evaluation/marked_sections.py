# src/evaluation/marked_sections.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
from docx import Document

MARKED_DIR = Path(r"data/contracts_marked")
OUT_GOLD = Path(r"data/marked_sections.jsonl")

def norm_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def detect_lang(text: str) -> str:
    # грубо: если кириллицы больше — ru
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return "ru" if cyr >= lat else "en"

def iter_h1_sections(doc: Document) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    cur_title = None
    cur_buf: List[str] = []

    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if not t:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        is_h1 = ("heading 1" in style) or (style == "heading1") or (style == "заголовок 1")

        if is_h1:
            if cur_title and cur_buf:
                out.append((cur_title, norm_spaces("\n".join(cur_buf))))
            cur_title = t
            cur_buf = []
        else:
            if cur_title:
                cur_buf.append(t)

    if cur_title and cur_buf:
        out.append((cur_title, norm_spaces("\n".join(cur_buf))))
    return out

def main() -> int:
    files = sorted(MARKED_DIR.glob("*.docx"))
    if not files:
        raise SystemExit(f"No docx files in {MARKED_DIR}")

    OUT_GOLD.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with OUT_GOLD.open("w", encoding="utf-8") as f:
        for fp in files:
            doc = Document(str(fp))
            sections = iter_h1_sections(doc)
            for title, text in sections:
                if len(text) < 80:
                    continue
                lang = detect_lang(title + "\n" + text)
                rec = {
                    "doc_id": fp.stem,
                    "title": title,
                    "text": text,
                    "language": lang,
                    "section_id": ""  # TODO: сюда можно подставить твой router title->section_id
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1

    print(f"OK: wrote {n} gold sections -> {OUT_GOLD}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
