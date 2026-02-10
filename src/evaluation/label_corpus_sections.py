# src/evaluation/label_corpus_sections_v2.py
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


# ----------------------------
# IO
# ----------------------------
def read_jsonl(path: Path) -> List[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def norm(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_lower(s: str) -> str:
    return norm(s).lower()


# ----------------------------
# Targets: your 10 sections
# ----------------------------
TARGET_SECTIONS = [
    "definitions",
    "subject_of_contract",
    "price_and_taxes",
    "payment_terms",
    "delivery_terms",
    "acceptance_and_inspection",
    "warranties",
    "liability_and_penalties",
    "force_majeure",
    "governing_law_and_disputes",
]


# ----------------------------
# Patterns
# ----------------------------
# (A) Title patterns: strong signal (1 match is enough)
TITLE_PATTERNS_EN: Dict[str, List[re.Pattern]] = {
    "definitions": [
        re.compile(r"\bdefinitions?\b", re.I),
        re.compile(r"\bdefinitions?\s+and\s+interpretation\b", re.I),
    ],
    "subject_of_contract": [
        re.compile(r"\bsubject\s+of\s+(the\s+)?contract\b", re.I),
        re.compile(r"\bsubject\s+matter\s+of\s+(the\s+)?contract\b", re.I),
        re.compile(r"\bscope\s+of\s+supply\b", re.I),
        re.compile(r"\bobject\s+of\s+the\s+contract\b", re.I),
    ],
    "price_and_taxes": [
        re.compile(r"\bprice\s+and\s+tax(es)?\b", re.I),
        re.compile(r"\bcontract\s+price\b", re.I),
        re.compile(r"\bprice\s+and\s+total\s+(amount|cost)\b", re.I),
        re.compile(r"\btaxes?\s+and\s+duties\b", re.I),
    ],
    "payment_terms": [
        re.compile(r"\bpayment\s+terms?\b", re.I),
        re.compile(r"\bpayment\s+conditions?\b", re.I),
        re.compile(r"\bterms?\s+of\s+payment\b", re.I),
    ],
    "delivery_terms": [
        re.compile(r"\bdelivery\s+terms?\b", re.I),
        re.compile(r"\bterms?\s+of\s+delivery\b", re.I),
        re.compile(r"\border(ing)?\s+and\s+conditions\s+of\s+delivery\b", re.I),
        re.compile(r"\bshipment\b", re.I),
    ],
    "acceptance_and_inspection": [
        re.compile(r"\bacceptance\s+and\s+inspection\b", re.I),
        re.compile(r"\border\s+of\s+goods\s+acceptance\b", re.I),
        re.compile(r"\bacceptance\b", re.I),
        re.compile(r"\binspection\b", re.I),
    ],
    "warranties": [
        re.compile(r"\bwarrant(y|ies)\b", re.I),
        re.compile(r"\bguarantee(s)?\b", re.I),
    ],
    "liability_and_penalties": [
        re.compile(r"\bliabilit(y|ies)\b", re.I),
        re.compile(r"\blimitation\s+of\s+liability\b", re.I),
        re.compile(r"\bpenalt(y|ies)\b", re.I),
        re.compile(r"\bdamages?\b", re.I),
    ],
    "force_majeure": [
        re.compile(r"\bforce\s+majeure\b", re.I),
        re.compile(r"\bacts?\s+of\s+god\b", re.I),
    ],
    "governing_law_and_disputes": [
        re.compile(r"\bgoverning\s+law\b", re.I),
        re.compile(r"\bapplicable\s+law\b", re.I),
        re.compile(r"\bdispute(s)?\s+resolution\b", re.I),
        re.compile(r"\barbitration\b", re.I),
        re.compile(r"\bjurisdiction\b", re.I),
    ],
}

TITLE_PATTERNS_RU: Dict[str, List[re.Pattern]] = {
    "definitions": [
        re.compile(r"\bопределени(я|е)\b", re.I),
        re.compile(r"\bтермин(ы|ология)\b", re.I),
    ],
    "subject_of_contract": [
        re.compile(r"\bпредмет\s+договор[ауы]\b", re.I),
        re.compile(r"\bпредмет\s+контракт[ауы]\b", re.I),
        re.compile(r"\bобъем\s+поставк(и|а)\b", re.I),
    ],
    "price_and_taxes": [
        re.compile(r"\bцена\s+и\s+налог(и|и)\b", re.I),
        re.compile(r"\bцена\s+договор[ауы]\b", re.I),
        re.compile(r"\bндс\b", re.I),
        re.compile(r"\bналог(и|и)\b", re.I),
    ],
    "payment_terms": [
        re.compile(r"\bуслови(я|е)\s+оплат(ы|а)\b", re.I),
        re.compile(r"\bпорядок\s+оплат(ы|а)\b", re.I),
        re.compile(r"\bоплат(а|ы)\b", re.I),
    ],
    "delivery_terms": [
        re.compile(r"\bуслови(я|е)\s+поставк(и|а)\b", re.I),
        re.compile(r"\bпорядок\s+поставк(и|а)\b", re.I),
        re.compile(r"\bсрок(и)?\s+поставк(и|а)\b", re.I),
        re.compile(r"\bотгрузк(а|и)\b", re.I),
    ],
    "acceptance_and_inspection": [
        re.compile(r"\bприемк(а|и)\b", re.I),
        re.compile(r"\bинспекц(ия|ии)\b", re.I),
        re.compile(r"\bакт\s+прием", re.I),
    ],
    "warranties": [
        re.compile(r"\bгаранти(я|и)\b", re.I),
        re.compile(r"\bгарантийн(ый|ые)\b", re.I),
    ],
    "liability_and_penalties": [
        re.compile(r"\bответственност(ь|и)\b", re.I),
        re.compile(r"\bштраф(ы|ов)\b", re.I),
        re.compile(r"\bнеустойк(а|и)\b", re.I),
        re.compile(r"\bубытк(и|ов)\b", re.I),
    ],
    "force_majeure": [
        re.compile(r"\bфорс[-\s]?мажор\b", re.I),
        re.compile(r"\bнепреодолим(ая|ой)\s+сил(а|ы)\b", re.I),
    ],
    "governing_law_and_disputes": [
        re.compile(r"\bприменим(ое|ого)\s+право\b", re.I),
        re.compile(r"\bразрешени(е|я)\s+спор(ов|а)\b", re.I),
        re.compile(r"\bарбитраж\b", re.I),
        re.compile(r"\bподсудност(ь|и)\b", re.I),
    ],
}

# (B) Text keywords: weaker signal, require >=2 matches
TEXT_KEYWORDS_EN: Dict[str, List[str]] = {
    "definitions": ["means", "shall mean", "for the purposes", "definition"],
    "subject_of_contract": ["seller shall supply", "buyer shall purchase", "scope of supply", "equipment", "goods"],
    "price_and_taxes": ["contract price", "total amount", "vat", "tax", "duties", "fees"],
    "payment_terms": ["invoice", "bank transfer", "payment", "advance", "prepayment", "due date"],
    "delivery_terms": ["incoterms", "delivery", "shipment", "partial shipment", "dispatch", "risk passes"],
    "acceptance_and_inspection": ["acceptance", "inspection", "acceptance certificate", "acceptance report", "defect notice"],
    "warranties": ["warranty period", "repair", "replace", "defects", "guarantee"],
    "liability_and_penalties": ["liability", "limitation", "cap", "penalty", "liquidated damages", "indirect"],
    "force_majeure": ["force majeure", "acts of god", "unforeseeable", "notice", "suspension"],
    "governing_law_and_disputes": ["governing law", "jurisdiction", "arbitration", "court", "dispute"],
}

TEXT_KEYWORDS_RU: Dict[str, List[str]] = {
    "definitions": ["означает", "под", "для целей", "определ"],
    "subject_of_contract": ["поставщик обязуется", "покупатель обязуется", "поставить", "оборудован", "товар"],
    "price_and_taxes": ["цена", "стоимость", "ндс", "налог", "пошлин"],
    "payment_terms": ["оплата", "счет", "инвойс", "предоплат", "аванс", "банковск"],
    "delivery_terms": ["поставка", "инкотермс", "отгрузк", "срок поставки", "риск", "место поставки"],
    "acceptance_and_inspection": ["приемк", "акт", "инспекц", "осмотр", "дефект", "претензи"],
    "warranties": ["гаранти", "ремонт", "замен", "дефект", "гарантийный срок"],
    "liability_and_penalties": ["ответствен", "огранич", "лимит", "штраф", "неустойк", "убытк"],
    "force_majeure": ["форс", "непреодолим", "уведом", "приостанов", "обстоятельств"],
    "governing_law_and_disputes": ["применим", "право", "арбитраж", "суд", "спор", "подсуд"],
}

GENERIC_TITLES = [
    re.compile(r"^\s*general\s*$", re.I),
    re.compile(r"^\s*miscellaneous\s*$", re.I),
    re.compile(r"^\s*other\s+provisions\s*$", re.I),
]

def is_generic_title(title: str) -> bool:
    t = norm(title)
    if not t:
        return True
    for rx in GENERIC_TITLES:
        if rx.search(t):
            return True
    return False


# ----------------------------
# Scoring
# ----------------------------
def score_by_title(title: str, lang: str) -> Dict[str, int]:
    t = norm(title)
    if is_generic_title(t):
        return {}
    patterns = TITLE_PATTERNS_RU if (lang or "").lower().startswith("ru") else TITLE_PATTERNS_EN
    scores: Dict[str, int] = {}
    for sid in TARGET_SECTIONS:
        s = 0
        for rx in patterns.get(sid, []):
            if rx.search(t):
                s += 1
        if s:
            scores[sid] = s
    return scores


def score_by_text(text: str, lang: str) -> Dict[str, int]:
    x = norm_lower(text)
    kw = TEXT_KEYWORDS_RU if (lang or "").lower().startswith("ru") else TEXT_KEYWORDS_EN
    scores: Dict[str, int] = {}
    for sid in TARGET_SECTIONS:
        hits = 0
        for needle in kw.get(sid, []):
            if needle in x:
                hits += 1
        if hits:
            scores[sid] = hits
    return scores


def pick_best(scores: Dict[str, int], min_score: int, require_margin: bool = True) -> str:
    if not scores:
        return ""
    best_sid, best_score = max(scores.items(), key=lambda x: x[1])
    if best_score < min_score:
        return ""
    if require_margin:
        # если второй почти такой же — не уверены
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] == sorted_scores[1]:
            return ""
    return best_sid


def infer_section_id(title: str, text: str, lang: str) -> str:
    # Step 1: title-only (точно)
    t_scores = score_by_title(title, lang)
    sid = pick_best(t_scores, min_score=1, require_margin=True)
    if sid:
        return sid

    # Step 2: text keywords (более мягко, но порог >=2)
    x_scores = score_by_text(text, lang)
    sid = pick_best(x_scores, min_score=2, require_margin=True)
    return sid


# ----------------------------
# main
# ----------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", type=str, default="data/corpus_sections.jsonl")
    ap.add_argument("--out", type=str, default="data/corpus_sections_labeled_all.jsonl")
    ap.add_argument("--only_empty", action="store_true")
    args = ap.parse_args()

    rows = read_jsonl(Path(args.inp))

    changed = 0
    empty_before = 0
    empty_after = 0
    dist = Counter()

    for r in rows:
        cur = (r.get("section_id") or "").strip()
        if not cur:
            empty_before += 1

        if args.only_empty and cur:
            dist[cur] += 1
            continue

        sid = infer_section_id(
            title=r.get("title", ""),
            text=r.get("text", ""),
            lang=r.get("language", ""),
        )
        if sid:
            r["section_id"] = sid
            dist[sid] += 1
            if sid != cur:
                changed += 1
        else:
            r["section_id"] = "" if not args.only_empty else cur
            if not r["section_id"]:
                empty_after += 1

    write_jsonl(Path(args.out), rows)

    total = len(rows)
    print(f"OK: rows={total} | changed={changed}")
    print(f"empty section_id: before={empty_before} ({empty_before/total:.1%}) | after={empty_after} ({empty_after/total:.1%})")
    print("Top section_id counts:")
    for sid, c in dist.most_common(20):
        print(f"  {sid:28s} {c}")

    print(f"OUT: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
