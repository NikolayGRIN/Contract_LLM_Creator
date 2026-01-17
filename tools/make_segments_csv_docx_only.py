#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build segments.csv from DOCX contracts (heading-based segmentation).

Outputs:
- <out> (e.g. data/segments_healed.csv) with columns:
  contract_id, order, section_title, section_id, text, source, confidence
- segments_report.csv рядом с out

PowerShell run example:
python tools/make_segments_csv_docx_only.py `
  --docx_dir data/contracts_docx_healed `
  --titles_map data/section_titles_map.csv `
  --out data/segments_healed.csv
"""

import argparse
import csv
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Iterator, Any

from docx import Document  # python-docx
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl


# ---------------------------
# Helpers
# ---------------------------

def norm(s: str) -> str:
    s = (s or "").strip()

    # normalize dashes / quotes / NBSP
    s = (s.replace("\u00A0", " ")
           .replace("\u2013", "-")
           .replace("\u2014", "-")
           .replace("«", '"').replace("»", '"'))

    s = re.sub(r"\s+", " ", s).strip()

    # remove leading labels + numbering:
    # "ARTICLE 1.", "SECTION IV", "СТАТЬЯ 2.", "РАЗДЕЛ 3", "ГЛАВА 1"
    s = re.sub(
        r"^(?:\(?\s*(section|article|clause|chapter|appendix|annex|schedule|"
        r"раздел|статья|глава|приложение)\s*)"
        r"([IVXLC]+|\d+)(?:\.\d+)*\s*[\)\.\-:]?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )

    # also remove pure leading numbering like "1.", "1.2.", "2)" etc.
    s = re.sub(r"^\s*([IVXLC]+|\d+)(?:\.\d+){0,3}\s*[\)\.\-:]?\s*", "", s, flags=re.IGNORECASE)

    # drop trailing punctuation
    s = re.sub(r"\s*[:;\-–]\s*$", "", s).strip()

    # remove common noise in parentheses: "(hereinafter...)" "(далее - ...)"
    s = re.sub(r"\((?:hereinafter|далее)[^)]*\)", "", s, flags=re.IGNORECASE).strip()

    s = re.sub(r"\s+", " ", s).strip()
    return s

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def looks_like_heading_text(text: str) -> bool:
    """Fallback heading heuristic when styles are not reliable."""
    t = norm(text)
    if not t:
        return False
    if len(t) > 120:
        return False
    if not re.search(r"[A-Za-zА-Яа-я]", t):
        return False

    if re.search(
        r"\b(предмет|оплата|поставка|ответственност|арбитраж|споры|право|"
        r"гаранти|форс|реквизит|definitions|subject|payment|delivery|"
        r"liability|arbitration|governing law|warranty|force majeure|signatures)\b",
        t,
        re.IGNORECASE,
    ):
        return True

    if t.isupper() and len(t) <= 80:
        return True

    return False

def docx_paragraph_is_heading(p: Paragraph) -> bool:
    """Prefer Word styles (Heading 1/2/3 etc.), fallback to bold+short heuristic."""
    style_name = (p.style.name or "") if p.style else ""
    if style_name and ("Heading" in style_name or "Заголовок" in style_name):
        return True

    txt = (p.text or "").strip()
    if not txt:
        return False

    if len(txt) <= 120:
        runs = [r for r in p.runs if r.text and r.text.strip()]
        if runs:
            bold_ratio = sum(1 for r in runs if r.bold) / len(runs)
            if bold_ratio >= 0.7 and looks_like_heading_text(txt):
                return True

    return looks_like_heading_text(txt)


def is_noise_heading(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True

    raw = re.sub(r"\s+", " ", t).strip()
    low = raw.lower()

    # stamps / seals
    if low in {"м.п.", "м.п. м.п.", "m.p.", "mp"}:
        return True

    # single short tokens (often table fields)
    if len(low) <= 4 and re.fullmatch(r"[a-zа-я0-9\.\-]+", low):
        if low in {"inn", "инн", "qty", "swft", "swift"}:
            return True

    # buyer/seller labels (table headers)
    if re.fullmatch(r"(buyer|seller|покупатель|продавец|поставщик|заказчик)(\s*/\s*.*)?", low):
        return True

    # requisites/fields commonly not headings
    if low in {"swift", "инн", "inn", "qty"}:
        return True

    # placeholders with underscores
    if re.search(r"_{3,}", raw):
        return True

    # Contract number placeholders / broken OCR ("ONTRACT")
    if re.search(r"\bcontract\b", low) and ("№" in raw or "no" in low or "n" in low):
        # CONTRACT №, CONTRACT No., ONTRACT № ...
        return True
    if low.startswith("ontract"):
        return True

    # pure Incoterms note / bracket-only notes
    if ("инкотермс" in low or "incoterms" in low) and (raw.startswith("(") and raw.endswith(")")):
        return True

    # currency+incoterms fragments like "USD ____ CIP,"
    if re.search(r"\b(usd|eur|rub|uzs|cny)\b", low) and any(x in low for x in ["cip", "cif", "fca", "dap", "ddp", "exw", "cpt", "cfr", "fob"]):
        return True

    # bracket-only headings: "(EQUIPMENT SUPPLY)"
    if raw.startswith("(") and raw.endswith(")") and len(raw) <= 40:
        return True

    return False

def keyword_route_to_section_id(title: str) -> Optional[str]:
    t = (title or "").lower()
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    t = re.sub(r"\s+", " ", t).strip()

    RULES = [
        # Compliance / ethics
        ("anti_corruption", [r"антикоррупц", r"anti-corruption", r"\banticorruption\b"]),
        ("export_compliance", [r"export compliance", r"экспорт", r"санкцион", r"\bcompliance\b"]),

        # Core commercial
        ("price", [r"\bcontract price\b", r"\bprice\b", r"цена", r"стоимост", r"общая стоимость"]),
        ("payment_terms", [r"\bpayment\b", r"оплат", r"расчет", r"payment terms", r"terms of payment"]),
        ("delivery_terms", [r"условия поставки", r"\bterms of supply\b", r"\bdelivery\b", r"\bshipment\b", r"поставка"]),
        ("packing_marking", [r"упаковк", r"маркировк", r"\bpacking\b", r"\bmarking\b"]),
        ("acceptance", [r"приемк", r"\bacceptance\b", r"\binspection\b", r"приемка товара"]),

        # Claims / disputes
        ("claims", [r"претенз", r"рекламац", r"\bclaims?\b", r"\bcomplaints?\b"]),
        ("dispute_resolution", [r"разрешение споров", r"\bdispute", r"arbitration", r"арбитраж", r"спор"]),

        # Rights & obligations / liability
        ("rights_obligations", [r"права и обязанност", r"rights and obligations", r"responsibilities", r"обязанност"]),
        ("liability", [r"ответствен", r"\bliabilit", r"\bresponsibilit\b"]),
        ("penalties", [r"штраф", r"санкц", r"неустойк", r"\bpenalt", r"\bfines?\b"]),

        # Confidentiality / data
        ("confidentiality", [r"конфиденц", r"\bconfidential", r"защита данных", r"\bdata protection\b"]),

        # Term / final
        ("term", [r"срок действия", r"\bterm\b", r"\bvalidity\b"]),
        ("final_provisions", [r"заключительные положения", r"\bmiscellaneous\b", r"\bgeneral provisions\b", r"прочие условия", r"общие положения"]),

        # Annexes / spec
        ("specification", [r"спецификац", r"\bspecification\b", r"\bannex\b", r"\bappendix\b", r"\bschedule\b"]),

        # Banking / details / signatures
        ("bank_details", [r"реквизит", r"bank details", r"account details", r"реквизиты счета"]),
        ("addresses", [r"адрес", r"addresses?", r"местонахожд", r"место нахожд"]),
        ("signatures", [r"подписи сторон", r"\bsignatures?\b", r"in witness", r"signature"]),
    ]

    for sid, patterns in RULES:
        for pat in patterns:
            if re.search(pat, t):
                return sid
    return None

# ---------------------------
# Iterate paragraphs including tables (supports bilingual table layouts)
# ---------------------------

def iter_block_items(parent: Any) -> Iterator[Any]:
    """
    Yield Paragraph and Table objects in document order.
    parent can be Document or _Cell.
    """
    # Document has .element.body; cell has ._tc
    parent_elm = parent.element.body if hasattr(parent, "element") else parent._tc
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def iter_paragraphs(parent: Any) -> Iterator[Paragraph]:
    """
    Yield all paragraphs from Document body + tables (including nested tables),
    preserving document order. Recurses into table cells.
    """
    for item in iter_block_items(parent):
        if isinstance(item, Paragraph):
            txt = (item.text or "").strip()
            if txt:
                yield item
        else:
            tbl: Table = item
            for row in tbl.rows:
                for cell in row.cells:
                    # recurse into cell (handles nested tables)
                    yield from iter_paragraphs(cell)


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
            if sid not in id_to_title:
                id_to_title[sid] = title

    return TitleMap(title_to_id=title_to_id, id_to_title=id_to_title)

_MAP_CACHE: Dict[str, Tuple[Optional[str], float]] = {}


def split_bilingual_title(title: str) -> List[str]:
    """
    Split bilingual headings like:
    'ПРЕДМЕТ ДОГОВОРА / SUBJECT OF THE CONTRACT'
    Return candidates to try for mapping.
    """
    t = (title or "").strip()
    if not t:
        return []
    # split on common separators
    parts = re.split(r"\s*/\s*|\s+\|\s+|\s+-\s+", t)
    parts = [p.strip() for p in parts if p.strip()]
    # return original + parts (normalized later)
    out = [t]
    out.extend(parts)
    # unique preserve order
    seen = set()
    uniq = []
    for x in out:
        nx = norm(x).lower()
        if not nx or nx in seen:
            continue
        seen.add(nx)
        uniq.append(x)
    return uniq


def map_title_to_section_id(title: str, tmap: TitleMap, min_sim: float = 0.78) -> Tuple[Optional[str], float]:
    """
    Try mapping for:
    - full title
    - bilingual parts (split by / | -)
    Return best match.
    """
    best_sid: Optional[str] = None
    best_score: float = 0.0

    for cand in split_bilingual_title(title):
        nt = norm(cand)
        if not nt:
            continue

        key = nt.lower()
        cached = _MAP_CACHE.get(key)
        if cached:
            sid, sc = cached
            if sc > best_score and sid:
                best_sid, best_score = sid, sc
            elif sc > best_score and not best_sid:
                best_sid, best_score = sid, sc
            continue

        exact = tmap.title_to_id.get(key)
        if exact:
            _MAP_CACHE[key] = (exact, 1.0)
            if 1.0 > best_score:
                best_sid, best_score = exact, 1.0
            continue

        L = len(key)
        lo = int(L * 0.6)
        hi = int(L * 1.6)  # немного шире, чем было

        # IMPORTANT: do NOT filter by first character (breaks RU vs EN)
        cand_keys = []
        for known in tmap.title_to_id.keys():
            lk = len(known)
            if lk < lo or lk > hi:
                continue
            cand_keys.append(known)

        local_best_sid, local_best_score = None, 0.0
        for known in cand_keys:
            sc = similarity(nt, known)
            if sc > local_best_score:
                local_best_score = sc
                local_best_sid = tmap.title_to_id[known]

        if local_best_score >= min_sim:
            out = (local_best_sid, float(local_best_score))
        else:
            out = (None, float(local_best_score))

        _MAP_CACHE[key] = out

        sid, sc = out
        if sc > best_score:
            best_sid, best_score = sid, sc

    return best_sid, best_score


# ---------------------------
# DOCX segmentation
# ---------------------------

def segment_docx(path: str) -> List[Tuple[str, str]]:
    """
    Returns list of (section_title, section_text) extracted from DOCX.
    Uses headings as boundaries.
    Supports text located inside tables (common for bilingual contracts).
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

    for p in iter_paragraphs(doc):
        txt = (p.text or "").strip()
        if not txt:
            continue

        if docx_paragraph_is_heading(p) and not is_noise_heading(txt):
            flush()
            current_title = txt

        else:
            if current_title is None:
                current_title = "PREFACE"
            buf.append(txt)

    flush()
    return segments


# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx_dir", required=True, help="Folder with DOCX files (healed)")
    ap.add_argument("--titles_map", required=True, help="CSV: section_id,title")
    ap.add_argument("--out", required=True, help="Output segments CSV path")
    ap.add_argument("--min_similarity", type=float, default=0.78)
    args = ap.parse_args()

    if not os.path.isdir(args.docx_dir):
        raise SystemExit(f"docx_dir not found: {args.docx_dir}")

    tmap = load_titles_map(args.titles_map)

    rows = []
    report = []
    attempted = 0

    def add_contract(contract_id: str, segments: List[Tuple[str, str]]):
        nonlocal rows
        for idx, (title, text) in enumerate(segments, start=1):
            route_sid = keyword_route_to_section_id(title)
            if route_sid:
                sid, conf = route_sid, 0.90
            else:
                sid, conf = map_title_to_section_id(title, tmap, min_sim=args.min_similarity)
            rows.append({
                "contract_id": contract_id,
                "order": idx,
                "section_title": norm(title),
                "section_id": sid or "",
                "text": text,
                "source": "docx",
                "confidence": f"{conf:.3f}",
            })

    for fn in sorted(os.listdir(args.docx_dir)):
        if not fn.lower().endswith(".docx"):
            continue
        if fn.startswith("~$"):
            continue

        attempted += 1
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
                "error": str(e),
            })
            continue

        if segs:
            add_contract(contract_id, segs)
            report.append({
                "contract_id": contract_id,
                "source": "docx",
                "status": "ok",
                "segments_count": len(segs),
                "error": "",
            })
        else:
            report.append({
                "contract_id": contract_id,
                "source": "docx",
                "status": "zero_segments",
                "segments_count": 0,
                "error": "No headings detected",
            })

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    fieldnames = ["contract_id", "order", "section_title", "section_id", "text", "source", "confidence"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    report_path = os.path.join(os.path.dirname(args.out) or ".", "segments_report.csv")
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["contract_id", "source", "status", "segments_count", "error"],
            delimiter=";",
            quoting=csv.QUOTE_ALL,
        )
        w.writeheader()
        w.writerows(report)

    ok = sum(1 for r in report if r["status"] == "ok")
    zero = sum(1 for r in report if r["status"] == "zero_segments")
    perr = sum(1 for r in report if r["status"] == "parse_error")

    print(f"Attempted DOCX: {attempted}")
    print(f"OK: {ok} | zero_segments: {zero} | parse_error: {perr}")
    print(f"Segments written: {len(rows)}")
    print(f"Output: {args.out}")
    print(f"Report: {report_path}")
    print("Note: empty section_id means title was not mapped by section_titles_map (see confidence).")


if __name__ == "__main__":
    main()
