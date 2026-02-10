# src/validation/contract_generation_metrics.py
from __future__ import annotations

import re
import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Any


# ============================================================
# 0) Типы и утилиты
# ============================================================

Vector = List[float]
EmbedFn = Callable[[str], Vector]


def cosine(a: Vector, b: Vector) -> float:
    """Cosine similarity for python lists (no numpy dependency)."""
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        x = float(a[i])
        y = float(b[i])
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def normalize_ws(s: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", (s or "")).strip()


def strip_control_chars(s: str) -> str:
    # Удаляем управляющие символы, оставляя \n
    s = s or ""
    return "".join(ch for ch in s if ch == "\n" or (ord(ch) >= 32 and ord(ch) != 127))


def text_no_spaces_len(s: str) -> int:
    return len(re.sub(r"\s+", "", s or ""))


def split_sentences(text: str) -> List[str]:
    """
    Простой splitter (достаточно для сигналов повторов).
    """
    t = normalize_ws((text or "").replace("\n", " "))
    if not t:
        return []
    parts = re.split(r"(?<=[\.\!\?\;\:])\s+|\s*\n+\s*", t)
    out = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out


# ============================================================
# 1) Валидаторы: язык / cross-refs / обрыв / мусор
# ============================================================

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

# Ловим любые cross-reference формулировки в EN + сами "section/clause/article N.N"
CROSSREF_RE = re.compile(
    r"\b("
    r"as\s+per|as\s+specified\s+in|as\s+defined\s+in|in\s+accordance\s+with|pursuant\s+to|under|see|as\s+set\s+forth\s+in"
    r")\s+(section|clause|article)\s+\d+(\.\d+)*\b"
    r"|\b(section|clause|article)\s+\d+(\.\d+)*\b",
    flags=re.IGNORECASE,
)

# Мусор/плейсхолдеры
GARBAGE_RE = re.compile(
    r"(\*\*\*\*|####|<\s*todo\s*>|\[?\s*insert\s*.*?\]?|\[?\s*tbd\s*\]?|{+|}+)",
    re.IGNORECASE,
)


def validate_language_purity(text: str, language_mode: str) -> Tuple[bool, str]:
    """
    EN: не должно быть кириллицы.
    RU: допускаем латиницу (в договорах это нормально: Incoterms, VAT, etc.).
    """
    lang = (language_mode or "ru").lower()
    t = text or ""
    if lang == "en":
        if CYRILLIC_RE.search(t):
            return False, "EN output contains Cyrillic characters."
    return True, "ok"


def validate_no_crossrefs(text: str) -> Tuple[bool, str]:
    if CROSSREF_RE.search(text or ""):
        return False, "Cross-references detected (section/clause/article references)."
    return True, "ok"


def validate_no_garbage(text: str) -> Tuple[bool, str]:
    if GARBAGE_RE.search(text or ""):
        return False, "Garbage placeholders detected (****/TBD/etc)."
    return True, "ok"


def looks_truncated(text: str) -> Tuple[bool, str]:
    """
    Детектор "обрыва":
    - нет финальной пунктуации (.!?…)
    - заканчивается на букву/цифру
    """
    t = (text or "").rstrip()
    if not t:
        return False, "empty"
    if re.search(r"[\.!\?…]\s*$", t):
        return False, "ok"
    if re.search(r"[A-Za-zА-Яа-яЁё0-9]\s*$", t):
        return True, "Likely truncated (no ending punctuation)."
    return False, "ok"


# ============================================================
# 2) Метрики повторов
# ============================================================

def repetition_score(text: str) -> Dict[str, Any]:
    """
    - sentence_unique_ratio: уникальные предложения / все предложения
    - max_sentence_dup_count: максимальное число повторов одного предложения
    """
    sents = split_sentences(text)
    if not sents:
        return {
            "sentence_count": 0,
            "sentence_unique_ratio": 1.0,
            "max_sentence_dup_count": 1,
            "top_repeated_sentences": [],
        }

    norm = [normalize_ws(x).lower() for x in sents]
    freq: Dict[str, int] = {}
    for x in norm:
        freq[x] = freq.get(x, 0) + 1

    unique_ratio = len(freq) / max(1, len(norm))
    max_dup = max(freq.values()) if freq else 1

    repeated = sorted([(k, v) for k, v in freq.items() if v > 1], key=lambda kv: kv[1], reverse=True)[:3]
    examples = [{"count": v, "sentence": k[:220]} for k, v in repeated]

    return {
        "sentence_count": len(sents),
        "sentence_unique_ratio": float(unique_ratio),
        "max_sentence_dup_count": int(max_dup),
        "top_repeated_sentences": examples,
    }


# ============================================================
# 3) Similarity-to-context (anti-hallucination proxy)
# ============================================================

def similarity_to_context(
    *,
    text: str,
    context_chunks: List[str],
    embed: Optional[EmbedFn] = None,
    max_chunks: int = 12,
) -> Dict[str, Any]:
    """
    Если передан embedder, считаем cosine(text, chunk_i).
    """
    if not context_chunks:
        return {"enabled": False, "reason": "no_context", "sim_mean": None, "sim_max": None}
    if embed is None:
        return {"enabled": False, "reason": "no_embedder", "sim_mean": None, "sim_max": None}

    chunks = [c for c in context_chunks if (c or "").strip()][:max_chunks]
    if not chunks:
        return {"enabled": False, "reason": "empty_context", "sim_mean": None, "sim_max": None}

    t = (text or "").strip()
    if not t:
        return {"enabled": True, "reason": "empty_text", "sim_mean": 0.0, "sim_max": 0.0}

    v_text = embed(t)
    sims: List[float] = []
    for c in chunks:
        v_c = embed(c)
        sims.append(cosine(v_text, v_c))

    return {
        "enabled": True,
        "reason": "ok",
        "sim_mean": float(sum(sims) / len(sims)) if sims else 0.0,
        "sim_max": float(max(sims)) if sims else 0.0,
        "chunks_used": int(len(sims)),
    }


# ============================================================
# 4) Coverage по секциям (обязательные элементы)
# ============================================================

@dataclass
class CoverageSpec:
    patterns: List[str]
    min_hit_ratio: float = 0.6


def default_coverage_specs(language_mode: str) -> Dict[str, CoverageSpec]:
    """
    Минимальный набор coverage-паттернов. Расширяй под диплом.
    """
    lang = (language_mode or "ru").lower()

    if lang == "en":
        return {
            "definitions": CoverageSpec(
                patterns=[r"\bmeans\b|\bshall\s+mean\b", r"\bSeller\b|\bBuyer\b", r"\bContract\b"],
                min_hit_ratio=0.5,
            ),
            "subject_of_contract": CoverageSpec(
                patterns=[r"\bsupply\b|\bdeliver\b", r"\bEquipment\b|\bGoods\b", r"\bappendix\b|\bspecification\b"],
                min_hit_ratio=0.5,
            ),
            "price_and_taxes": CoverageSpec(
                patterns=[r"\bprice\b", r"\bcurrency\b|\bUSD|EUR|RUB|CNY\b", r"\bVAT\b|\btax\b"],
                min_hit_ratio=0.5,
            ),
            "payment_terms": CoverageSpec(
                patterns=[r"\bpayment\b", r"\binvoice\b", r"\bwithin\s+\d+\s+days\b", r"\bbank\b|\btransfer\b"],
                min_hit_ratio=0.6,
            ),
            "delivery_terms": CoverageSpec(
                patterns=[r"\bdelivery\b|\bshipment\b", r"\bplace\b|\bpoint\b", r"\bincoterms\b", r"\brisk\b"],
                min_hit_ratio=0.6,
            ),
            "acceptance_and_inspection": CoverageSpec(
                patterns=[r"\bacceptance\b|\binspection\b", r"\bnotify\b|\bnotice\b", r"\bdefect\b", r"\bwithin\s+\d+\s+days\b"],
                min_hit_ratio=0.6,
            ),
            "warranties": CoverageSpec(
                patterns=[r"\bwarrant", r"\bwarranty\s+period\b|\b\d+\s+months\b", r"\brepair\b|\breplace\b", r"\bdefect\b"],
                min_hit_ratio=0.6,
            ),
            "liability_and_penalties": CoverageSpec(
                patterns=[r"\bliabilit", r"\bcap\b|\blimited\b", r"\bindirect\b|\bconsequential\b", r"\bfraud\b|\bwilful\b|\bwillful\b"],
                min_hit_ratio=0.5,
            ),
            "force_majeure": CoverageSpec(
                patterns=[r"\bforce\s+majeure\b", r"\bnotify\b|\bnotice\b", r"\bmitigat", r"\bsuspend\b|\bresume\b", r"\bterminate\b"],
                min_hit_ratio=0.55,
            ),
            "governing_law_and_disputes": CoverageSpec(
                patterns=[r"\bgoverning\s+law\b|\bapplicable\s+law\b", r"\barbitration\b|\bcourt\b", r"\bseat\b|\bplace\b", r"\blanguage\b"],
                min_hit_ratio=0.6,
            ),
        }

    # RU
    return {
        "definitions": CoverageSpec(
            patterns=[r"\bПоставщик\b|\bПродавец\b", r"\bПокупатель\b", r"\bДоговор\b"],
            min_hit_ratio=0.5,
        ),
        "subject_of_contract": CoverageSpec(
            patterns=[r"\bпостав(ить|ка)\b|\bпереда(ть|ча)\b", r"\bспецификац|\bприложен", r"\bпринять\b|\bоплатить\b"],
            min_hit_ratio=0.55,
        ),
        "price_and_taxes": CoverageSpec(
            patterns=[r"\bцена\b", r"\bвалют", r"\bНДС\b|\bналог"],
            min_hit_ratio=0.55,
        ),
        "payment_terms": CoverageSpec(
            patterns=[r"\bоплат|\bплатеж|\bплатёж", r"\bсчет\b|\bсчёт\b", r"\bв\s+течение\s+\d+\s+(дней|дня)\b|\bсрок\s+оплат", r"\bбезналич|\bперевод\b"],
            min_hit_ratio=0.6,
        ),
        "delivery_terms": CoverageSpec(
            patterns=[r"\bпоставк|\bдоставк|\bотгруз", r"\bсрок\s+постав", r"\bместо\s+постав|\bместо\s+достав", r"\bриск|\bпереход\s+риск", r"\bинкотерм|\bIncoterms\b"],
            min_hit_ratio=0.55,
        ),
        "acceptance_and_inspection": CoverageSpec(
            patterns=[r"\bприемк|\bприёмк|\bинспекц", r"\bсрок\s+приемк|\bв\s+течение\s+\d+\s+(дней|дня)\b", r"\bуведом(ить|ление)\b", r"\bдефект|\bнесоответ"],
            min_hit_ratio=0.6,
        ),
        "warranties": CoverageSpec(
            patterns=[r"\bгаранти", r"\bгарантийн(ый|ого)\s+срок\b|\b\d+\s+(месяц|месяцев)\b", r"\bремонт|\bзамен", r"\bдефект|\bнедостат"],
            min_hit_ratio=0.6,
        ),
        "liability_and_penalties": CoverageSpec(
            patterns=[r"\bответственност", r"\bлимит\b|\bогранич", r"\bкосвенн|\bупущенн", r"\bмошеннич|\bумышлен"],
            min_hit_ratio=0.5,
        ),
        "force_majeure": CoverageSpec(
            patterns=[r"\bфорс-?мажор|\bнепреодолим", r"\bуведом(ить|ление)\b", r"\bприостан|\bвозобнов", r"\bминимиз|\bуменьш", r"\bрасторж"],
            min_hit_ratio=0.55,
        ),
        "governing_law_and_disputes": CoverageSpec(
            patterns=[r"\bприменим(ое|ым)\s+прав|\bприменимое\s+право\b", r"\bспор|\bразноглас", r"\bсуд\b|\bарбитраж\b", r"\bместо\b"],
            min_hit_ratio=0.55,
        ),
    }


def coverage_score(text: str, spec: CoverageSpec) -> Dict[str, Any]:
    t = text or ""
    hits = 0
    details = []
    for pat in spec.patterns:
        ok = re.search(pat, t, flags=re.IGNORECASE) is not None
        details.append({"pattern": pat, "hit": bool(ok)})
        if ok:
            hits += 1

    total = len(spec.patterns)
    ratio = hits / max(1, total)
    passed = ratio >= float(spec.min_hit_ratio)
    return {
        "patterns_total": total,
        "patterns_hit": hits,
        "hit_ratio": float(ratio),
        "min_hit_ratio": float(spec.min_hit_ratio),
        "passed": bool(passed),
        "details": details,
    }


# ============================================================
# 5) Числовая консистентность (простая эвристика)
# ============================================================

_NUM_TERM_RE = re.compile(
    r"\b(?P<num>\d{1,4})\s*(?P<unit>days?|day|дней|дня|months?|month|месяц(?:ев|а)?)\b",
    flags=re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b(?P<p>\d{1,3})\s*%\b")
_CCY_RE = re.compile(r"\b(USD|EUR|RUB|CNY|GBP)\b", flags=re.IGNORECASE)


def numeric_consistency(text: str) -> Dict[str, Any]:
    t = text or ""

    terms: Dict[str, set] = {"days": set(), "months": set()}
    for m in _NUM_TERM_RE.finditer(t):
        num = m.group("num")
        unit = (m.group("unit") or "").lower()
        if "day" in unit or "дн" in unit:
            terms["days"].add(num)
        if "month" in unit or "месяц" in unit:
            terms["months"].add(num)

    perc = {m.group("p") for m in _PERCENT_RE.finditer(t)}
    ccy = {m.group(1).upper() for m in _CCY_RE.finditer(t)}

    flags = []
    if len(terms["days"]) >= 4:
        flags.append("Many different 'days' values found (possible inconsistency).")
    if len(terms["months"]) >= 2:
        flags.append("Multiple different 'months' values found (possible inconsistency).")
    if len(perc) >= 4:
        flags.append("Many different percent values found (possible inconsistency).")

    return {
        "days_values": sorted(list(terms["days"]))[:12],
        "months_values": sorted(list(terms["months"]))[:12],
        "percent_values": sorted(list(perc))[:12],
        "currency_values": sorted(list(ccy))[:12],
        "flags": flags,
        "passed": (len(flags) == 0),
    }


# ============================================================
# 6) Оценка секции и контракта
# ============================================================

@dataclass
class SectionEval:
    section_id: str
    language_mode: str
    ok: bool
    metrics: Dict[str, Any]
    errors: List[str]


def evaluate_section(
    *,
    section_id: str,
    text: str,
    language_mode: str,
    generation_type: str,  # "form_llm" | "bm25_llm" | "rag_llm"
    embed: Optional[EmbedFn] = None,
    retrieved_context: Optional[List[str]] = None,
    min_chars_no_spaces: int = 700,
    forbid_crossrefs_en: bool = True,
    coverage_specs: Optional[Dict[str, CoverageSpec]] = None,
) -> SectionEval:
    t_raw = strip_control_chars(text or "")
    t = t_raw.strip()

    errors: List[str] = []
    metrics: Dict[str, Any] = {
        "generation_type": generation_type,
        "min_chars_no_spaces": int(min_chars_no_spaces),
        "len_no_spaces": text_no_spaces_len(t),
    }

    if metrics["len_no_spaces"] < int(min_chars_no_spaces):
        errors.append(f"Too short: len_no_spaces={metrics['len_no_spaces']} < {min_chars_no_spaces}")

    ok_lang, msg_lang = validate_language_purity(t, language_mode)
    metrics["language_ok"] = bool(ok_lang)
    metrics["language_msg"] = msg_lang
    if not ok_lang:
        errors.append(msg_lang)

    if (language_mode or "").lower() == "en" and forbid_crossrefs_en:
        ok_xr, msg_xr = validate_no_crossrefs(t)
        metrics["crossrefs_ok"] = bool(ok_xr)
        if not ok_xr:
            errors.append(msg_xr)
    else:
        metrics["crossrefs_ok"] = True

    ok_g, msg_g = validate_no_garbage(t)
    metrics["garbage_ok"] = bool(ok_g)
    if not ok_g:
        errors.append(msg_g)

    trunc, trunc_msg = looks_truncated(t)
    metrics["likely_truncated"] = bool(trunc)
    metrics["trunc_msg"] = trunc_msg
    if trunc:
        errors.append(trunc_msg)

    rep = repetition_score(t)
    metrics["repetition"] = rep
    if rep["sentence_count"] >= 8 and rep["sentence_unique_ratio"] < 0.75:
        errors.append(f"High repetition: sentence_unique_ratio={rep['sentence_unique_ratio']:.3f}")

    specs = coverage_specs or default_coverage_specs(language_mode)
    if section_id in specs:
        cov = coverage_score(t, specs[section_id])
        metrics["coverage"] = cov
        if not cov["passed"]:
            errors.append(f"Coverage failed: hit_ratio={cov['hit_ratio']:.3f} < min={cov['min_hit_ratio']:.3f}")
    else:
        metrics["coverage"] = {"enabled": False, "reason": "no_spec_for_section"}

    numc = numeric_consistency(t)
    metrics["numeric_consistency"] = numc
    if not numc["passed"]:
        errors.extend(numc["flags"])

    sim = similarity_to_context(
        text=t,
        context_chunks=retrieved_context or [],
        embed=embed,
    )
    metrics["similarity_to_context"] = sim
    if sim.get("enabled") and sim.get("sim_max") is not None:
        if float(sim["sim_max"]) < 0.20:
            errors.append(f"Low similarity_to_context: sim_max={sim['sim_max']:.3f} (possible hallucination)")

    ok = len(errors) == 0
    return SectionEval(section_id=section_id, language_mode=language_mode, ok=ok, metrics=metrics, errors=errors)


def evaluate_contract(
    *,
    sections: Dict[str, str],                       # section_id -> generated text
    language_mode: str,
    generation_type_by_section: Dict[str, str],     # section_id -> "form_llm" | "bm25_llm" | "rag_llm"
    embed: Optional[EmbedFn] = None,
    retrieved_context_by_section: Optional[Dict[str, List[str]]] = None,
    min_chars_no_spaces_default: int = 700,
    min_chars_override: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    retrieved_context_by_section = retrieved_context_by_section or {}
    min_chars_override = min_chars_override or {}

    per_section: List[Dict[str, Any]] = []
    ok_count = 0

    rep_ratios: List[float] = []
    cov_hit_ratios: List[float] = []
    sim_max_vals: List[float] = []

    for sid, txt in sections.items():
        gtype = generation_type_by_section.get(sid, "form_llm")
        min_chars = int(min_chars_override.get(sid, min_chars_no_spaces_default))

        ev = evaluate_section(
            section_id=sid,
            text=txt,
            language_mode=language_mode,
            generation_type=gtype,
            embed=embed,
            retrieved_context=retrieved_context_by_section.get(sid),
            min_chars_no_spaces=min_chars,
        )

        per_section.append({"section_id": ev.section_id, "ok": ev.ok, "errors": ev.errors, "metrics": ev.metrics})
        if ev.ok:
            ok_count += 1

        rep = ev.metrics.get("repetition", {})
        if isinstance(rep, dict) and rep.get("sentence_unique_ratio") is not None:
            rep_ratios.append(float(rep["sentence_unique_ratio"]))

        cov = ev.metrics.get("coverage", {})
        if isinstance(cov, dict) and cov.get("hit_ratio") is not None:
            cov_hit_ratios.append(float(cov["hit_ratio"]))

        sim = ev.metrics.get("similarity_to_context", {})
        if isinstance(sim, dict) and sim.get("enabled") and sim.get("sim_max") is not None:
            sim_max_vals.append(float(sim["sim_max"]))

    total = max(1, len(per_section))
    summary = {
        "sections_total": total,
        "sections_ok": ok_count,
        "pass_rate": ok_count / total,
        "avg_sentence_unique_ratio": (sum(rep_ratios) / len(rep_ratios)) if rep_ratios else None,
        "avg_coverage_hit_ratio": (sum(cov_hit_ratios) / len(cov_hit_ratios)) if cov_hit_ratios else None,
        "avg_similarity_max": (sum(sim_max_vals) / len(sim_max_vals)) if sim_max_vals else None,
    }
    return {"summary": summary, "per_section": per_section}


# ============================================================
# 7) Парсинг out.txt по "section_id-маркерам" (по заголовкам)
# ============================================================
# Твой формат заголовков:
# 1. ОПРЕДЕЛЕНИЯ
# 2. ПРЕДМЕТ ДОГОВОРА
# ...
# 10. ПРИМЕНИМОЕ ПРАВО И СПОРЫ
#
# Мы берём Title, нормализуем его и маппим в section_id.
# Если заголовок слегка меняется — добавляешь синоним ниже.
# ============================================================

HEADER_RE = re.compile(r"^\s*(?P<num>\d{1,2})\.\s*(?P<title>.+?)\s*$", flags=re.MULTILINE)


def _norm_title(title: str) -> str:
    t = (title or "").strip().lower()
    t = t.replace("ё", "е")
    t = re.sub(r"[^\w\s\-]", " ", t)  # убрать пунктуацию
    t = re.sub(r"\s+", " ", t).strip()
    return t


def title_to_section_id_map(language_mode: str) -> Dict[str, str]:
    """
    Маппинг нормализованного заголовка -> section_id.
    
    """
    lang = (language_mode or "ru").lower()

    if lang == "en":
        return {
            # 1
            "definitions": "definitions",
            # 2
            "subject of contract": "subject_of_contract",
            "subject": "subject_of_contract",
            # 3
            "price and taxes": "price_and_taxes",
            "price & taxes": "price_and_taxes",
            # 4
            "payment terms": "payment_terms",
            "terms of payment": "payment_terms",
            # 5
            "delivery terms": "delivery_terms",
            "terms of delivery": "delivery_terms",
            # 6
            "acceptance and inspection": "acceptance_and_inspection",
            "acceptance & inspection": "acceptance_and_inspection",
            # 7
            "warranties": "warranties",
            "warranty": "warranties",
            # 8
            "liability and penalties": "liability_and_penalties",
            "liability & penalties": "liability_and_penalties",
            "liability": "liability_and_penalties",
            # 9
            "force majeure": "force_majeure",
            # 10
            "governing law and disputes": "governing_law_and_disputes",
            "governing law & disputes": "governing_law_and_disputes",
            "governing law": "governing_law_and_disputes",
            "applicable law and disputes": "governing_law_and_disputes",
        }

    # RU
    return {
        # 1
        "определения": "definitions",
        "термины и определения": "definitions",
        # 2
        "предмет договора": "subject_of_contract",
        "предмет": "subject_of_contract",
        # 3
        "цена и налоги": "price_and_taxes",
        "цена и налогообложение": "price_and_taxes",
        "цена договора и налоги": "price_and_taxes",
        # 4
        "условия оплаты": "payment_terms",
        "порядок расчетов": "payment_terms",
        "порядок расчётов": "payment_terms",
        # 5
        "условия поставки": "delivery_terms",
        "поставка": "delivery_terms",
        "доставка": "delivery_terms",
        # 6
        "приемка и инспекция": "acceptance_and_inspection",
        "приемка и проверка": "acceptance_and_inspection",
        "приемка": "acceptance_and_inspection",
        # 7
        "гарантии": "warranties",
        "гарантийные обязательства": "warranties",
        # 8
        "ответственность и штрафы": "liability_and_penalties",
        "ответственность": "liability_and_penalties",
        "штрафы и ответственность": "liability_and_penalties",
        # 9
        "форс мажор": "force_majeure",
        "форс-мажор": "force_majeure",
        "обстоятельства непреодолимой силы": "force_majeure",
        # 10
        "применимое право и споры": "governing_law_and_disputes",
        "применимое право": "governing_law_and_disputes",
        "право и споры": "governing_law_and_disputes",
        "споры": "governing_law_and_disputes",
    }


def extract_sections_from_contract_text(
    contract_text: str,
    *,
    language_mode: str,
) -> Dict[str, str]:
    """
    Парсер по заголовкам вида "N. TITLE".
    TITLE маппится в section_id через title_to_section_id_map().

    Возвращает: section_id -> текст секции (включая заголовок строки).
    """
    t = strip_control_chars(contract_text or "")
    if not t.strip():
        return {}

    title_map = title_to_section_id_map(language_mode)

    # найдём все заголовки
    headers: List[Tuple[int, str, int, int]] = []  # (num, title, start, end_of_line)
    for m in HEADER_RE.finditer(t):
        num = int(m.group("num"))
        title = (m.group("title") or "").strip()
        start = m.start()
        end_line = m.end()
        headers.append((num, title, start, end_line))

    if not headers:
        return {}

    headers.sort(key=lambda x: x[2])

    out: Dict[str, str] = {}
    for i, (num, title, start, _end_line) in enumerate(headers):
        end = headers[i + 1][2] if i + 1 < len(headers) else len(t)
        block = t[start:end].strip()

        sid = title_map.get(_norm_title(title))
        if not sid:
            # неузнанный заголовок — пропускаем
            continue

        # если одна и та же секция встретилась дважды (редко, но бывает), склеим
        if sid in out:
            out[sid] = (out[sid].rstrip() + "\n\n" + block).strip()
        else:
            out[sid] = block

    return out
