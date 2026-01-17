# src/generation/delivery_terms_generate.py
# src/generation/delivery_terms_generate.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


def _norm_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _pick_snippets(precedents: List[str], *, max_snippets: int = 6) -> List[str]:
    """
    Берём короткие "полезные" фразы из прецедентов как подсказки стилю.
    Только формулировки; факты брать нельзя (сроки, адреса, Incoterms, компании, номера пунктов).
    """
    if not precedents:
        return []

    keywords = [
        "постав", "достав", "отгруз", "shipment", "delivery",
        "срок", "сроки", "estimated", "delay",
        "место", "пункт", "delivery point",
        "риск", "risk", "переход", "title",
        "приемк", "акт", "накладн", "упд", "acceptance",
        "упаков", "маркир", "погруз", "разгруз",
        "парт", "частичн", "partial", "split",
        "приостанов", "suspend",
        "форс", "force majeure",  # иногда в доставке встречается как риск/задержки
    ]

    out: List[str] = []
    seen = set()

    for p in precedents:
        text = re.sub(r"\s+", " ", p).strip()
        sents = re.split(r"(?<=[.!?])\s+", text)
        for s in sents:
            s2 = s.strip()
            if "[" in s2 or "]" in s2:
                continue
            if len(s2) < 60 or len(s2) > 240:
                continue
            low = s2.lower()
            if not any(k in low for k in keywords):
                continue
            if low in seen:
                continue
            seen.add(low)
            out.append(s2)
            if len(out) >= max_snippets:
                return out

    return out


# ------------------------------
# Form mapping (schema-light)
# ------------------------------
@dataclass
class DeliveryTermsParams:
    delivery_term_days: int
    delivery_trigger: str
    partial_deliveries_allowed: bool
    delivery_place: str
    incoterms: str
    risk_transfer: str
    acceptance_docs: str
    packaging_required: bool


def _get_delivery_block(form_input: dict) -> dict:
    d = form_input.get("delivery")
    if isinstance(d, dict):
        return d
    return {}


def _parse_params(form_input: dict) -> DeliveryTermsParams:
    """
    Консервативные дефолты. Если поля нет — ставим безопасное значение.
    """
    d = _get_delivery_block(form_input)

    return DeliveryTermsParams(
        delivery_term_days=int(d.get("delivery_term_days")),
        delivery_trigger=str(d.get("delivery_trigger", "с даты подписания договора")),
        partial_deliveries_allowed=bool(d.get("partial_deliveries_allowed", True)),
        delivery_place=str(d.get("delivery_place", "в согласованное место поставки")),
        incoterms=str(d.get("incoterms", "")),
        risk_transfer=str(d.get("risk_transfer", "в момент передачи товара Покупателю")),
        acceptance_docs=str(d.get("acceptance_docs", "")),
        packaging_required=bool(d.get("packaging_required", True)),
    )

def _lang(form_input: dict) -> str:
        lm = (form_input.get("language_mode") or form_input.get("language") or "ru").strip().lower()
        return "en" if lm.startswith("en") else "ru"


def _output_language_instruction(form_input: dict) -> str:
        return "Write in English." if _lang(form_input) == "en" else "Пиши на русском."

def build_delivery_terms_prompt(form_input: dict, precedents_clean: List[str]) -> str:
    """
    Промпт для секции Delivery Terms / Условия поставки.
    Требование: НЕ МЕНЕЕ 20 подпунктов (2.1 ... 2.20+).
    """
    p = _parse_params(form_input)
    snippets = _pick_snippets(precedents_clean, max_snippets=6)

    party_vocab = [
        "Используй термины Сторон единообразно по всему тексту: «Покупатель» и «Поставщик».",
        "НЕ используй в этой секции термины «Заказчик», «Исполнитель», «Продавец», если уже используешь «Покупатель/Поставщик».",
    ]

    requirements = [
        f"- Срок поставки: {p.delivery_term_days} дней.",
        f"- Начало течения срока поставки (триггер): {p.delivery_trigger}.",
        f"- Частичные поставки/поставка партиями: {'разрешены' if p.partial_deliveries_allowed else 'не допускаются без отдельного согласования'}.",
        f"- Место поставки: {p.delivery_place}.",
        f"- Incoterms: {p.incoterms if p.incoterms.strip() else 'не указывать (если не задано формой)'}.",
        f"- Переход рисков: {p.risk_transfer}.",
        f"- Документы приемки: {p.acceptance_docs if p.acceptance_docs.strip() else 'оформляются стандартные документы поставки (без реквизитов)'}.",
        f"- Упаковка/маркировка: {'обязательны' if p.packaging_required else 'по согласованию'}.",
    ]

    # ✅ Требование 20+ подпунктов
    structure_requirements = [
        "Структура раздела:",
        "- НЕ МЕНЕЕ 20 подпунктов.",
        "- Формат подпунктов: строго 2.1, 2.2, 2.3, ... (минимум до 2.20, можно больше).",
        "- Каждый подпункт — с новой строки.",
        "- Каждый подпункт — одно законченное юридическое предложение.",
        "- Каждый подпункт раскрывает ОТДЕЛЬНЫЙ аспект поставки и НЕ повторяет другие (ни дословно, ни по смыслу).",
        "- Если получилось менее 20 подпунктов — считай ответ НЕЗАВЕРШЁННЫМ и дополни до 20+ без повторов.",
    ]

    # ✅ План тем расширен до 20 (минимум), с возможностью 21–24
    topic_plan = [
        "Разрешённые темы (покрой все, без повторов; 1 тема = 1 подпункт):",
        "1) Общий принцип поставки: поставка осуществляется Поставщиком в адрес Покупателя/в место поставки.",
        f"2) Срок поставки: {p.delivery_term_days} дней.",
        f"3) Начало течения срока поставки: {p.delivery_trigger}.",
        f"4) Место поставки: {p.delivery_place}.",
        "5) График поставки: согласование графика/партии без ссылок на иные секции.",
        "6) Частичные поставки: допустимость и порядок согласования (строго по форме).",
        "7) Досрочная поставка: допустимость и порядок согласования.",
        "8) Условия отгрузки: подготовка товара к отгрузке и готовность к передаче.",
        "9) Перевозка/логистика: кто организует перевозку (без конкретных адресов/перевозчиков).",
        "10) Погрузка: распределение обязанностей по погрузке (общими словами).",
        "11) Разгрузка: распределение обязанностей по разгрузке (общими словами).",
        f"12) Переход рисков: {p.risk_transfer}.",
        "13) Переход права собственности: нейтрально и кратко (без ссылок на другие разделы).",
        "14) Упаковка: требования к упаковке для сохранности при перевозке.",
        "15) Маркировка: требования к маркировке для идентификации партии/единиц товара.",
        "16) Комплектность: поставка в комплектности согласно согласованной спецификации (без конкретики).",
        "17) Проверка количества: общий порядок проверки по количеству при приемке.",
        "18) Проверка качества: общий порядок проверки качества при приемке (без споров/претензий).",
        "19) Документы поставки: накладная/акт/УПД — общими словами, без реквизитов.",
        "20) Подписание приемочных документов: порядок оформления и фиксации передачи товара.",
        "Если нужно 21–24 подпункта: добавь пункты про сроки осмотра/проверки, корректировку графика поставки, замены упаковки/перемаркировку — но строго без штрафов и споров.",
    ]

    forbidden_topics = [
        "Запрещено упоминать (это другие секции договора):",
        "- Оплата/расчеты/банковские реквизиты/счета как платежные документы.",
        "- Ответственность/штрафы/пени/убытки за просрочку поставки (это liability/penalties).",
        "- Споры/арбитраж/суд/претензии/претензионный порядок/переговоры.",
        "- Уведомления (notices) как отдельная секция и строгие формальные процедуры.",
        "- Платежи, счета, инвойсы, штрафы, неустойки,право приостановления, расторжение, споры, суд, арбитраж.",
    ]

    constraints = [
        "Не копируй факты из прецедентов (адреса, сроки, Incoterms, валюты, названия компаний/стран, номера пунктов).",
        "Все условия и переключатели берутся ТОЛЬКО из Input Form.",
        "Не повторяй предложения и фразы: каждое утверждение должно появляться только один раз.",
        "Не используй плейсхолдеры вида [DATE]/[ADDRESS]/[TERM_DAYS] в финальном тексте.",
    ]

    mandatory_structure = (
        "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К СТРУКТУРЕ:\n"
        "- Раздел ДОЛЖЕН содержать НЕ МЕНЕЕ 20 подпунктов.\n"
        "- Формат подпунктов: строго 2.1, 2.2, 2.3, ... (минимум до 2.20) с точкой после номера.\n"
        "- Каждый подпункт — с новой строки.\n"
        "- Каждый подпункт — одно законченное юридическое предложение.\n"
        "- НЕЛЬЗЯ объединять несколько условий в один подпункт.\n"
        "- Если получилось меньше 20 подпунктов — добавь новые подпункты (по разрешённым темам) до 20+.\n"
    )

    return _norm_spaces(
        f"""
Ты — помощник юриста. Сгенерируй раздел договора "Delivery Terms / Условия поставки".

{mandatory_structure}

Параметры (обязательно соблюдай):
{chr(10).join(requirements)}

Термины сторон (обязательно соблюдай):
{chr(10).join(f"- {x}" for x in party_vocab)}

Структурные требования (обязательно соблюдай):
{chr(10).join(structure_requirements)}

План тем (обязательно соблюдай):
{chr(10).join(topic_plan)}

Запрещённые темы (обязательно соблюдай):
{chr(10).join(forbidden_topics)}

Фразы-ориентиры (ТОЛЬКО стиль/формулировки, не факты):
{chr(10).join(f"- {s}" for s in snippets) if snippets else "- (нет)"}

Ограничения:
{chr(10).join(f"- {c}" for c in constraints)}

Сгенерируй ТОЛЬКО текст раздела (без заголовка). {_output_language_instruction(form_input)}
"""
    )
