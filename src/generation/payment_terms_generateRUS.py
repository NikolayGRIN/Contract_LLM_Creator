from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


def _norm_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def postprocess_payment_terms(text: str) -> str:
    """
    Нормализует вывод LLM, чтобы он проходил валидатор и выглядел аккуратно:
    - убирает пустые строки между подпунктами
    - нормализует пробелы
    - гарантирует формат '1.1.' + пробел
    """
    t = (text or "").strip()

    # убрать пустые строки (модель любит вставлять \n\n)
    t = re.sub(r"\n\s*\n+", "\n", t)

    # нормализуем "1.1." -> "1.1. "
    t = re.sub(r"^(\s*\d+\.\d+\.)\s*", r"\1 ", t, flags=re.MULTILINE)

    # финальная чистка пробелов/табов
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def _pick_snippets(precedents: List[str], *, max_snippets: int = 6) -> List[str]:
    """
    Берём короткие "полезные" фразы из прецедентов как подсказки стилю.
    Только формулировки; факты брать нельзя (суммы/сроки/валюта/ссылки).
    """
    if not precedents:
        return []

    keywords = [
        "оплат", "платеж", "платёж", "счет", "счёт", "инвойс", "invoice",
        "дата оплаты", "датой оплаты", "банковск", "комисси", "ндс", "vat",
        "предоплат", "аванс", "удержан", "withholding", "приостанов",
        "suspension", "пен", "неустойк", "penalt",
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
# Form mapping (your schema)
# ------------------------------
@dataclass
class PaymentTermsParams:
    payment_trigger: str                # invoice_date / acceptance_date / delivery_date / etc.
    payment_term_days: int
    prepayment_required: bool
    bank_details_included: bool
    withholding_allowed: bool
    suspension_right: bool
    bank_charges: str                   # payer / beneficiary / shared
    vat_mode: str                       # exclusive_if_any / inclusive / not_applicable
    late_payment_penalty_enabled: bool


def _get_payment_block(form_input: dict) -> dict:
    p = form_input.get("payment")
    if isinstance(p, dict):
        return p
    return {}


def _parse_params(form_input: dict) -> PaymentTermsParams:
    """
    Строгий парсинг из form_input["payment"].
    Если какого-то поля нет — ставим дефолт (консервативный).
    """
    p = _get_payment_block(form_input)

    return PaymentTermsParams(
        payment_trigger=str(p.get("payment_trigger", "invoice_date")),
        payment_term_days=int(p.get("payment_term_days", 30)),
        prepayment_required=bool(p.get("prepayment_required", False)),
        bank_details_included=bool(p.get("bank_details_included", False)),
        withholding_allowed=bool(p.get("withholding_allowed", False)),
        suspension_right=bool(p.get("suspension_right", False)),
        bank_charges=str(p.get("bank_charges", "payer")),
        vat_mode=str(p.get("vat_mode", "exclusive_if_any")),
        late_payment_penalty_enabled=bool(p.get("late_payment_penalty_enabled", False)),
    )


def _trigger_phrase(trigger: str) -> str:
    t = (trigger or "").lower().strip()
    mapping = {
        "invoice_date": "с даты выставления счета/инвойса",
        "receipt_of_invoice": "с даты получения счета/инвойса",
        "acceptance_date": "с даты подписания документов, подтверждающих приемку",
        "delivery_date": "с даты поставки (отгрузки) товара",
        "signing_date": "с даты подписания договора",
    }
    return mapping.get(t, "с даты наступления согласованного события (invoice/acceptance/delivery)")


def _bank_charges_phrase(bank_charges: str) -> str:
    t = (bank_charges or "").lower().strip()
    mapping = {
        "payer": "банковские комиссии несет плательщик",
        "beneficiary": "банковские комиссии несет получатель",
        "shared": "банковские комиссии распределяются между Сторонами по согласованию",
    }
    return mapping.get(t, "банковские комиссии распределяются в соответствии с согласованием Сторон")


def _vat_mode_phrase(vat_mode: str) -> str:
    t = (vat_mode or "").lower().strip()
    mapping = {
        "exclusive_if_any": "НДС/VAT начисляется сверх цены, если подлежит применению",
        "inclusive": "НДС/VAT включен в цену, если подлежит применению",
        "not_applicable": "НДС/VAT не применяется",
    }
    return mapping.get(t, "НДС/VAT применяется (или не применяется) в соответствии с применимым законодательством")


def build_payment_terms_prompt(form_input: dict, precedents_clean: List[str]) -> str:
    """
    Промпт для LLM: генерируем секцию Payment Terms,
    используя параметры формы и фразы-ориентиры из прецедентов.
    """
    p = _parse_params(form_input)
    snippets = _pick_snippets(precedents_clean, max_snippets=6)

    party_vocab = [
        "Используй термины Сторон единообразно по всему тексту: «Покупатель» и «Поставщик».",
        "НЕ используй в этой секции термины «Заказчик», «Исполнитель», «Продавец», если уже используешь «Покупатель/Поставщик».",
    ]

    requirements = [
        f"- Срок оплаты: {p.payment_term_days} дней {_trigger_phrase(p.payment_trigger)}.",
        f"- Предоплата: {'требуется' if p.prepayment_required else 'не требуется'}.",
        f"- Удержания/зачеты: {'разрешены' if p.withholding_allowed else 'не допускаются, если иное не согласовано'}.",
        f"- Приостановление исполнения при просрочке: {'право есть' if p.suspension_right else 'право не предоставляется'}.",
        f"- Банковские комиссии: {_bank_charges_phrase(p.bank_charges)}.",
        f"- НДС/VAT: {_vat_mode_phrase(p.vat_mode)}.",
        f"- Неустойка за просрочку оплаты: {'включить' if p.late_payment_penalty_enabled else 'не включать'}.",
        f"- Банковские реквизиты включены в договор: {'да' if p.bank_details_included else 'нет'}.",
    ]

    topic_plan = [
        "Разрешённые темы (покрой все, без повторов):",
        "1) Форма расчетов, Основание оплаты: счет/инвойс как основание.",
        f"2) Срок оплаты: {p.payment_term_days} дней {_trigger_phrase(p.payment_trigger)}.",
        "3) Момент исполнения: только зачисление на счет Поставщика (или только списание) — выбери одно и держись его.",
        "4) Валюта и способ платежа: безналичный перевод (без сумм/валюты, если их нет в форме).",
        "5) Частичная оплата/предоплата: строго по форме.",
        "6) Удержания/зачеты: строго по форме.",
        "7) Банковские комиссии: строго по форме.",
        "8) НДС/VAT: строго по форме.",
        "9) Счет/инвойс: минимальный набор сведений и допустимость электронного счета (без реквизитов).",
        "10) Порядок обмена счетами/инвойсами (электронная форма/копии)."
        "11) Подтверждающие документы по поставке/приемке: общие виды (накладная/акт), без номеров и реквизитов.",
        "12) Порядок сверки взаиморасчетов: акт сверки по запросу стороны/периодичность (без дублей).",
        "13) Запрет/условия приостановления исполнения при просрочке (если включено).",
        "14) Порядок исправления ошибок в счете: корректировочный счет/инвойс (без сроков, если их нет в форме).",
        "15) Порядок зачета переплат/ошибочных платежей: возврат/зачет по согласованию (без деталей реквизитов).",
        "16) Каналы обмена счетами/инвойсами: электронная форма/копии, порядок подтверждения получения.",    
        "Если нужно 20 подпунктов: детализируй внутри этих тем, не добавляя новые разделы договора.",
    ]

    forbidden_topics = [
        "Запрещено упоминать (это другие секции договора):",
        "- Споры/арбитраж/суд/претензии/переговоры.",
        "- Notices/уведомления как отдельный порядок.",
        "- Изменение договора/допсоглашения как общий механизм.",
        "- Убытки/общая ответственность (liability/remedies).",
        "- Банковские реквизиты в виде ИНН/КПП/БИК/SWIFT/IBAN/номер счета.",
    ]

    constraints = [
        "Не копируй факты и реквизиты из прецедентов (суммы, валюты, ставки, номера пунктов, названия компаний/стран, банковские реквизиты).",
        "Все условия и переключатели берутся ТОЛЬКО из Input Form.",
        "Не повторяй предложения и фразы.",
        "Не используй плейсхолдеры вида [AMOUNT]/[CURRENCY]/[TERM_DAYS].",
        "Если bank_details_included=false: нельзя писать ИНН/КПП/БИК/SWIFT/IBAN/номер счета; допускается общая фраза «на расчетный счет, указанный в договоре».",
        "Пиши грамматически корректно: «датой оплаты считается дата …», а не «считается дату».",
        "Избегай двоеточий; формулируй подпункт как одно цельное предложение.",
    ]

    mandatory_structure = (
        "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К СТРУКТУРЕ:\n"
        "- Раздел ДОЛЖЕН содержать НЕ МЕНЕЕ 20 подпунктов.\n"
        "- Формат подпунктов: строго 1.1., 1.2., 1.3., ...\n"
        "- Каждый подпункт — с новой строки, БЕЗ пустых строк между подпунктами.\n"
        "- Каждый подпункт — одно законченное юридическое предложение.\n"
        "- Каждый подпункт должен добавлять НОВУЮ информацию и НЕ повторять другие подпункты.\n"
        "- НЕЛЬЗЯ объединять несколько условий в один подпункт.\n"
        "- Если сомневаешься, добавь дополнительные подпункты.\n"
    )

    prompt = f"""
Ты — помощник юриста. Сгенерируй раздел договора "Payment Terms / Порядок расчетов".

{mandatory_structure}

Параметры (обязательно соблюдай):
{chr(10).join(requirements)}

Термины сторон (обязательно соблюдай):
{chr(10).join(f"- {x}" for x in party_vocab)}

План тем (обязательно соблюдай):
{chr(10).join(topic_plan)}

Запрещённые темы (обязательно соблюдай):
{chr(10).join(forbidden_topics)}

Фразы-ориентиры (ТОЛЬКО стиль/формулировки, не факты):
{chr(10).join(f"- {s}" for s in snippets) if snippets else "- (нет)"}

Ограничения:
{chr(10).join(f"- {c}" for c in constraints)}

Сгенерируй ТОЛЬКО текст раздела (без заголовка). 
""".strip()

    return _norm_spaces(prompt)
