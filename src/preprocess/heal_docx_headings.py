import argparse
import csv
import re
from pathlib import Path
from typing import Optional, Tuple

from docx import Document
from docx.text.paragraph import Paragraph


DASHES = {
    "\u2013": "-",  # en-dash
    "\u2014": "-",  # em-dash
    "\u2212": "-",  # minus
    "\u00AD": "",   # soft hyphen
    "\u00A0": " ",  # nbsp
}

# --- Regex patterns (v1) ---
RE_ARTICLE_RU = re.compile(r"^\s*СТАТЬЯ\s+(\d+)\.?\s*(.*)$", re.IGNORECASE)
RE_NUM_DOT = re.compile(r"^\s*(\d{1,3})(?:\.(\d{1,3}))?(?:\.(\d{1,3}))?\s*[\.\)]\s*(.+)$")
RE_NUM_DASH = re.compile(r"^\s*(\d{1,3})\s*-\s*(.+)$")
RE_BULLETISH = re.compile(r"^\s*[-•]\s+.+$")

# Single-line caps heading heuristic (English/Russian)
RE_MOSTLY_CAPS = re.compile(r"[A-ZА-Я]")
RE_SENTENCE_PUNCT = re.compile(r"[.!?;:]{1}")


def normalize_text(s: str) -> str:
    if not s:
        return s
    for k, v in DASHES.items():
        s = s.replace(k, v)
    # collapse whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n\s+", "\n", s)
    return s.strip()


def fix_number_spacing(title: str) -> str:
    """
    - '7.THE ABC' -> '7. THE ABC'
    - '7)THE ABC' -> '7) THE ABC'
    """
    title = re.sub(r"^(\d{1,3})([.)])([A-Za-zА-Яа-я])", r"\1\2 \3", title)
    return title


def canonicalize_heading_line(line: str) -> str:
    line = normalize_text(line)
    line = fix_number_spacing(line)

    m = RE_NUM_DASH.match(line)
    if m:
        # "12 - FORCE MAJEURE" -> "12. FORCE MAJEURE"
        line = f"{m.group(1)}. {m.group(2).strip()}"

    # If someone wrote "12 -FORCE", after dash normalization it becomes above.
    return line.strip()


def is_probable_caps_heading(line: str) -> bool:
    """
    Heuristic for headings like 'DEFINITIONS', 'FORCE MAJEURE', 'ПРЕДМЕТ ДОГОВОРА'
    """
    s = normalize_text(line)
    if not s:
        return False
    if len(s) > 90:
        return False
    # Avoid bullet lines
    if RE_BULLETISH.match(s):
        return False

    # Must have letters
    letters = [ch for ch in s if ch.isalpha()]
    if len(letters) < 4:
        return False

    # If it has many punctuation markers, likely not a heading
    # (but allow single colon sometimes)
    punct_count = len(re.findall(r"[.!?;]", s))
    if punct_count >= 2:
        return False

    # Uppercase ratio (for cyrillic+latin)
    upper = sum(1 for ch in letters if ch.isupper())
    ratio = upper / max(1, len(letters))

    # Common legal headings often are caps or titlecase short
    if ratio >= 0.75:
        return True

    # Bilingual with slash also a good signal (short)
    if "/" in s and len(s) <= 110:
        return True

    return False


def detect_heading_level(line: str) -> Optional[int]:
    """
    Return 1/2/3 if the line is a heading candidate, else None.
    """
    s = canonicalize_heading_line(line)

    # Russian "Статья N"
    m_ru = RE_ARTICLE_RU.match(s)
    if m_ru:
        return 1

    # Numbered with dot/paren:
    m = RE_NUM_DOT.match(s)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        if c:
            return 3
        if b:
            return 2
        return 1

    # Number + dash (after canonicalize should be less frequent, but keep)
    if RE_NUM_DASH.match(normalize_text(line)):
        return 1

    # Pure caps headings
    if is_probable_caps_heading(s):
        return 1

    return None


def split_paragraph_on_first_line_if_needed(par: Paragraph) -> Tuple[str, Optional[str]]:
    """
    If paragraph has line breaks and first line looks like a heading and remaining looks like body,
    split into (heading_line, rest_text). Else return (full_text, None).
    """
    raw = par.text or ""
    if "\n" not in raw:
        return raw, None

    parts = [p.strip() for p in raw.split("\n") if p.strip()]
    if len(parts) < 2:
        return raw, None

    first = parts[0]
    lvl = detect_heading_level(first)
    if not lvl:
        return raw, None

    rest = "\n".join(parts[1:]).strip()
    if not rest:
        return raw, None

    # If rest is very short, maybe it's still heading-ish; keep together
    if len(rest) < 20 and detect_heading_level(rest):
        return raw, None

    return first, rest


def insert_paragraph_before(par: Paragraph, text: str, style: Optional[str] = None) -> Paragraph:
    """
    python-docx doesn't have a public 'insert_before' paragraph API, so we use the XML.
    """
    new_p = par._p.addprevious(par._p.__class__())
    new_par = Paragraph(new_p, par._parent)
    new_par.text = text
    if style:
        try:
            new_par.style = style
        except Exception:
            pass
    return new_par


def apply_heading_style(par: Paragraph, level: int) -> None:
    style_name = f"Heading {level}"
    try:
        par.style = style_name
    except Exception:
        # If doc has localized style names, fallback to built-in by id is harder.
        # Usually English Heading styles exist even in RU Office, but not always.
        pass


def heal_docx(in_path: Path, out_path: Path) -> dict:
    doc = Document(str(in_path))

    changed = False
    headings_set = 0
    splits_done = 0

    # Iterate over a snapshot list because we may insert paragraphs
    paragraphs = list(doc.paragraphs)

    for par in paragraphs:
        if not (par.text and par.text.strip()):
            continue

        # Split paragraph if it contains a heading line + body
        head, rest = split_paragraph_on_first_line_if_needed(par)
        if rest is not None:
            # Create a new heading paragraph before this one
            head_fixed = canonicalize_heading_line(head)
            lvl = detect_heading_level(head_fixed) or 1
            insert_paragraph_before(par, head_fixed, style=f"Heading {lvl}")
            # Replace current paragraph text with rest (body)
            par.text = normalize_text(rest)
            changed = True
            headings_set += 1
            splits_done += 1
            continue

        # Normal case: decide if this whole paragraph is a heading
        text_norm = canonicalize_heading_line(par.text)
        lvl = detect_heading_level(text_norm)
        if not lvl:
            continue

        # Guardrail: avoid marking very long paragraphs as headings
        if len(text_norm) > 160:
            continue

        # Apply normalization only if we mark it as heading
        if par.text != text_norm:
            par.text = text_norm
            changed = True

        # Only set heading if it isn't already
        cur_style = getattr(par.style, "name", "") if par.style else ""
        if not cur_style.startswith("Heading"):
            apply_heading_style(par, lvl)
            changed = True
        headings_set += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))

    return {
        "file": in_path.name,
        "changed": changed,
        "headings_set": headings_set,
        "splits_done": splits_done,
        "status": "ok" if headings_set > 0 else "no_candidates",
    }


def main():
    ap = argparse.ArgumentParser(description="Heal DOCX headings: add Heading 1/2/3 for contract clauses.")
    ap.add_argument("--in_dir", required=True, help="Input folder with .docx files")
    ap.add_argument("--out_dir", required=True, help="Output folder for healed .docx files")
    ap.add_argument("--report", default="healing_report.csv", help="CSV report path")
    ap.add_argument("--recursive", action="store_true", help="Scan input folder recursively")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    report_path = Path(args.report)

    if not in_dir.exists():
        raise SystemExit(f"Input dir not found: {in_dir}")

    pattern = "**/*.docx" if args.recursive else "*.docx"
    files = sorted(in_dir.glob(pattern))

    rows = []
    for f in files:
        # Skip temporary Word files
        if f.name.startswith("~$"):
            continue
        out_path = out_dir / f.name.replace(".docx", "__headings_fixed.docx")
        try:
            rows.append(heal_docx(f, out_path))
        except Exception as e:
            rows.append({
                "file": f.name,
                "changed": False,
                "headings_set": 0,
                "splits_done": 0,
                "status": f"error: {type(e).__name__}",
            })

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["file", "status", "changed", "headings_set", "splits_done"])
        w.writeheader()
        w.writerows(rows)

    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"Processed: {len(rows)} files. OK: {ok}. Report: {report_path.resolve()}")
    print(f"Output folder: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
