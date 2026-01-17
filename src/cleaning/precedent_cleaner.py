from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple



# РАЗБИЕНИЕ НА ПРЕДЛОЖЕНИЯ

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9])")


def _split_sentences(text: str) -> List[str]:
    """
    Разбивает текст на предложения по простому правилу:
    точка/вопрос/восклицание + пробел + заглавная буква/цифра.
    """
    t = (text or "").strip()
    if not t:
        return []
    # Переносы строк приводим к пробелам для корректной логики предложений
    t = re.sub(r"\s+", " ", t).strip()
    return [s.strip() for s in _SENT_SPLIT_RE.split(t) if s.strip()]

# БАЗОВАЯ НОРМАЛИЗАЦИЯ ПРОБЕЛОВ

def _normalize_spaces(s: str) -> str:
    """
    Убирает неразрывные пробелы, лишние пробелы и лишние переводы строк,
    не трогая пунктуацию и регистр.
    """
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# ДЕДУПЛИКАЦИЯ С СОХРАНЕНИЕМ ПОРЯДКА

def _dedupe_keep_order(items: List[str]) -> List[str]:
    
    # Удаляет полностью дублирующиеся элементы.
   
    seen = set()
    out: List[str] = []
    for x in items:
        k = x.casefold()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def _dedupe_lines_window(text: str, window: int = 30) -> str:
    
    # Убирает повторяющиеся строки / абзацы    
    
    lines = [ln.strip() for ln in (text or "").splitlines()]
    out: List[str] = []
    recent: List[str] = []
    recent_set = set()

    for ln in lines:
        ln = _normalize_spaces(ln)
        if not ln:
            continue
        k = ln.casefold()
        if k in recent_set:
            continue
        out.append(ln)
        recent.append(k)
        recent_set.add(k)
        if len(recent) > window:
            old = recent.pop(0)
            recent_set.discard(old)

    return "\n".join(out).strip()



# УДАЛЕНИЕ "ЭХА" ЗАГОЛОВКОВ ВНУТРИ ТЕКСТА

def _remove_heading_echo(text: str) -> str:
   
    # Удаляет типичные повторы заголовков, которые часто попадают в тело секции   
   
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return ""

    def looks_caps_heading(ln: str) -> bool:
        letters = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", ln)
        if len(letters) < 4 or len(ln) > 90:
            return False
        upper = sum(1 for ch in letters if ch.isupper())
        return (upper / max(1, len(letters))) > 0.88

    # Удаляем 1–2 первых строк, если они выглядят как заголовки
    while lines and looks_caps_heading(lines[0]):
        lines.pop(0)

    return "\n".join(lines).strip()

# Валюты кодами 
_CURRENCY_RE = re.compile(
    r"\b(USD|EUR|RUB|GBP|CNY|CHF|AED|KZT|UAH|PLN|TRY|JPY)\b",
    re.IGNORECASE,
)

# Валюты словами (RU/EN) — покрывает "долларов", "евро", "злотых", "рублей" и т.п.
_CURRENCY_WORD_RE = re.compile(
    r"\b("
    r"доллар(?:а|ов)?|usd|"
    r"евро|eur|"
    r"руб(?:ль|ля|лей)|rub|"
    r"фунт(?:а|ов)?\s+стерлинг(?:ов)?|gbp|"
    r"злот(?:ый|ых|ого|ым|ыми)|pln|"
    r"юан(?:ь|я|ей)|cny|"
    r"тенге|kzt|"
    r"дирхам(?:а|ов)?|aed"
    r")\b",
    re.IGNORECASE,
)

# Убираем прилагательные/указатели страны перед плейсхолдером валюты:

_CURRENCY_ADJ_BEFORE_PLACEHOLDER_RE = re.compile(
    r"\bпольск\w*\s+\[CURRENCY\](?=[\s,.;:)\]]|$)",
    re.IGNORECASE,
)

# VAT/НДС
_VAT_RE = re.compile(r"\b(vat)\b|ндс", re.IGNORECASE)

# VAT/НДС со ставкой
_VAT_RATE_RE = re.compile(
    r"(?:(?:ндс|vat)\s*(?:в\s*размере\s*)?)\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*%",
    re.IGNORECASE,
)

# Проценты 
_PERCENT_RE = re.compile(r"(?<!\w)(\d{1,2}(?:[.,]\d{1,2})?)\s*%")

# Сроки в днях (цифрами), включая "банковских/рабочих дней"
_DAYS_RE = re.compile(
    r"\b(\d{1,3})\s*(?:day|days|banking\s+days|business\s+days|дн\.?|дней|дня|сут\.?|банковских\s+дней|рабочих\s+дней)\b",
    re.IGNORECASE,
)

# Сроки в днях (словами)
_DAYS_WORD_RE = re.compile(
    r"\b("
    r"одного|один|двух|два|трех|трёх|три|четырех|четырёх|четыре|"
    r"пяти|пять|шести|шесть|семи|семь|восьми|восемь|"
    r"девяти|девять|десяти|десять|"
    r"тридцати|тридцать|сорока|сорок"
    r")\b\s*(?:банковских\s+дней|рабочих\s+дней|дней|суток)?\b",
    re.IGNORECASE,
)

# Суммы
_AMOUNT_RE = re.compile(
    r"(?<!\w)(?:\d{1,3}(?:[ ,.\u00A0]\d{3})+(?:[.,]\d{1,2})?|\d{4,}(?:[.,]\d{1,2})?)(?!\w)"
)

# Удаляем расшифровки"чисел словами в скобках
_PARENS_NUMBER_WORD_RE = re.compile(
    r"\s*\(\s*"
    r"(?:одного|один|двух|два|трех|трёх|три|четырех|четырёх|четыре|"
    r"пяти|пять|шести|шесть|семи|семь|восьми|восемь|"
    r"девяти|девять|десяти|десять|"
    r"тридцати|тридцать|сорока|сорок)"
    r"\s*\)\s*",
    re.IGNORECASE,
)

# Если [AMOUNT] стоит после "пункт/п./раздел/статья", это не сумма, а ссылка на пункт договора
_AMOUNT_USED_AS_CLAUSE_RE = re.compile(
    r"\b(пункт[аеуы]?|п\.|раздел[аеуы]?|стать[еяи])\s+\[AMOUNT\]\b",
    re.IGNORECASE,
)

# Если [AMOUNT] используется как "кол-во банковских/рабочих дней" — это срок, а не сумма
_AMOUNT_USED_AS_DAYS_BANKING_RE = re.compile(
    r"\[AMOUNT\](\s+(?:банковских\s+дней|рабочих\s+дней|business\s+days|banking\s+days))",
    re.IGNORECASE,
)

# Если [AMOUNT] используется как "кол-во дней/дня/суток" 
_AMOUNT_USED_AS_DAYS_GENERIC_RE = re.compile(
    r"[«\"']?\[AMOUNT\][»\"']?(\s+(?:календарн(?:ых|ые)\s+)?(?:дней|дня|суток))",
    re.IGNORECASE,
)

# Удаляем межсекционные ссылки на пункты договора
_CLAUSE_REF_PHRASE_RE = re.compile(
    r"(?:,?\s*)?"
    r"(?:указанн\w*|предусмотренн\w*)\s+"
    r"(?:в\s+)?(пункте|п\.|разделе|статье)\s+"
    r"(?:\[[A-Z_]+\]|\d+(?:\.\d+)*)\s+"
    r"(?:настоящего|данного)\s+контракт\w*",
    re.IGNORECASE,
)


def anonymize_payment_terms(text: str) -> Tuple[str, int]:
    """
    Заменяет конкретные значения (факты) на канонические плейсхолдеры.
    Возвращает:
    - очищенный текст
    - количество произведённых замен
    """
    t = text or ""
    reps = 0

    # 0) Убираем расшифровки числа словами в скобках 
    t2, n = _PARENS_NUMBER_WORD_RE.subn(" ", t)
    reps += n
    t = t2

    # 1) VAT/НДС со ставкой 
    t2, n = _VAT_RATE_RE.subn("[VAT_RATE]", t)
    reps += n
    t = t2

    # 2) VAT/НДС как маркер 
    t2, n = _VAT_RE.subn("[VAT]", t)
    reps += n
    t = t2

    # 3) Валюты кодами
    t2, n = _CURRENCY_RE.subn("[CURRENCY]", t)
    reps += n
    t = t2

    # 4) Валюты словами
    t2, n = _CURRENCY_WORD_RE.subn("[CURRENCY]", t)
    reps += n
    t = t2

    # 4.1) Убираем "польских" перед [CURRENCY]
    t2, n = _CURRENCY_ADJ_BEFORE_PLACEHOLDER_RE.subn("[CURRENCY]", t)
    reps += n
    t = t2

    # 5) Проценты
    t2, n = _PERCENT_RE.subn("[PERCENT]", t)
    reps += n
    t = t2

    # 6) Сроки в днях (цифрами)
    def _days_sub(_: re.Match) -> str:
        nonlocal reps
        reps += 1
        return "[TERM_DAYS]"

    t = _DAYS_RE.sub(_days_sub, t)

    # 7) Сроки в днях (словами)
    def _days_word_sub(_: re.Match) -> str:
        nonlocal reps
        reps += 1
        return "[TERM_DAYS]"

    t = _DAYS_WORD_RE.sub(_days_word_sub, t)

    # 8) Суммы
    t2, n = _AMOUNT_RE.subn("[AMOUNT]", t)
    reps += n
    t = t2

    # 9) Контекстные исправления типа сущности:
    # [AMOUNT] как ссылка на пункт/раздел договора 
    t2, n = _AMOUNT_USED_AS_CLAUSE_RE.subn(r"\1 [CLAUSE_REF]", t)
    reps += n
    t = t2

    # [AMOUNT] как срок в банковских/рабочих днях 
    t2, n = _AMOUNT_USED_AS_DAYS_BANKING_RE.subn(r"[TERM_DAYS]\1", t)
    reps += n
    t = t2

    # [AMOUNT] как срок в "днях/дня/сутках" (в т.ч. «[AMOUNT]» дней) 
    t2, n = _AMOUNT_USED_AS_DAYS_GENERIC_RE.subn(r"[TERM_DAYS]\1", t)
    reps += n
    t = t2

    # Удаляем межсекционные ссылки на пункты договора целиком
    t2, n = _CLAUSE_REF_PHRASE_RE.subn("", t)
    reps += n
    t = t2

    t = _normalize_spaces(t)
    return t, reps



# БЕЗОПАСНАЯ ОБРЕЗКА ПО ГРАНИЦАМ ПРЕДЛОЖЕНИЙ

def truncate_sentence_safe(text: str, max_chars: int = 1500) -> str:
    """
    Обрезает текст по границе предложений, не допуская обрывов на полуслове.
    """
    t = _normalize_spaces(text)
    if len(t) <= max_chars:
        return t

    sents = _split_sentences(t)
    if not sents:
        return t[:max_chars].rsplit(" ", 1)[0].strip()

    out: List[str] = []
    cur = 0
    for s in sents:
        add = len(s) + (1 if out else 0)
        if cur + add > max_chars:
            break
        out.append(s)
        cur += add

    if not out:
        return sents[0][:max_chars].rsplit(" ", 1)[0].strip()

    return " ".join(out).strip()



# ОСНОВНОЙ CLEANER ДЛЯ PAYMENT TERMS

@dataclass
class CleanReport:
    
    input_count: int
    output_count: int
    dropped_empty: int
    dropped_duplicates: int
    total_replacements: int


def clean_precedents_payment_terms(
    precedents: List[str],
    *,
    min_chars: int = 120,
    max_chars: int = 1500,
) -> Tuple[List[str], CleanReport]:
    """
    Основная функция очистки прецедентов для секции Payment Terms.
    Вход: raw precedents (как пришли из BM25)
    Выход: список очищенных прецедентов
    """
    input_count = len(precedents)
    dropped_empty = 0

    # 1) Нормализация + удаление эха заголовков + дедуп строк
    normalized: List[str] = []
    for p in precedents:
        t = _normalize_spaces(p)
        t = _remove_heading_echo(t)
        t = _dedupe_lines_window(t, window=30)
        t = t.strip()
        if len(t) < min_chars:
            dropped_empty += 1
            continue
        normalized.append(t)

    # 2) Анонимизация
    anonymized: List[str] = []
    total_reps = 0
    for t in normalized:
        t2, reps = anonymize_payment_terms(t)
        total_reps += reps
        anonymized.append(t2)

    # 3) Обрезка по предложениям
    truncated = [truncate_sentence_safe(t, max_chars=max_chars) for t in anonymized]

    # 4) Финальная дедупликация целых прецедентов
    before = len(truncated)
    unique = _dedupe_keep_order([t for t in truncated if t.strip()])
    dropped_duplicates = before - len(unique)

    report = CleanReport(
        input_count=input_count,
        output_count=len(unique),
        dropped_empty=dropped_empty,
        dropped_duplicates=dropped_duplicates,
        total_replacements=total_reps,
    )
    return unique, report

def clean_precedents_delivery_terms(*args, **kwargs):
    # пока используем тот же cleaner, что и для payment_terms
    return clean_precedents_payment_terms(*args, **kwargs)
