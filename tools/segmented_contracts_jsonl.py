from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Any, Tuple

from docx import Document


DOCX_DIR = Path(r"data/contracts_docx_healed")
OUT_SEGMENTED = Path(r"data/segmented_contracts.jsonl")
OUT_CORPUS = Path(r"data/corpus_sections.jsonl")

MIN_SECTION_TEXT_CHARS = 80


# ----------------------------
# Helpers: iterate DOCX blocks
# ----------------------------
def iter_block_items(doc: Document) -> Iterable[Tuple[str, str]]:
    """
    Yield ("p", text) for paragraphs and ("t", text) for table-cell paragraphs,
    preserving approximate document order. (Tables are inserted where they appear.)
    """
    # python-docx internals: doc.element.body contains paragraphs and tables in order
    body = doc.element.body

    for child in body.iterchildren():
        tag = child.tag.lower()
        if tag.endswith("}p"):  # paragraph
            p = child
            text = "".join(node.text or "" for node in p.iter() if hasattr(node, "text")).strip()
            if text:
                yield ("p", text)
        elif tag.endswith("}tbl"):  # table
            # Walk all cells; keep row/col order
            for row in child.iter():
                if not getattr(row, "tag", "").lower().endswith("}tr"):
                    continue
                # find cells in row
                cells = [c for c in row.iterchildren() if c.tag.lower().endswith("}tc")]
                for cell in cells:
                    # cell paragraphs
                    for p in cell.iter():
                        if getattr(p, "tag", "").lower().endswith("}p"):
                            text = "".join(node.text or "" for node in p.iter() if hasattr(node, "text")).strip()
                            if text:
                                yield ("t", text)


# ----------------------------
# Heading / section logic
# ----------------------------
NOISE_HEADING_PATTERNS = [
    r"^buyer\s*/\s*seller$",
    r"^seller\s*/\s*buyer$",
    r"^buyer$",
    r"^seller$",
    r"^м\.?п\.?$",
    r"^swift$",
    r"^инн$",
    r"^кпп$",
    r"^огрн$",
    r"^qty$",
]

def is_noise_heading(s: str) -> bool:
    x = s.strip().lower()
    if not x:
        return True
    if len(x) <= 2:
        return True
    for pat in NOISE_HEADING_PATTERNS:
        if re.match(pat, x):
            return True
    # too "code-like" / реквизитные строки
    if re.fullmatch(r"[\w\-/.,:;() ]{1,25}", s) and sum(ch.isdigit() for ch in s) >= 6:
        return True
    return False


def looks_like_heading(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if len(s) > 120:
        return False

    # numbered headings like "3.2. Payment" or "10. TERMS"
    if re.match(r"^\d{1,2}(\.\d{1,2}){0,3}\.?\s+\S+", s):
        return True

    # ALL CAPS short-ish headings
    letters = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", s)
    if letters and len(s) <= 80:
        upper_ratio = sum(ch.isupper() for ch in letters) / max(1, len(letters))
        if upper_ratio > 0.85:
            return True

    # Ends with ":" and short → likely heading
    if s.endswith(":") and len(s) <= 80:
        return True

    return False


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def infer_language(text: str) -> str:
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    cyr = sum(1 for ch in text if ("а" <= ch.lower() <= "я") or ch.lower() == "ё")
    if latin > cyr and latin > 20:
        return "en"
    return "ru"


def map_section_id(title: str) -> Tuple[str, str]:
    """
    Minimal router: map title -> (section_id, section_group).
    We keep it very conservative; unknown => ("", "other").
    """
    t = title.lower()

    # payment / price / invoicing
    if any(k in t for k in ["payment", "оплат", "расчет", "расчёт", "settlement", "invoic", "price", "цена", "стоимост"]):
        return ("payment_terms", "commercial")

    # delivery / acceptance / performance
    if any(k in t for k in ["delivery", "поставк", "отгруз", "shipment", "accept", "приемк", "приёмк", "performance", "срок"]):
        return ("delivery_terms", "commercial")

    # liability / penalties
    if any(k in t for k in ["liabil", "responsib", "ответствен", "неустойк", "штраф", "пен", "penalt"]):
        return ("liability_penalties", "liability")

    # disputes / governing law
    if any(k in t for k in ["dispute", "спор", "арбит", "jurisdiction", "подсуд", "governing law", "применим", "право"]):
        return ("disputes_governing_law", "disputes")

    return ("", "other")


# ----------------------------
# Segmentation
# ----------------------------
@dataclass
class Section:
    section_id: str
    section_group: str
    title: str
    text: str
    language: str


def segment_docx_simple(docx_path: Path) -> List[Section]:
    doc = Document(str(docx_path))

    sections: List[Section] = []
    current_title = "Preamble"
    current_lines: List[str] = []

    def flush():
        nonlocal current_lines, current_title, sections
        body = "\n".join(current_lines).strip()
        if body:
            sid, grp = map_section_id(current_title)
            sections.append(
                Section(
                    section_id=sid,
                    section_group=grp,
                    title=current_title,
                    text=body,
                    language=infer_language(body),
                )
            )
        current_lines = []

    for kind, text in iter_block_items(doc):
        line = text.strip()

        if looks_like_heading(line) and not is_noise_heading(line):
            # start new section
            flush()
            current_title = normalize_title(line.rstrip(":"))
            continue

        current_lines.append(line)

    flush()
    return sections


# ----------------------------
# Build outputs
# ----------------------------
def main() -> None:
    if not DOCX_DIR.exists():
        raise RuntimeError(f"DOCX folder not found: {DOCX_DIR}")

    OUT_SEGMENTED.parent.mkdir(parents=True, exist_ok=True)

    docs = 0
    sections_seen = 0
    corpus_written = 0

    with OUT_SEGMENTED.open("w", encoding="utf-8") as seg_out, OUT_CORPUS.open("w", encoding="utf-8") as corp_out:
        for docx_path in sorted(DOCX_DIR.glob("*.docx")):
            docs += 1
            contract_id = docx_path.stem

            sections = segment_docx_simple(docx_path)

            seg_record = {
                "contract_id": contract_id,
                "source": "docx",
                "sections": [
                    {
                        "section_id": s.section_id,
                        "section_group": s.section_group,
                        "title": s.title,
                        "language": s.language,
                        "text": s.text,
                    }
                    for s in sections
                ],
            }
            seg_out.write(json.dumps(seg_record, ensure_ascii=False) + "\n")

            for s in sections:
                sections_seen += 1
                if len(s.text) < MIN_SECTION_TEXT_CHARS:
                    continue

                corp_record = {
                    "doc_id": contract_id,
                    "section_group": s.section_group,
                    "section_id": s.section_id,
                    "language": s.language,
                    "title": s.title,
                    "text": s.text,
                }
                corp_out.write(json.dumps(corp_record, ensure_ascii=False) + "\n")
                corpus_written += 1

    print("DONE")
    print("docs:", docs)
    print("sections_seen:", sections_seen)
    print("corpus_written:", corpus_written)
    print("segmented_out:", OUT_SEGMENTED)
    print("corpus_out:", OUT_CORPUS)


if __name__ == "__main__":
    main()
