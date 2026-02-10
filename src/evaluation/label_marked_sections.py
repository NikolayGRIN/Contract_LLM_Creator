from __future__ import annotations

import json
import re
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


IN_PATH = Path("data/marked_sections.jsonl")
OUT_PATH = Path("data/marked_sections_labeled.jsonl")


# ----------------------------
# Normalization helpers
# ----------------------------
def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _detect_language(title: str, text: str) -> str:
    """
    Быстрая эвристика языка.
    """
    sample = (title or "") + " " + (text or "")
    sample = sample[:1500]
    has_cyr = bool(re.search(r"[А-Яа-яЁё]", sample))
    has_lat = bool(re.search(r"[A-Za-z]", sample))
    if has_cyr and not has_lat:
        return "ru"
    if has_lat and not has_cyr:
        return "en"
    # смешанное/непонятно -> предпочтем язык заголовка
    return "ru" if has_cyr else "en"


# ----------------------------
# Section keyword router
# ----------------------------
SECTION_KEYWORDS = {
    # core
    "definitions": [
        "definitions", "definition", "определения", "термины", "определение",
    ],
    "subject_of_contract": [
        "subject", "subject matter", "scope of supply", "предмет", "предмет договора", "объект", "scope",
    ],
    "price_and_taxes": [
        "price", "contract price", "tax", "vat", "ндс", "цена", "стоимость", "налоги", "пошлины", "duties",
    ],
    "payment_terms": [
        "payment", "payments", "payment terms", "payment conditions", "оплата", "платеж", "платежи",
        "расчеты", "инвойс", "invoice", "счет", "счёт",
    ],
    "delivery_terms": [
        "delivery", "shipment", "shipping", "dispatch", "поставка", "доставка", "отгрузка",
        "terms of delivery", "delivery terms",
    ],
    "acceptance_and_inspection": [
        "acceptance", "inspection", "acceptance and inspection", "приемка", "приёмка", "инспекция", "осмотр",
    ],
    "warranties": [
        "warranty", "warranties", "guarantee", "гарантия", "гарантии", "гарантийный",
    ],
    "liability_and_penalties": [
        "liability", "penalty", "penalties", "limitation of liability", "responsibility",
        "ответственность", "штраф", "неустойк", "пени", "лимит ответственности",
    ],
    "force_majeure": [
        "force majeure", "форс-мажор", "форс мажор",
    ],
    "governing_law_and_disputes": [
        "governing law", "law", "jurisdiction", "dispute", "disputes", "arbitration", "court",
        "применимое право", "право", "подсудность", "споры", "арбитраж", "суд",
    ],
    "notices": [
        "notices", "notice", "уведомления", "уведомление",
    ],
    "term_and_termination": [
        "term", "termination", "expiry", "срок", "расторжение", "прекращение",
    ],
    "bank_details": [
        "bank details", "banking details", "реквизиты", "банковские реквизиты",
    ],
    "anti_bribery": [
        "anti-bribery", "anti bribery", "corruption", "антикорруп", "взятк", "коррупц",
    ],
}

# Если нужен "секционный вес" (например, чтобы payment_terms > price_and_taxes при слове "invoice"),
# можно просто переставить порядок проверки ниже.


def _label_section_id(title: str, text: str, lang: str) -> str:
    """
    Возвращает section_id или "" если не смогли уверенно определить.
    Основной сигнал: title (H1). text используем как слабый fallback.
    """
    t = _norm(title)
    body = _norm(text)

    # 1) Сначала пробуем по title
    for sec_id, keys in SECTION_KEYWORDS.items():
        for k in keys:
            kk = _norm(k)
            if kk and kk in t:
                return sec_id

    # 2) Fallback: по первым N символам текста (аккуратно, чтобы не ловить шум)
    body_head = body[:600]
    for sec_id, keys in SECTION_KEYWORDS.items():
        for k in keys:
            kk = _norm(k)
            if kk and kk in body_head:
                return sec_id

    return ""


# ----------------------------
# Ordered output
# ----------------------------
OUTPUT_KEY_ORDER = ["doc_id", "section_id", "title", "language", "section_group", "text"]


def _reorder_keys(obj: Dict[str, Any]) -> Dict[str, Any]:
    new = OrderedDict()

    for k in OUTPUT_KEY_ORDER:
        if k in obj:
            new[k] = obj[k]

    for k, v in obj.items():
        if k not in new:
            new[k] = v

    return new


# ----------------------------
# IO
# ----------------------------
def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main() -> int:
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Input not found: {IN_PATH}")

    total = 0
    labeled = 0
    counts = Counter()

    with OUT_PATH.open("w", encoding="utf-8") as out:
        for obj in _iter_jsonl(IN_PATH):
            total += 1

            title = str(obj.get("title", "") or "")
            text = str(obj.get("text", "") or "")

            lang = str(obj.get("language", "") or "").strip().lower()
            if not lang:
                lang = _detect_language(title, text)

            # если section_id уже был — сохраняем
            sec_id = str(obj.get("section_id", "") or "").strip()
            if not sec_id:
                sec_id = _label_section_id(title, text, lang)

            obj["language"] = lang
            obj["section_id"] = sec_id

            if sec_id:
                labeled += 1
                counts[sec_id] += 1

            obj_out = _reorder_keys(obj)
            out.write(json.dumps(obj_out, ensure_ascii=False) + "\n")

    pct = (labeled / total * 100.0) if total else 0.0
    print(f"OK: total={total}, labeled={labeled} ({pct:.1f}%) -> {OUT_PATH}")
    for sec_id, c in counts.most_common():
        print(f"{sec_id:26s} {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
