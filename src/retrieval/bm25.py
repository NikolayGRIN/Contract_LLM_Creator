from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional, Set

print("DEBUG: bm25.py LOADED from", __file__)


# МОДЕЛЬ ДАННЫХ

@dataclass
class Doc:
    doc_id: str
    section_group: str
    section_id: str
    language: str
    title: str
    text: str


# ТЕКСТОВЫЕ УТИЛИТЫ (без потери регистра/пунктуации)

_word_re = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)

def normalize_ws(s: str) -> str:
    # Нормализуем пробелы, НЕ меняя регистр
    return re.sub(r"[ \t\r\f\v]+", " ", (s or "")).strip()

def normalize_newlines(s: str) -> str:
    # Нормализуем переносы, чтобы не было \r\r\n и т.п.
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    # Схлопываем слишком частые пустые строки
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s

def smart_truncate(text: str, max_chars: int = 2600) -> str:
    """
    Обрезаем текст не по середине слова:
    если длиннее max_chars, ищем ближайшую "нормальную" границу (., ;, :, ?, !, \n) в хвосте, и режем там.
    """
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t

    cut = max_chars
    tail = t[int(max_chars * 0.65):max_chars]  # хвостовая зона для поиска границы
    m = None
    for m0 in re.finditer(r"[\.\!\?\;\:\n]", tail):
        m = m0
    if m:
        cut = int(max_chars * 0.65) + m.end()

    t = t[:cut].rstrip()
    if t and t[-1] not in ".!?…":
        t += "…"
    return t

def squash_consecutive_repeats(text: str, min_len: int = 30, max_len: int = 220) -> str:
    """
    Универсально схлопывает подряд идущие повторы одной и той же подстроки.    
    """
    t = text or ""
    if len(t) < min_len * 2:
        return t

    pat = re.compile(rf"(.{{{min_len},{max_len}}})(?:[\s]*\1)+", re.DOTALL)

    while True:
        new_t = pat.sub(r"\1", t)
        if new_t == t:
            break
        t = new_t
    return t

def fix_glued_words(text: str) -> str:
    """
    Общая попытка починить склейки слов 
    """
    t = text or ""

    t = re.sub(r"([,;:])([A-Za-zА-Яа-яЁё])", r"\1 \2", t)
    t = re.sub(r"([A-Za-zА-Яа-яЁё])(\d)", r"\1 \2", t)
    t = re.sub(r"(\d)([A-Za-zА-Яа-яЁё])", r"\1 \2", t)
    t = re.sub(r"([А-Яа-яЁё])([A-Za-z])", r"\1 \2", t)
    t = re.sub(r"([A-Za-z])([А-Яа-яЁё])", r"\1 \2", t)

    return t

def tokenize_for_bm25(text: str) -> List[str]:
    """
    Токенизация только для BM25.
    НЕ влияет на вывод прецедентов.
    """
    return _word_re.findall((text or "").lower())

def maybe_filter_language(lang_req: str, lang_doc: str) -> bool:
    """
    True если язык документа подходит под запрошенный язык.
    ru/en -> exact + bilingual; bilingual -> ru/en/bilingual.
    """
    lr = (lang_req or "ru").lower()
    ld = (lang_doc or "ru").lower()
    if lr in ("ru", "en"):
        return ld in (lr, "bilingual")
    if lr == "bilingual":
        return ld in ("ru", "en", "bilingual")
    return True



# BM25


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = float(k1)
        self.b = float(b)

        self.docs: List[Doc] = []
        self.doc_len: List[int] = []
        self.avgdl: float = 0.0

        self.df: Dict[str, int] = {}
        self.N: int = 0
        self.tf: List[Dict[str, int]] = []

    def add_documents(self, docs: Iterable[Doc]) -> None:
        self.docs = list(docs)
        self._build()

    def _build(self) -> None:
        self.N = len(self.docs)
        self.df = {}
        self.tf = []
        self.doc_len = []

        total_len = 0

        for d in self.docs:
            tokens = tokenize_for_bm25(f"{d.title}\n{d.text}")
            total_len += len(tokens)
            self.doc_len.append(len(tokens))

            freqs: Dict[str, int] = {}
            for tok in tokens:
                freqs[tok] = freqs.get(tok, 0) + 1
            self.tf.append(freqs)

            for tok in freqs.keys():
                self.df[tok] = self.df.get(tok, 0) + 1

        self.avgdl = (total_len / self.N) if self.N else 1.0

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        if df <= 0:
            return 0.0
        return math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: List[str], doc_idx: int) -> float:
        if not query_tokens:
            return 0.0

        freqs = self.tf[doc_idx]
        dl = self.doc_len[doc_idx] or 1
        avgdl = self.avgdl or 1.0

        score = 0.0
        for term in query_tokens:
            f = freqs.get(term, 0)
            if f <= 0:
                continue
            idf = self._idf(term)
            denom = f + self.k1 * (1.0 - self.b + self.b * (dl / avgdl))
            score += idf * (f * (self.k1 + 1.0) / denom)
        return score

    def search(self, query: str, *, top_k: int = 5) -> List[Tuple[int, float]]:
        q_tokens = tokenize_for_bm25(query)
        if not q_tokens:
            return []

        scores: List[Tuple[int, float]] = []
        for i in range(self.N):
            s = self.score(q_tokens, i)
            if s > 0:
                scores.append((i, s))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k * 8]  # берем с запасом — потом диверсифицируем


def load_corpus_sections_jsonl(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows



# ДОМЕННЫЕ ФИЛЬТРЫ: PAYMENT TERMS

PAYMENT_POS = [
    # RU
    "оплата", "платеж", "платёж", "счет", "счёт", "инвойс", "предоплата", "аванс",
    "отсрочка", "расчет", "расчёт", "расчеты", "расчёты", "срок", "банков",
    "ндс", "комис", "неустойк", "пеня", "процент", "просроч",
    # EN
    "payment", "invoice", "due", "payable", "prepayment", "advance", "bank", "transfer",
    "vat", "interest", "penalty", "setoff", "set-off"
]

PAYMENT_NEG = [
    "поставщик обязуется", "передать в собственность", "номенклатур", "ассортимент",
    "техническ", "спецификац", "предмет договора", "поставка товара осуществляется",
    "продукци", "оборудовани", "товар", "работ", "услуг", "комплект",
    "acceptance", "приемк", "приёмк", "качество", "количество"
]

def filter_payment_terms(docs: List[Doc]) -> List[Doc]:
    out: List[Doc] = []
    for d in docs:
        low = (d.title + "\n" + d.text).lower()
        pos = sum(1 for k in PAYMENT_POS if k in low)
        neg = sum(1 for k in PAYMENT_NEG if k in low)

        if pos < 4:
            continue

        if neg >= 3 and pos < 7:
            continue

        out.append(d)
    return out

# ДОМЕННЫЕ ФИЛЬТРЫ: DELIVERY TERMS

DELIVERY_POS = [
    # RU
    "поставка", "доставка", "отгруз", "срок постав", "срок достав",
    "место постав", "место достав", "переход риск", "риск случайной",
    "инкотерм", "incoterms", "склад", "перевоз", "транспорт", "упаков",
    "маркир", "приемк", "приёмк", "акт прием", "накладн", "товаротранспорт",
    "частичн", "партиями", "график", "задержк", "просрочк", "хранен", "демерредж", "простой",
    # EN
    "delivery", "dispatch", "shipment", "shipping", "lead time", "delivery date",
    "delivery point", "incoterms", "risk", "title", "packing", "packaging",
    "marking", "carrier", "transport", "acceptance", "take delivery", "demurrage", "storage",
    "partial delivery", "instalments", "schedule"
]

DELIVERY_NEG = [
    # сильные признаки не-delivery секций
    "оплата", "платеж", "счет", "инвойс", "проценты", "пеня", "неустойк", "штраф",
    "payment", "invoice", "interest", "penalty", "late payment",
    "арбитраж", "суд", "претенз", "спор", "jurisdiction", "governing law",
    "liability", "damages", "убытк", "ответственност"
]

def filter_delivery_terms(docs: List[Doc]) -> List[Doc]:
    out: List[Doc] = []
    for d in docs:
        low = (d.title + "\n" + d.text).lower()
        pos = sum(1 for k in DELIVERY_POS if k in low)
        neg = sum(1 for k in DELIVERY_NEG if k in low)

        if pos < 4:
            continue

        if neg >= 3 and pos < 7:
            continue

        out.append(d)
    return out


# СБОРКА ДОКУМЕНТОВ ИЗ ROWS

def build_docs_from_rows(
    rows: List[dict],
    *,
    language_mode: str = "ru",
    min_chars: int = 80,
    max_chars: int = 2600,
) -> List[Doc]:
    docs: List[Doc] = []

    for r in rows:
        text = (r.get("text") or "").strip()
        if len(text) < min_chars:
            continue

        text = normalize_newlines(text)

        # убрать плейсхолдеры вида 
        text = re.sub(r"\[[^\]]{1,120}\]", "", text)

        text = fix_glued_words(text)

        # нормализовать пробелы
        text = normalize_ws(text)

        # схлопнуть повторы
        text = squash_consecutive_repeats(text, min_len=35, max_len=220)

        # еще раз пробелы
        text = normalize_ws(text)

        # обрезка
        text = smart_truncate(text, max_chars=max_chars)

        lang = (r.get("language") or "ru").strip().lower()
        if not maybe_filter_language(language_mode, lang):
            continue

        docs.append(
            Doc(
                doc_id=str(r.get("doc_id") or r.get("contract_id") or ""),
                section_group=str(r.get("section_group") or ""),
                section_id=str(r.get("section_id") or ""),
                language=lang,
                title=str(r.get("title") or ""),
                text=text,
            )
        )

    return docs

# ПОСТ-ОБРАБОТКА ПРЕЦЕДЕНТОВ


def mask_form_variables(text: str, form: dict) -> str:
    """
    Убираем из прецедента то, что задаётся в Input Form:
    - валюта / суммы / сроки (дни) / проценты
    - страну/юрисдикцию (если есть в форме)
    """
    t = text or ""

    # Валюта из формы (если есть)
    payment = form.get("payment", {}) if isinstance(form.get("payment"), dict) else {}
    currency = payment.get("currency") or form.get("currency")
    if isinstance(currency, str) and currency.strip():
        c = currency.strip()
        t = re.sub(re.escape(c), "[CURRENCY]", t, flags=re.IGNORECASE)

    # Страна/юрисдикция (если есть)
    jurisdiction = (
        (form.get("jurisdiction", {}) if isinstance(form.get("jurisdiction"), dict) else {})
        .get("jurisdiction_country")
        or form.get("jurisdiction_country")
    )
    if isinstance(jurisdiction, str) and jurisdiction.strip():
        j = jurisdiction.strip()
        t = re.sub(re.escape(j), "[JURISDICTION_COUNTRY]", t, flags=re.IGNORECASE)

    # Сроки в днях 
    t = re.sub(r"\b(\d{1,4})\s*(дней|дня|дн\.|day|days)\b", r"[TERM_DAYS] \2", t, flags=re.IGNORECASE)

    # Проценты
    t = re.sub(r"\b(\d{1,3})\s*%", "[PERCENT]%", t)

    # Денежные суммы
    t = re.sub(r"\b\d{1,3}(?:[ \u00A0]\d{3})*(?:[.,]\d{1,2})?\b", "[AMOUNT]", t)

    # подчистка повторов после масок
    t = squash_consecutive_repeats(t, min_len=35, max_len=220)
    t = normalize_ws(t)

    return t



# ДИВЕРСИФИКАЦИЯ: чтобы не брать одинаковые куски несколько раз


def _shingles(text: str, k: int = 7) -> Set[str]:
    w = tokenize_for_bm25(text)
    if len(w) < k:
        return set()
    return {" ".join(w[i:i+k]) for i in range(0, len(w)-k+1)}

def _too_similar(a: str, b: str, threshold: float = 0.55) -> bool:
    sa = _shingles(a, k=7)
    sb = _shingles(b, k=7)
    if not sa or not sb:
        return False
    inter = len(sa & sb)
    union = len(sa | sb)
    if union == 0:
        return False
    return (inter / union) >= threshold


# Конструктор запросов: PAYMENT TERMS

def build_payment_query(language_mode: str, form: dict) -> str:
    lang = (language_mode or "ru").lower()
    payment = form.get("payment", {}) if isinstance(form.get("payment"), dict) else {}

    if lang == "en":
        q = [
            "payment terms", "invoice", "due date", "bank transfer", "currency",
            "without set-off", "VAT", "late payment interest", "prepayment"
        ]
        if payment.get("prepayment_required") is True:
            q.append("advance payment")
        if payment.get("late_payment_penalty_enabled") is True:
            q.append("penalty interest")
        return " ".join(q)

    q = [
        "условия оплаты", "порядок расчетов", "счет", "срок оплаты", "валюта платежа",
        "банковский перевод", "без зачета", "ндс", "проценты за просрочку", "предоплата"
    ]
    if payment.get("prepayment_required") is True:
        q.append("аванс")
    if payment.get("late_payment_penalty_enabled") is True:
        q.append("неустойка пеня проценты")
    return " ".join(q)


# Конструктор запросов: DELIVERY TERMS

def build_delivery_query(language_mode: str, form: dict) -> str:
    lang = (language_mode or "ru").lower()

    if lang == "en":
        q = [
            "delivery terms", "delivery date", "delivery point", "shipment", "dispatch",
            "partial deliveries", "incoterms", "risk of loss", "packaging", "acceptance",
            "take delivery", "storage", "demurrage"
        ]
        return " ".join(q)

    q = [
        "условия поставки", "доставка", "срок поставки", "место поставки",
        "отгрузка", "перевозка", "инкотермс", "переход рисков",
        "упаковка", "маркировка", "приемка", "частичная поставка",
        "хранение", "простой", "демерредж"
    ]
    return " ".join(q)


# ГОТОВАЯ ФУНКЦИЯ RETRIEVAL: PAYMENT TERMS

def retrieve_payment_terms_bm25(
    form_input: dict,
    corpus_rows: List[dict],
    *,
    top_k: int = 3,
    max_docs: int = 800,
) -> List[str]:
    """
    Возвращает список прецедентов (строки) для PAYMENT_TERMS.
    """
    language_mode = form_input.get("language_mode", "ru")

    docs = build_docs_from_rows(
        corpus_rows,
        language_mode=language_mode,
        min_chars=80,
        max_chars=2600,
    )

    docs = filter_payment_terms(docs)

    if max_docs and len(docs) > max_docs:
        docs = docs[:max_docs]

    if not docs:
        return []

    idx = BM25Index(k1=1.5, b=0.75)
    idx.add_documents(docs)

    query = build_payment_query(language_mode, form_input)
    hits = idx.search(query, top_k=top_k)

    chosen: List[str] = []
    used_doc_ids: Set[str] = set()

    for i, _score in hits:
        d = docs[i]
        if d.doc_id and d.doc_id in used_doc_ids:
            continue

        candidate = d.text
        candidate = mask_form_variables(candidate, form_input)

        if any(_too_similar(candidate, prev) for prev in chosen):
            continue

        chosen.append(candidate)
        if d.doc_id:
            used_doc_ids.add(d.doc_id)

        if len(chosen) >= top_k:
            break

    return chosen


# ФУНКЦИЯ RETRIEVAL: DELIVERY TERMS


def retrieve_delivery_terms_bm25(
    form_input: dict,
    corpus_rows: List[dict],
    *,
    top_k: int = 3,
    max_docs: int = 800,
) -> List[str]:
    """
    Возвращает список прецедентов (строки) для DELIVERY_TERMS.

    Логика как у Payment:
    - docs из корпуса
    - приоритет section_id == delivery_terms (если заполнен)
    - доменный фильтр delivery (если section_id пустой в корпусе)
    - BM25 + диверсификация
    - mask_form_variables (мягко)
    """
    language_mode = form_input.get("language_mode", "ru")

    docs_all = build_docs_from_rows(
        corpus_rows,
        language_mode=language_mode,
        min_chars=80,
        max_chars=2600,
    )

    if not docs_all:
        return []

    docs_sid = [d for d in docs_all if (d.section_id or "").strip().lower() == "delivery_terms"]
    docs_filt = filter_delivery_terms(docs_all)

    merged: List[Doc] = []
    seen_keys = set()

    def _add_many(lst: List[Doc]) -> None:
        for d in lst:
            key = (d.doc_id, d.section_id, d.title, d.text[:160])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(d)

    _add_many(docs_sid)
    _add_many(docs_filt)

    docs = merged

    if max_docs and len(docs) > max_docs:
        docs = docs[:max_docs]

    if not docs:
        return []

    idx = BM25Index(k1=1.5, b=0.75)
    idx.add_documents(docs)

    query = build_delivery_query(language_mode, form_input)
    hits = idx.search(query, top_k=top_k)

    chosen: List[str] = []
    used_doc_ids: Set[str] = set()

    for i, _score in hits:
        d = docs[i]
        if d.doc_id and d.doc_id in used_doc_ids:
            continue

        candidate = d.text
        candidate = mask_form_variables(candidate, form_input)

        if any(_too_similar(candidate, prev) for prev in chosen):
            continue

        chosen.append(candidate)
        if d.doc_id:
            used_doc_ids.add(d.doc_id)

        if len(chosen) >= top_k:
            break

    return chosen
