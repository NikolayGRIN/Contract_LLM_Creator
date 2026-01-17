from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


# ============================================================
# НАСТРОЙКИ ВХОДА / ВЫХОДА
# ============================================================
DOCX_DIR = Path(r"data/contracts_docx_healed")
OUT_SEGMENTED = Path(r"data/segmented_contracts.jsonl")
OUT_CORPUS = Path(r"data/corpus_sections.jsonl")

MIN_SECTION_TEXT_CHARS = 80

# ВАЖНО: мы больше НЕ используем агрессивную нормализацию, которая убивает пунктуацию/регистр.
# Все "чистки" — только про пробелы/переносы/дубликаты абзацев.


# ============================================================
# УТИЛИТЫ ТЕКСТА
# ============================================================
def _normalize_spaces(s: str) -> str:
    # Убираем неразрывные пробелы и лишние пробелы, но СОХРАНЯЕМ пунктуацию и регистр.
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _norm_key(s: str) -> str:
    # Ключ для дедупликации строк: без лишних пробелов, в нижнем регистре.
    return _normalize_spaces(s).casefold()


def _dedupe_lines_keep_order(lines: List[str], window: int = 25) -> List[str]:
    """
    Убираем повторяющиеся строки/абзацы (частая проблема после извлечения docx),
    но не "вырезаем" всё подряд: держим скользящее окно.
    """
    out: List[str] = []
    recent: List[str] = []
    recent_set = set()

    for ln in lines:
        ln = _normalize_spaces(ln)
        if not ln:
            continue
        key = ln.casefold()
        if key in recent_set:
            continue
        out.append(ln)
        recent.append(key)
        recent_set.add(key)

        if len(recent) > window:
            old = recent.pop(0)
            recent_set.discard(old)

    return out


def _remove_title_echo_from_body(title: str, body_lines: List[str]) -> List[str]:
    """
    Часто заголовок "попадает" в тело секции (или даже несколько раз).
    Удаляем его из начала тела, если он совпадает по нормализованному ключу.
    """
    tkey = _norm_key(title)
    out = body_lines[:]

    # Удаляем подряд идущие повторы заголовка в начале секции
    while out and _norm_key(out[0].rstrip(":")) == tkey:
        out.pop(0)

    return out


def infer_language(text: str) -> str:
    # Очень грубая эвристика: достаточно для RU/EN.
    t = text or ""
    latin = sum(1 for ch in t if "a" <= ch.lower() <= "z")
    cyr = sum(1 for ch in t if ("а" <= ch.lower() <= "я") or ch.lower() == "ё")
    if latin > cyr and latin > 20:
        return "en"
    return "ru"


def normalize_title(title: str) -> str:
    # Нормализуем пробелы, убираем двоеточие справа
    t = _normalize_spaces(title).rstrip(":").strip()
    return t


# ============================================================
# ИТЕРАЦИЯ ПО БЛОКАМ DOCX В ПОРЯДКЕ ДОКУМЕНТА
# ============================================================
def iter_block_items(doc: Document) -> Iterable[Tuple[str, Paragraph, str]]:
    """
    Возвращаем блоки документа в порядке: paragraph / table-cell paragraph.

    КЛЮЧЕВОЕ ИЗМЕНЕНИЕ (по нашему анализу):
    - НЕ используем child.iter() по XML и node.text, потому что это легко даёт дубли
      и "склейки" (особенно когда повторяются runs).
    - Привязываем XML-элементы к объектам python-docx Paragraph/Table.
    """

    body = doc.element.body
    for child in body.iterchildren():
        tag = getattr(child, "tag", "").lower()

        # Параграф
        if tag.endswith("}p"):
            p = Paragraph(child, doc)
            text = _normalize_spaces(p.text)
            if text:
                yield ("p", p, text)

        # Таблица
        elif tag.endswith("}tbl"):
            tbl = Table(child, doc)
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        text = _normalize_spaces(p.text)
                        if text:
                            yield ("t", p, text)


# ============================================================
# HEADING LOGIC (эвристики + стили)
# ============================================================
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
    x = _normalize_spaces(s).lower()
    if not x:
        return True
    if len(x) <= 2:
        return True
    for pat in NOISE_HEADING_PATTERNS:
        if re.match(pat, x):
            return True

    # Реквизитные/кодовые короткие строки с большим числом цифр
    if re.fullmatch(r"[\w\-/.,:;() ]{1,25}", s) and sum(ch.isdigit() for ch in s) >= 6:
        return True

    return False


def _style_says_heading(p: Paragraph) -> bool:
    """
    ВАЖНО: в docx заголовки часто помечены стилями.
    Это самый надёжный сигнал и как раз помогает не "угадать" заголовок по CAPS.
    """
    try:
        name = (p.style.name or "").strip().lower()
    except Exception:
        return False

    # RU/EN варианты встречающихся названий
    # "Heading 1", "Heading 2", "Заголовок 1", ...
    return (
        name.startswith("heading")
        or name.startswith("заголовок")
        or name.startswith("header")  # иногда встречается
    )


def looks_like_heading(text: str, p: Optional[Paragraph] = None) -> bool:
    s = _normalize_spaces(text)
    if not s:
        return False
    if len(s) > 140:
        return False

    # 1) Приоритет: стиль документа
    if p is not None and _style_says_heading(p):
        return True

    # 2) Нумерованные заголовки: "5." / "3.2." / "10. TERMS"
    if re.match(r"^\d{1,3}(\.\d{1,3}){0,4}\.?\s+\S+", s):
        return True

    # 3) ALL CAPS короткие
    letters = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", s)
    if letters and len(s) <= 90:
        upper_ratio = sum(ch.isupper() for ch in letters) / max(1, len(letters))
        if upper_ratio > 0.88:
            return True

    # 4) "Заголовок:" короткий
    if s.endswith(":") and len(s) <= 90:
        return True

    return False


# ============================================================
# ROUTER: title -> (section_id, section_group)
# ============================================================
def map_section_id(title: str) -> Tuple[str, str]:
    """
    Минимальный роутер. Мы специально держим его консервативным:
    неизвестное => ("", "other")
    """
    t = (title or "").lower()

    # payment / price / invoicing
    if any(
        k in t
        for k in [
            "payment",
            "оплат",
            "расчет",
            "расчёт",
            "settlement",
            "invoic",
            "price",
            "цена",
            "стоимост",
        ]
    ):
        return ("payment_terms", "commercial")

    # delivery / acceptance / performance
    if any(
        k in t
        for k in [
            "delivery",
            "поставк",
            "отгруз",
            "shipment",
            "accept",
            "приемк",
            "приёмк",
            "performance",
            "срок",
        ]
    ):
        return ("delivery_terms", "commercial")

    # liability / penalties
    if any(k in t for k in ["liabil", "responsib", "ответствен", "неустойк", "штраф", "пен", "penalt"]):
        return ("liability_penalties", "liability")

    # disputes / governing law
    if any(
        k in t
        for k in ["dispute", "спор", "арбит", "jurisdiction", "подсуд", "governing law", "применим", "право"]
    ):
        return ("disputes_governing_law", "disputes")

    return ("", "other")


# ============================================================
# СЕГМЕНТАЦИЯ
# ============================================================
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

    last_heading_key: Optional[str] = None  # помогает гасить "заголовок-заголовок-заголовок"

    def flush() -> None:
        nonlocal current_lines, current_title, last_heading_key, sections

        # 1) Дедуп строк/абзацев внутри секции (ключевая правка против повтора заголовка 2-3 раза)
        lines = _dedupe_lines_keep_order(current_lines, window=25)

        # 2) Убираем "эхо" заголовка в начале секции
        lines = _remove_title_echo_from_body(current_title, lines)

        body = "\n".join(lines).strip()
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
        last_heading_key = _norm_key(current_title)

    for kind, p, text in iter_block_items(doc):
        line = text  # уже нормализован по пробелам

        # 1) проверяем заголовок
        if looks_like_heading(line, p) and not is_noise_heading(line):
            candidate_title = normalize_title(line)

            # 2) защитный фильтр: если один и тот же заголовок повторяется подряд — игнорируем повтор
            ckey = _norm_key(candidate_title)
            if last_heading_key is not None and ckey == last_heading_key:
                # НЕ делаем flush повторно, просто пропускаем этот дубль заголовка
                continue

            # 3) начинаем новую секцию
            flush()
            current_title = candidate_title
            last_heading_key = ckey
            continue

        # Обычный текст секции (важно: добавляем как отдельную строку, не склеиваем без разделителя)
        current_lines.append(line)

    flush()
    return sections


# ============================================================
# BUILD OUTPUTS
# ============================================================
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
