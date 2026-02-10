# run_generate.py
from __future__ import annotations

from pathlib import Path
import json
import sys
import importlib
import re
import os
import numpy as np
import pymorphy3
from typing import Callable, Optional

from src.validation.form_validate import validate_form

from src.validation.payment_terms_validator import payment_terms_validator
from src.validation.delivery_terms_validator import delivery_terms_validator

from src.generation.definitions_generate import build_definitions_prompt
from src.generation.subject_generate import build_subject_prompt
from src.generation.price_generate import build_price_prompt
from src.generation.acceptance_generate import build_acceptance_prompt
from src.generation.warranties_generate import build_warranties_prompt
from src.generation.liability_generate import build_liability_prompt
from src.generation.force_majeure_generate import build_force_majeure_prompt
from src.generation.governing_law_generate import build_governing_law_prompt
from src.prompts.topic_checklists import get_section_checklist
from txt_to_docx import txt_to_docx
from src.retrieval.dense_index import DenseIndex, DenseRetriever

from src.retrieval.bm25 import (
    load_corpus_sections_jsonl,
    retrieve_payment_terms_bm25,
    retrieve_delivery_terms_bm25,
)

from src.retrieval.retrieval_llama import LlamaEmbedder


from src.cleaning.precedent_cleaner import (
    clean_precedents_payment_terms,
    clean_precedents_delivery_terms,
)

from src.validation.consistency_validator import (
    compose_validators,
    make_payment_consistency_validator,
    make_delivery_consistency_validator,
)

from src.generation.payment_terms_generate import build_payment_terms_prompt
from src.generation.delivery_terms_generate import build_delivery_terms_prompt

from src.planning.contract_planner import build_contract_plan
from src.coverage.coverage_controller import precheck_missing_sections, postcheck_coverage

from src.state.contract_state import ContractState, bootstrap_state_from_form
from src.state.state_updater import update_state_from_section
from src.prompts.consistency_context import build_consistency_context



START_FROM_SECTION = int(os.getenv("START_FROM_SECTION", "0"))

SKIP_RETRIEVAL_SECTIONS = False
RETRIEVAL_SECTION_IDS = {"payment_terms", "delivery_terms"}

SOFT_FAIL_SECTIONS = True

FORM_SECTION_MIN_CHARS = {
    "definitions": 900,
    "subject_of_contract": 900,
    "price_and_taxes": 1000,
    "acceptance_and_inspection": 900,
    "warranties": 1000,
    "liability_and_penalties": 1200,
    "force_majeure": 1000,
    "governing_law_and_disputes": 900,
}


FORM_TARGET_SUBCLAUSES = {
    "definitions": 10,
    "subject_of_contract": 12,
    "price_and_taxes": 16,
    "acceptance_and_inspection": 14,
    "warranties": 16,
    "liability_and_penalties": 14,
    "force_majeure": 16,
    "governing_law_and_disputes": 14,
}

DENSE_INDEX_NPY = Path("debug/emb_index_bge_m3/bge_m3_doc_embs.npy")
DENSE_INDEX_META = Path("debug/emb_index_bge_m3/bge_m3_docs_meta.jsonl")

AVG_CHARS_PER_LINE = 95

MIN_SECTION_FLOOR = 900

FORM_SECTION_MIN_CHARS = {
    sid: max(MIN_SECTION_FLOOR, FORM_TARGET_SUBCLAUSES[sid] * AVG_CHARS_PER_LINE)
    for sid in FORM_TARGET_SUBCLAUSES
}

RU_SECTION_TITLES = {
    "definitions": "ОПРЕДЕЛЕНИЯ",
    "subject_of_contract": "ПРЕДМЕТ ДОГОВОРА",
    "price_and_taxes": "ЦЕНА И НАЛОГИ",
    "payment_terms": "УСЛОВИЯ ОПЛАТЫ",
    "delivery_terms": "УСЛОВИЯ ПОСТАВКИ",
    "acceptance_and_inspection": "ПРИЕМКА И ИНСПЕКЦИЯ",
    "warranties": "ГАРАНТИИ",
    "liability_and_penalties": "ОТВЕТСТВЕННОСТЬ И ШТРАФЫ",
    "force_majeure": "ФОРС-МАЖОР",
    "governing_law_and_disputes": "ПРИМЕНИМОЕ ПРАВО И СПОРЫ",
}

EN_SECTION_TITLES = {
    "definitions": "DEFINITIONS",
    "subject_of_contract": "SUBJECT OF CONTRACT",
    "price_and_taxes": "PRICE AND TAXES",
    "payment_terms": "PAYMENT TERMS",
    "delivery_terms": "DELIVERY TERMS",
    "acceptance_and_inspection": "ACCEPTANCE AND INSPECTION",
    "warranties": "WARRANTIES",
    "liability_and_penalties": "LIABILITY AND PENALTIES",
    "force_majeure": "FORCE MAJEURE",
    "governing_law_and_disputes": "GOVERNING LAW AND DISPUTES",
}

FORM_BASED_BUILDERS = {
    "definitions": build_definitions_prompt,
    "subject_of_contract": build_subject_prompt,
    "price_and_taxes": build_price_prompt,
    "acceptance_and_inspection": build_acceptance_prompt,
    "warranties": build_warranties_prompt,
    "liability_and_penalties": build_liability_prompt,
    "force_majeure": build_force_majeure_prompt,
    "governing_law_and_disputes": build_governing_law_prompt,
}


# GENERATION POLICY SPLIT

FORM_ONLY_SECTION_IDS = {
    "definitions",
    "subject_of_contract",
    "price_and_taxes",
}

# CONFIG: embeddings retrieval for sections 6-10

EMBEDDINGS_SECTION_IDS = {
    "acceptance_and_inspection",
    "warranties",
    "liability_and_penalties",
    "force_majeure",
    "governing_law_and_disputes",
}

# retrieval params 
EMB_TOP_K = 5

EMB_TOP_K_BY_SECTION = {
    "acceptance_and_inspection": 20,  
}

EMB_MAX_DOCS = 800          
EMB_CHUNK_TOKENS = 256
EMB_OVERLAP_TOKENS = 64


MAX_PRECEDENT_CHARS = 900        
MAX_PRECEDENTS_TOTAL_CHARS = 3000  

# RU post-processing helpers

ENUM_TO_RU = {
    "contract_price": "цена договора",
    "aggregate": "совокупный",
    "fraud": "мошенничество",
    "wilful_misconduct": "умышленное нарушение",
    "exclusive_if_any": "исключительный режим налогообложения",
    "lump_sum": "фиксированной суммой",
    "per_unit": "за единицу",
    "per_lot": "за партию",
}

def trim_precedents(top_rows):
    out = []
    total = 0
    for r in top_rows:
        t = (r.get("text") or "").strip()
        if not t:
            continue
        t = t[:MAX_PRECEDENT_CHARS]
        if total + len(t) > MAX_PRECEDENTS_TOTAL_CHARS:
            break
        out.append({**r, "text": t})
        total += len(t)
    return out

def replace_enum_to_ru(text: str) -> str:
    for k, v in ENUM_TO_RU.items():
        text = text.replace(k, v)
    return text

def normalize_currency_ru(text: str) -> str:
    return text.replace("RUB", "руб.")

def strip_subheadings_article_10(text: str) -> str:
    
    if not text.lstrip().startswith("10."):
        return text

    lines = text.splitlines()
    out = []
    for line in lines:
        line = re.sub(
            r"^(10\.\d+)\.\s+[А-ЯЁа-яё\s]+?\.\s*",
            r"\1. ",
            line,
        )
        out.append(line)
    return "\n".join(out)

def postprocess_ru_section(text: str, section_id: str) -> str:
    text = replace_enum_to_ru(text)
    text = normalize_currency_ru(text)
    text = re.sub(r"(руб)\.\.+", r"\1.", text)            # руб.. -> руб.
    text = re.sub(r"\.\.+", ".", text)                   # .. -> .
    text = re.sub(r"\s+\.", ".", text)                   # " ." -> "."
    text = re.sub(r"\(\s*руб\.\s*\)\.", "(руб.)", text)  # (руб.). -> (руб.)

    if section_id == "governing_law_and_disputes":
        text = strip_subheadings_article_10(text)

    if section_id == "force_majeure":
        # Удаляем строки вида "9.2. Уведомление" без текста
        text = re.sub(r"(?m)^\s*9\.\d+\.\s*(Уведомление|Notice)\s*$\n?", "", text)

    return text.strip()

def build_embed_query(form_input: dict, section_id: str, base_prompt: str) -> str:
    lang = str(form_input.get("language_mode", "ru")).strip().lower()
    return f"SECTION={section_id}\nLANG={lang}\n\n" + (base_prompt or "")

def format_precedents_for_prompt(rows: list[dict], *, lang: str) -> str:
    if not rows:
        return ""
    title = (
        "RELEVANT PRECEDENTS (use for style/structure; do not copy verbatim):"
        if lang == "en"
        else "РЕЛЕВАНТНЫЕ ПРЕЦЕДЕНТЫ (ориентир по стилю/структуре; не копируй дословно):"
    )
    parts = []
    for i, r in enumerate(rows, start=1):
        txt = (r.get("text") or "").strip()
        if txt:
            parts.append(f"[{i}] {txt}")
    return title + "\n" + "\n\n".join(parts) + "\n"

def _norm(s: str) -> str:
    return (s or "").strip()

def _norm_l(s: str) -> str:
    return (s or "").strip().lower()

def _make_doc_key(r: dict) -> tuple:
    """
    Универсальный ключ для сопоставления docs_meta <-> corpus_rows.
    Приоритет: (source/contract_id, section_id, language) затем (section_id, language, title).
    """
    sid = _norm(r.get("section_id"))
    lang = _norm_l(r.get("language"))
    title = _norm(r.get("title"))

    contract_id = _norm(r.get("contract_id"))
    source_file = _norm(r.get("source_file") or r.get("source_path") or r.get("source") or "")
    src = contract_id or source_file

    if src:
        return ("src", src, sid, lang)

    return ("ttl", sid, lang, title)

def _build_text_lookup(corpus_rows: list[dict]) -> dict[tuple, list[str]]:
    """
    Строит lookup: key -> [text1, text2, ...]
    чтобы корректно обрабатывать дубликаты ключей.
    """
    mp: dict[tuple, list[str]] = {}
    for r in corpus_rows:
        sid = _norm(r.get("section_id"))
        if not sid:
            continue
        key = _make_doc_key(r)
        txt = (r.get("text") or "").strip()
        if not txt:
            continue
        mp.setdefault(key, []).append(txt)
    return mp


def shingle_loop_bad(
    text: str,
    *,
    k_words: int = 5,
    max_occ: int = 2,
    max_overused: int = 2,
    lang: str = "ru",
) -> Optional[str]:
    """
    Детект "зацикливания" по повторяющимся шинглам (k-словным фрагментам).   
    """
    t = (text or "").strip()
    if not t:
        return None
    
    words = re.findall(r"[A-Za-zА-Яа-яЁё]+", t.lower())
    if len(words) < k_words * 6:  # слишком коротко, статистика бессмысленна
        return None

    counts: dict[str, int] = {}
    for i in range(0, len(words) - k_words + 1):
        sh = " ".join(words[i:i + k_words])
        counts[sh] = counts.get(sh, 0) + 1

    overused = [(sh, c) for sh, c in counts.items() if c > max_occ]
    if len(overused) > max_overused:
       
        overused.sort(key=lambda x: x[1], reverse=True)
        top_sh, top_c = overused[0]
        return f"shingle_loop(k={k_words}, overused={len(overused)}, top='{top_sh}' x{top_c})"

    return None

def apply_antiloop_shingles(
    text: str,
    *,
    debug_dir: Path,
    section_id: str,
    section_no: int,
    lang: str,
    k_words: int = 5,
    max_occ: int = 2,
    max_overused: int = 2,
    repair_sem_threshold: float = 0.92,
) -> str:
    """
    Универсальный anti-loop: проверяет шингловые повторы 
    """

    loop_err = shingle_loop_bad(
        text,
        k_words=k_words,
        max_occ=max_occ,
        max_overused=max_overused,
        lang=lang,
    )

    if not loop_err:
        return text

    (debug_dir / f"{section_id}_shingle_loop.txt").write_text(loop_err, encoding="utf-8")

    repaired = semantic_deduplicate(text, threshold=repair_sem_threshold)
    repaired = drop_exact_duplicate_lines(repaired)
    repaired = ensure_numbered_lines(repaired, section_no=section_no)
    return repaired

def semantic_deduplicate_embeddings(
    text: str,
    *,
    embedder,
    threshold: float = 0.85,
) -> str:    

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) <= 1:
        return text

    # --- embeddings одной пачкой (ВАЖНО быстрее чем по одной)
    embs = embedder.embed_many(lines)
    embs = np.array(embs, dtype=np.float32)

    # L2 normalization
    embs /= np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9

    keep_lines = []
    keep_embs = []

    for line, emb in zip(lines, embs):
        is_duplicate = False

        for prev_emb in keep_embs:
            if np.dot(emb, prev_emb) > threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            keep_lines.append(line)
            keep_embs.append(emb)

    return "\n".join(keep_lines)


# LLM factory

def make_llm(*, root: Path):
    from src.generation.local_llm import LocalLLM, LLMConfig
    import src.config as cfg

    model_path = Path(cfg.LOCAL_GGUF_MODEL_PATH or cfg.LOCAL_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = root / model_path
    if not model_path.exists():
        raise FileNotFoundError(f"GGUF model not found: {model_path}")

    return LocalLLM(LLMConfig(
        model_path=model_path,

        # context
        n_ctx=cfg.N_CTX,
        n_threads=cfg.N_THREADS,
        n_gpu_layers=cfg.N_GPU_LAYERS,

        # sampling
        temperature=cfg.TEMPERATURE,
        top_p=cfg.TOP_P,
        top_k=cfg.TOP_K,
        typical_p=cfg.TYPICAL_P,

        # penalties
        repeat_penalty=cfg.REPEAT_PENALTY,
        presence_penalty=cfg.PRESENCE_PENALTY,
        frequency_penalty=cfg.FREQUENCY_PENALTY,

        # output
        max_tokens=cfg.MAX_TOKENS,

        # retry
        max_retries=cfg.MAX_RETRIES,
        retry_temperature=cfg.RETRY_TEMPERATURE,
        retry_top_p=cfg.RETRY_TOP_P,
        retry_top_k=cfg.RETRY_TOP_K,
        retry_typical_p=cfg.RETRY_TYPICAL_P,

        retry_repeat_penalty=cfg.RETRY_REPEAT_PENALTY,
        retry_presence_penalty=cfg.RETRY_PRESENCE_PENALTY,
        retry_frequency_penalty=cfg.RETRY_FREQUENCY_PENALTY,
    ))


# Language helpers + titles

def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()

def section_title(form_input: dict, section_id: str) -> str:
    if _lang(form_input) == "ru":
        return RU_SECTION_TITLES.get(section_id, section_id.upper())
    return EN_SECTION_TITLES.get(section_id, section_id.upper())

_morph = pymorphy3.MorphAnalyzer()

def ru_genitive(text: str) -> str:
    
    words = []

    for w in text.split():
        p = _morph.parse(w)[0]
        inflected = p.inflect({"gent"})  # genitive
        words.append(inflected.word if inflected else w)

    return " ".join(words)

def contract_title(form_input: dict) -> str:
    lang = _lang(form_input)

    goods = (form_input.get("goods", {}).get("goods_description") or "").strip()

    if lang == "en":
        return f"CONTRACT FOR DELIVERY OF {(goods or 'goods').upper()}"

    subject = ru_genitive(goods) if goods else "ТОВАРА"
    return f"ДОГОВОР НА ПОСТАВКУ {subject.upper()}"

# ----------------------------
# Retry instructions
# ----------------------------
def retry_form_based(*, section_no: int, lang: str, target_subclauses: int) -> str:
    if lang == "en":
        return (
            "The previous draft is too short or poorly formatted.\n"
            f"Rewrite the section and output {target_subclauses}–{target_subclauses + 4} subclauses numbered "
            f"{section_no}.1., {section_no}.2., ...\n"
            "- One sentence per line.\n"
            "- No headings, no blank lines, no markdown.\n"
            "- Add NEW aspects; do NOT repeat the same idea.\n"
            "- If you are running out of ideas, split procedures into smaller steps while staying in this section.\n"
            "- do NOT repeat the same idea or thesis twice.\n"
        )
    return (
        "Предыдущий вариант слишком короткий или плохо оформлен.\n"
        f"Перепиши раздел и выведи {target_subclauses}–{target_subclauses + 4} подпунктов формата "
        f"{section_no}.1., {section_no}.2., ...\n"
        "- Одно предложение на строке.\n"
        "- Без заголовков, без пустых строк, без markdown.\n"
        "- Добавляй НОВЫЕ аспекты; не повторяй одну и ту же мысль.\n"
        "- Если не хватает идей — дроби процедуры на более мелкие шаги, не выходя за рамки секции.\n"
        "- Не повторяй одну и ту же мысль или тезис дважды.\n"
    )

def retry_delivery(*, section_no: int, lang: str) -> str:
    if lang == "en":
        return (
            f"Rewrite the section.\n"
            f"Output at least 25 subclauses numbered {section_no}.1., {section_no}.2., ...\n"
            "- Exactly one or two complete legal sentences per line.\n"
            "- No blank lines.\n"
            "- Each clause must contain sufficient legal detail (not shorter than 15–20 words).\n"
            "- Do NOT repeat the same idea or wording.\n"
            "- Do NOT start 4 or more clauses with the same first 3 words.\n"
            "- Vary sentence openings and grammatical structure.\n"
            "- Alternate subjects and phrasing such as:\n"
            "  'The Supplier...', 'The Buyer...', 'Delivery...', 'Shipment...', "
            "'Risk of loss...', 'Title...', 'Packaging...', 'Inspection...', "
            "'Incoterms...', 'Partial deliveries...', 'Early delivery...', 'Transportation...', 'Documents...'\n"
            "- Replace repetitive delivery wording with NEW procedural or logistical aspects.\n"
        )

    return (
        f"Перепиши раздел.\n"
        f"Выведи не менее 25 подпунктов формата {section_no}.1., {section_no}.2., ...\n"
        "- Одно предложение на строке.\n"
        "- Без пустых строк.\n"
        "- Убери повторы, заменяя их новыми темами по поставке.\n"
        "- Каждые 3–4 подпункта начинай с другой конструкции.\n"
        "- Не начинай 4 и более подпункта одинаковыми первыми словами.\n"
    )

def embeddings_guard_instruction(*, section_id: str, lang: str) -> str:
    if lang == "en":
        return (
            "STRICT QUALITY RULES:\n"
            "- Do NOT use tautological phrases like ""applicable law is the applicable law"".\n"
            "- If data missing → write neutral but meaningful legal wording.\n"
            "- Do NOT repeat the same clause idea twice; each line must be a new topic.\n"
            "- Do NOT duplicate the same pre-claim procedure wording.\n"
            "- Do NOT invent a court/arbitration seat or governing law. Use ONLY what is stated in the form/context.\n"
            "- If the form/context does NOT specify governing law or forum, use a neutral placeholder-free wording "
            "('in accordance with applicable law', 'competent court/arbitration agreed by the Parties') WITHOUT naming a city/country.\n"
            "- Avoid circular restatements.\n"
        )
    return (
        "СТРОГИЕ ПРАВИЛА КАЧЕСТВА:\n"
        "- Не используй тавтологию.\n"
        "- Пиши длинные развернутые предложения.\n"
        "- НЕ повторяй одну и ту же идею/формулировку дважды: каждый подпункт = новая тема.\n"
        "- НЕ дублируй претензионный порядок (опиши один раз, далее не повторяй).\n"
        "- НЕ выдумывай юрисдикцию/город/суд/место арбитража и применимое право — используй ТОЛЬКО то, что задано в форме/контексте.\n"
        "- Если применимое право или орган разрешения споров НЕ заданы в форме/контексте — пиши нейтрально "
        "(«в соответствии с применимым правом», «компетентный суд/арбитраж по соглашению Сторон») БЕЗ указания страны/города.\n"
        "- Избегай круговых повторов.\n"
    )

# ----------------------------
# Numbering instruction for form-based
# ----------------------------
def form_based_numbering_instruction(*, section_no: int, lang: str, target_subclauses: int) -> str:
    if lang == "en":
        return (
            "OUTPUT FORMAT STRICT:\n"
            "- Section title is NOT needed.\n"
            f"- Output ONLY numbered subclauses: {section_no}.1., {section_no}.2., ... each on a new line.\n"
            f"- Produce {target_subclauses} to {target_subclauses + 4} subclauses (do NOT output fewer).\n"
            "- Each subclause must be exactly ONE complete legal sentence.\n"
            "- No headings, no blank lines, no bullets, no markdown.\n"
            "- Do NOT output TBD/None or empty lines like “9.2. Notice”.\n"
            "- Do NOT repeat the same idea; each subclause must introduce a NEW topic.\n"
            "- Start subclauses in different ways. Use different grammatical constructions (e.g., 'The parties agreed…', 'Cost amounts to…', 'Penalty is applied...').\n"
            "- Do NOT use the same beginning frase more than twice in one section.\n"
        )
    return (
        "СТРОГИЙ ФОРМАТ ВЫВОДА:\n"
        "- Заголовок секции НЕ нужен.\n"
        f"- Выведи ТОЛЬКО подпункты: {section_no}.1., {section_no}.2., ... каждый с новой строки.\n"
        f"- Сделай {target_subclauses}–{target_subclauses + 4} подпунктов (НЕЛЬЗЯ меньше).\n"
        "- Каждый подпункт — РОВНО одно законченное юридическое предложение.\n"
        "- Без подзаголовков, без пустых строк, без маркеров, без markdown.\n"
        "- Запрещены строки вида «9.2. Уведомление» без пояснения.\n"
        "- Не повторяй одну и ту же мысль; каждый подпункт = новая тема.\n"
        "- Начинай разные пункты по-разному: используй разные грамматические конструкции.\n"
        "- Не используй одну и ту же стартовую фразу более 2 раз во всём разделе.\n"
    )


# ----------------------------
# System prompts
# ----------------------------
def _system_generic(form_input: dict) -> str:
    if _lang(form_input) == "en":
        return (
            "You are a careful legal drafting assistant. "
            "Strictly follow the input form constraints. "
            "Write in a formal legal style. "
            "Do not invent facts. "
            "Do not output markdown. "
            "Avoid placeholders like TBD/None."
        )
    return (
        "Ты — аккуратный юридический ассистент. "
        "Строго следуй ограничениям из формы. "
        "Пиши юридическим деловым стилем. "
        "Не выдумывай факты. "
        "Не используй markdown. "
        "Не выводи маркеры типа TBD/None."
    )

def _system_payment(form_input: dict) -> str:
    if _lang(form_input) == "en":
        return (
            "You are a careful legal drafting assistant. "
            "Strictly follow user constraints. "
            "Write in a formal legal style. "
            "Do not invent facts."
        )
    return (
        "Ты — аккуратный юридический ассистент. "
        "Строго следуй ограничениям из формы. "
        "Пиши юридическим деловым стилем. "
        "Не выдумывай факты."
    )

def _system_delivery(form_input: dict) -> str:
    if _lang(form_input) == "en":
        return (
            "You are a careful legal drafting assistant. "
            "Strictly follow user constraints. "
            "Write in a formal legal style. "
            "Do not invent facts."
        )
    return (
        "Ты — аккуратный юридический ассистент. "
        "Строго следуй ограничениям из формы. "
        "Пиши юридическим деловым стилем. "
        "Не выдумывай факты."
    )


# ----------------------------
# Output cleanup (remove markers / mixed language)
# ----------------------------
_re_md = re.compile(r"^\s*(#+|\*|\-|\>|\`{3,}).*$", re.MULTILINE)
_re_tbd = re.compile(r"\b(TBD|None|null|N/A)\b", re.IGNORECASE)

def sanitize_text(text: str, *, lang: str) -> str:
    text = _re_md.sub("", text or "")
    text = _re_tbd.sub("", text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = re.sub(r"[\u3000-\u9fff]+", "", text)
    text = re.sub(r"[，。；：]+", "", text)

    if lang == "ru":
        
        text = re.sub(r"[\u4e00-\u9fff]+", "", text)

    return text.strip()

def drop_exact_duplicate_lines(text: str) -> str:
    seen = set()
    out = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        key = re.sub(r"\s+", " ", s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return "\n".join(out)


# ----------------------------
# Numbering helpers
# ----------------------------
def ensure_numbered_lines(text: str, *, section_no: int) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]

    cleaned = []
    for ln in lines:
       
        ln = re.sub(r"^\s*(?:\(\d+\)|\d+(?:[.)]?\d*)*[.)]?)\s*", "", ln)
        cleaned.append(ln.strip())

    cleaned = [ln for ln in cleaned if ln]

    out = []
    for i, ln in enumerate(cleaned, start=1):
        out.append(f"{section_no}.{i}. {ln}")
    return "\n".join(out).strip()

def semantic_deduplicate(text: str, threshold: float = 0.85) -> str:
    import difflib

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    result = []

    for ln in lines:
        if not any(
            difflib.SequenceMatcher(None, ln, r).ratio() > threshold
            for r in result
        ):
            result.append(ln)

    return "\n".join(result)

def make_section_block(*, section_no: int, title: str, body_numbered: str) -> str:
    header = f"{section_no}. {title}"
    return header + "\n" + body_numbered.strip()


# ----------------------------
# Simple validator for form-based sections
# ----------------------------
def _count_chars_no_spaces(s: str) -> int:
    return len(re.sub(r"\s+", "", s or ""))

def form_section_validator(
    *,
    section_no: int,
    min_chars_no_spaces: int,
    min_items: Optional[int] = None,
) -> Callable[[str], Optional[str]]:
    def _v(text: str) -> Optional[str]:
        if _count_chars_no_spaces(text) < min_chars_no_spaces:
            return "too_short"

        if min_items is not None:
            items = re.findall(rf"^\s*{section_no}\.\d+\.\s+", text, flags=re.MULTILINE)
            if len(items) < min_items:
                return f"too_few_items({len(items)}<{min_items})"
        return None
    return _v

# ----------------------------
# Validator wrapper: validate AFTER formatting
# ----------------------------
def wrap_validator_after_format(
    *,
    validator: Callable[[str], Optional[str]],
    section_no: int,
    lang: str,
    debug_cnt_path: Optional[Path] = None,
) -> Callable[[str], Optional[str]]:

    def _v(text: str) -> Optional[str]:
        t = sanitize_text(text or "", lang=lang)
        t = drop_exact_duplicate_lines(t)
        t = ensure_numbered_lines(t, section_no=section_no)

        # --- anti-repetition: 3-word prefix more than 2 times ---
        prefixes = {}
        for ln in t.splitlines():
            m = re.match(rf"^\s*{section_no}\.\d+\.\s+(.*)$", ln)
            if not m:
                continue
            body = m.group(1).strip()
            words = re.findall(r"[А-Яа-яЁёA-Za-z]+", body.lower())

            # 1) убираем вводные/служебные старты, которые часто повторяются в юр. стиле
            STOP_START = {"если", "при", "в", "условии", "в", "случае", "когда", "в", "том", "числе", "the", "is", "if", "in"}
            # аккуратно: "в случае" = два слова, поэтому удаляем по одному
            while words and words[0] in STOP_START:
                words = words[1:]

            if len(words) < 3:
                continue

            pref = " ".join(words[:3])
            prefixes[pref] = prefixes.get(pref, 0) + 1
            if prefixes[pref] >= 4:
                return f"repetition_prefix({pref})"

        
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

        starts = []
        for ln in lines:
            # после ensure_numbered_lines формат всегда: "{section_no}.{i}. <текст>"
            after_num = ln.split(" ", 1)[1] if " " in ln else ln
            first_words = " ".join(after_num.split()[:3]).lower()
            if first_words:
                starts.append(first_words)

        if starts:
            most_common = max(starts.count(s) for s in set(starts))
            if most_common >= 4:
                return "loop_like_repeated_starts"

        if debug_cnt_path is not None:
            cnt = len(re.findall(rf"(?m)^\s*{section_no}\.\d+\.\s+", t))
            debug_cnt_path.write_text(str(cnt), encoding="utf-8")

        return validator(t)

    return _v


# ----------------------------
# Main generation pipeline
# ----------------------------
def generate_contract(form_input: dict) -> str:
    root = Path(__file__).parent
    debug_dir = root / "debug"
    debug_dir.mkdir(exist_ok=True)

    # plan
    plan = build_contract_plan(form_input)
    (debug_dir / "contract_plan.json").write_text(
        json.dumps(
            {
                "contract_type": plan.contract_type,
                "language_mode": plan.language_mode,
                "ordered_sections": plan.ordered_section_ids(),
                "generation_policy": plan.generation_policy,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    llm = make_llm(root=root)
    print("DEBUG: llm max_retries =", getattr(llm.cfg, "max_retries", None))
    print("DEBUG: retry_temperature =", getattr(llm.cfg, "retry_temperature", None))
    print("DEBUG: retry_top_p =", getattr(llm.cfg, "retry_top_p", None))

    # state
    state_path = debug_dir / "contract_state.json"
    if state_path.exists():
        state = ContractState.load(state_path)
    else:
        state = ContractState.empty(
            contract_type=form_input.get("contract_type", "supply"),
            language_mode=form_input.get("language_mode", "ru"),
        )

    state = bootstrap_state_from_form(form_input, state=state)
    lang = str(form_input.get("language_mode", "ru")).strip().lower()
    state.data.setdefault("meta", {})["language_mode"] = lang
    state.save(state_path)

    # warnings sink (soft consistency)
    cons_warnings_path = debug_dir / "consistency_warnings.log"

    def _warn(msg: str) -> None:
        with cons_warnings_path.open("a", encoding="utf-8") as f:
            f.write(msg.strip() + "\n")

    def _warn_to_state(msg: str) -> None:
        _warn(msg)
        state.data.setdefault("consistency", {}).setdefault("warnings", []).append(msg.strip())

    # coverage precheck
    generated_ids: set[str] = set()
    pre = precheck_missing_sections(plan, already_generated=generated_ids, form=form_input)
    to_generate = set(pre.to_generate)

    (debug_dir / "coverage_precheck_notes.txt").write_text(
        "\n".join(pre.notes) if getattr(pre, "notes", None) else "",
        encoding="utf-8",
    )

    ordered_ids = plan.ordered_section_ids()

    # retrieval corpus load only if used
    corpus_rows = None
    corpus_path = root / "data" / "corpus_sections.jsonl"
    if (not SKIP_RETRIEVAL_SECTIONS) and any(sid in to_generate for sid in RETRIEVAL_SECTION_IDS):
        if not corpus_path.exists():
            raise FileNotFoundError(f"Corpus file not found: {corpus_path}")
        corpus_rows = load_corpus_sections_jsonl(corpus_path)

    sections_out: list[str] = []
    lang = _lang(form_input)

    # ------------------------------------------------------------
# embeddings: runtime cache (embedder + dense index)
# ------------------------------------------------------------
    emb_cache: dict = {}

    need_embeddings = any((sid in to_generate) for sid in EMBEDDINGS_SECTION_IDS)
    if need_embeddings:
        import src.config as cfg

        # 1) embedder нужен только для query embedding (быстро)
        embed_model_path = Path(cfg.LOCAL_GGUF_EMBED_MODEL_PATH)
        if not embed_model_path.is_absolute():
            embed_model_path = root / embed_model_path
        if not embed_model_path.exists():
            raise FileNotFoundError(f"Embedding GGUF model not found: {embed_model_path}")

        emb_cache["embedder"] = LlamaEmbedder(
            model_path=str(embed_model_path),
            n_ctx=8192,
            n_threads=int(cfg.N_THREADS),
            n_gpu_layers=0,
            verbose=False,
        )

        # 2) dense index: загружаем готовые эмбеддинги (НЕ пересчитываем!)
        if not DENSE_INDEX_NPY.exists() or not DENSE_INDEX_META.exists():
            raise FileNotFoundError(
                f"Precomputed dense index not found:\n"
                f"- {DENSE_INDEX_NPY}\n- {DENSE_INDEX_META}\n"
                f"Run: python src/retrieval/emb_index_bge_m3.py ..."
            )

        print(f"DEBUG: loading dense embeddings index: {DENSE_INDEX_NPY}")
        dense_index = DenseIndex.load(DENSE_INDEX_NPY, DENSE_INDEX_META, normalize=True)
        dense_retriever = DenseRetriever(dense_index)

        emb_cache["dense_index"] = dense_index
        emb_cache["dense_retriever"] = dense_retriever

        # 3) нужен доступ к текстам прецедентов => готовим lookup по corpus_rows
       
        emb_cache["text_lookup_ready"] = False

    def _soft_fail_use_last_attempt(
        *,
        section_id: str,
        section_no: int,
        title: str,
        err: str,
        last_text: str,
    ) -> None:
        
        (debug_dir / f"{section_id}_soft_fail.txt").write_text(
            f"SECTION: {section_id}\nERROR: {err}\n\nLAST_TEXT:\n{last_text}\n",
            encoding="utf-8",
        )
        
        body = sanitize_text(last_text or "", lang=lang)
        body = drop_exact_duplicate_lines(body)
        body = ensure_numbered_lines(body, section_no=section_no)
        
        sections_out.append(make_section_block(section_no=section_no, title=title, body_numbered=body))
        generated_ids.add(section_id)

    # сквозная нумерация по порядку plan
    section_no_map = {sid: i + 1 for i, sid in enumerate(ordered_ids)}

    for section_id in ordered_ids:
        need_generate = section_id in to_generate
        section_no = section_no_map[section_id]
        title = section_title(form_input, section_id)

        # >>> PATCH: fast debug - start from section N
        if START_FROM_SECTION and section_no < START_FROM_SECTION:
            print(f"DEBUG: skip section {section_no} ({section_id}) due to START_FROM_SECTION={START_FROM_SECTION}")
            continue

        title = section_title(form_input, section_id)

        # =========================================================
        # PAYMENT TERMS (retrieval)
        # =========================================================
        if section_id == "payment_terms" and need_generate and not SKIP_RETRIEVAL_SECTIONS:
            print("DEBUG: BM25 retrieval for payment_terms...")

            precedents_raw = retrieve_payment_terms_bm25(form_input, corpus_rows, top_k=5, max_docs=800)
            precedents_clean, rep = clean_precedents_payment_terms(precedents_raw, min_chars=120, max_chars=1800)

            base_prompt = build_payment_terms_prompt(form_input, precedents_clean)
            numbering_instruction = (
                "OUTPUT FORMAT STRICT:\n"
                f"- Output ONLY numbered subclauses like: {section_no}.1. ..., {section_no}.2. ..., each on a new line.\n"
                "- Each subclause MUST be exactly ONE complete legal sentence.\n"
                "- Do NOT merge two sentences into one line.\n"
                "- No headings, no blank lines, no bullets.\n"
                "- Do NOT repeat the same idea.\n"
                if lang == "en" else
                "СТРОГИЙ ФОРМАТ ВЫВОДА:\n"
                f"- Выведи ТОЛЬКО подпункты вида: {section_no}.1. ..., {section_no}.2. ..., каждый с новой строки.\n"
                "- Каждый подпункт — РОВНО одно законченное юридическое предложение.\n"
                "- НЕЛЬЗЯ ставить два предложения в одной строке.\n"
                "- Без заголовков, без пустых строк, без маркеров.\n"
                "- Начинай разные пункты по-разному: используй разные грамматические конструкции (например: 'Стороны согласовали…', 'Оплата производится…', 'НДС начисляется…', 'Изменение цены допускается…').\n"
                "- Не используй одну и ту же стартовую фразу более 2 раз во всём разделе.\n"
            )
            consistency = build_consistency_context(state=state, target_section_id=section_id)
            prompt = consistency + "\n\n" + numbering_instruction + "\n" + base_prompt

            base_validator = payment_terms_validator(
                bank_details_included=form_input["payment"]["bank_details_included"],
                late_payment_penalty_enabled=form_input["payment"]["late_payment_penalty_enabled"],
                min_chars_no_spaces=900,
                min_subclauses=20,
            )
            cons_validator = make_payment_consistency_validator(
                form_input, min_unique_lines=18, mode="warn", on_warning=_warn_to_state
            )
            validator = compose_validators(base_validator, cons_validator)

            def _pay_validate_after_format(text: str) -> Optional[str]:
                t = sanitize_text(text or "", lang=lang)
                t = drop_exact_duplicate_lines(t)
                t = ensure_numbered_lines(t, section_no=section_no)

                cnt = len(re.findall(rf"(?m)^\s*{section_no}\.\d+\.\s+", t))
                (debug_dir / "payment_terms_items_cnt_last.txt").write_text(str(cnt), encoding="utf-8")

                return validator(t)

            retry_instruction = (
                f"Rewrite the section.\n"
                f"Output at least 25 subclauses numbered {section_no}.1., {section_no}.2., ...\n"
                "- One sentence per line.\n"
                "- No blank lines.\n"
                "- Remove repetitions by replacing them with new payment-related topics.\n"
                if lang == "en" else
                f"Перепиши раздел.\n"
                f"Выведи не менее 25 подпунктов формата {section_no}.1., {section_no}.2., ...\n"
                "- Одно предложение на строке.\n"
                "- Без пустых строк.\n"
                "- Убери повторы, заменяя их новыми темами по оплате.\n"
            )

            generated, err, used = llm.generate_with_retry(
                system=_system_payment(form_input),
                user=prompt,
                validator=_pay_validate_after_format,
                retry_instruction=retry_instruction,
                save_bad_path=debug_dir / "payment_terms_llm_bad.txt",
            )
            (debug_dir / "payment_terms_llm_used_attempts.txt").write_text(str(used), encoding="utf-8")
            (debug_dir / "payment_terms_raw_last.txt").write_text(generated or "", encoding="utf-8")

            if err:
                raise RuntimeError(f"LLM output validation failed (payment_terms): {err}")

            generated = sanitize_text(generated, lang=lang)
            generated = drop_exact_duplicate_lines(generated)
            generated = ensure_numbered_lines(generated, section_no=section_no)

            generated = apply_antiloop_shingles(
                generated,
                debug_dir=debug_dir,
                section_id=section_id,
                section_no=section_no,
                lang=lang,
            )
            

            state = update_state_from_section(state=state, section_id=section_id, section_text=generated, form=form_input)
            state.save(state_path)

            sections_out.append(make_section_block(section_no=section_no, title=title, body_numbered=generated))
            generated_ids.add(section_id)
            continue

        # =========================================================
        # DELIVERY TERMS (retrieval)
        # =========================================================
        if section_id == "delivery_terms" and need_generate and not SKIP_RETRIEVAL_SECTIONS:
            print("DEBUG: BM25 retrieval for delivery_terms...")

            precedents_raw = retrieve_delivery_terms_bm25(form_input, corpus_rows, top_k=5, max_docs=1200)
            precedents_clean, rep = clean_precedents_delivery_terms(precedents_raw, min_chars=120, max_chars=2200)

            base_prompt = build_delivery_terms_prompt(form_input, precedents_clean)
            numbering_instruction = (
                "OUTPUT FORMAT STRICT:\n"
                f"- Output ONLY numbered subclauses like: {section_no}.1. ..., {section_no}.2. ..., each on a new line.\n"
                "- Each subclause MUST be exactly ONE complete legal sentence.\n"
                "- Do NOT merge two sentences into one line.\n"
                "- No headings, no blank lines, no bullets.\n"                
                "- Do NOT use the same beginning phrase more than twice.\n"
                if lang == "en" else
                "СТРОГИЙ ФОРМАТ ВЫВОДА:\n"
                f"- Выведи ТОЛЬКО подпункты вида: {section_no}.1. ..., {section_no}.2. ..., каждый с новой строки.\n"
                "- Каждый подпункт — одно законченное юридическое предложение.\n"
                "- НЕЛЬЗЯ ставить два предложения в одной строке.\n"
                "- Без заголовков, без пустых строк, без маркеров.\n"                
                "- Не используй одну и ту же стартовую фразу более 2 раз во всём разделе.\n"
            )
            consistency = build_consistency_context(state=state, target_section_id=section_id)
            prompt = consistency + "\n\n" + numbering_instruction + "\n" + base_prompt

            base_validator = delivery_terms_validator(min_chars_no_spaces=1100, min_subclauses=20)
            cons_validator = make_delivery_consistency_validator(
                form_input, min_unique_lines=20, mode="warn", on_warning=_warn_to_state
            )
            validator = compose_validators(base_validator, cons_validator)

            validator_after = wrap_validator_after_format(
                validator=validator,
                section_no=section_no,
                lang=lang,
                debug_cnt_path=debug_dir / "delivery_terms_items_cnt_last.txt",
            )

            generated, err, used = llm.generate_with_retry(
                system=_system_delivery(form_input),
                user=prompt,
                validator=validator_after,
                retry_instruction=retry_delivery(section_no=section_no, lang=lang),
                save_bad_path=debug_dir / "delivery_terms_llm_bad.txt",
            )
            (debug_dir / "delivery_terms_llm_used_attempts.txt").write_text(str(used), encoding="utf-8")

            if err:
                if SOFT_FAIL_SECTIONS:
                    _soft_fail_use_last_attempt(
                        section_id=section_id,
                        section_no=section_no,
                        title=title,
                        err=str(err),
                        last_text=generated,
                    )
                    continue
                raise RuntimeError(f"LLM output validation failed (delivery_terms): {err}")

            generated = sanitize_text(generated, lang=lang)
            generated = drop_exact_duplicate_lines(generated)
            generated = ensure_numbered_lines(generated, section_no=section_no)
            generated = apply_antiloop_shingles(
                generated,
                debug_dir=debug_dir,
                section_id=section_id,
                section_no=section_no,
                lang=lang,
            )

            state = update_state_from_section(state=state, section_id=section_id, section_text=generated, form=form_input)
            state.save(state_path)

            sections_out.append(make_section_block(section_no=section_no, title=title, body_numbered=generated))
            generated_ids.add(section_id)
            continue

        # =========================================================
        # EMBEDDINGS + GENERATION (sections 6-10)
        # =========================================================
        if need_generate and section_id in EMBEDDINGS_SECTION_IDS:
            print(f"DEBUG: embeddings+generation for {section_id}...")

            lang = _lang(form_input)

            # базовый промпт секции (используем те же builders, но отдельным блоком)
            base_prompt = FORM_BASED_BUILDERS[section_id](form_input, None)
            checklist = get_section_checklist(section_id, lang)
            # ensure corpus loaded
            if corpus_rows is None:
                corpus_path = root / "data" / "corpus_sections.jsonl"
                if not corpus_path.exists():
                    raise FileNotFoundError(f"Corpus file not found: {corpus_path}")
                corpus_rows = load_corpus_sections_jsonl(corpus_path)

            embedder = emb_cache["embedder"]
            dense_index: DenseIndex = emb_cache["dense_index"]
            dense_retriever: DenseRetriever = emb_cache["dense_retriever"]
            
            if corpus_rows is None:
                corpus_path = root / "data" / "corpus_sections.jsonl"
                if not corpus_path.exists():
                    raise FileNotFoundError(f"Corpus file not found: {corpus_path}")
                corpus_rows = load_corpus_sections_jsonl(corpus_path)
            
            if not emb_cache.get("text_lookup_ready", False):
                emb_cache["text_lookup"] = _build_text_lookup(corpus_rows)
                emb_cache["text_lookup_ready"] = True
                print(f"DEBUG: text_lookup built: keys={len(emb_cache['text_lookup'])}")

            text_lookup: dict = emb_cache["text_lookup"]

            # --- query embedding 
            query = build_embed_query(form_input, section_id, base_prompt)
            q_emb = np.array(embedder.embed(query), dtype=np.float32)  

            # --- retrieval по ГОТОВОЙ матрице эмбеддингов

            top_k = int(EMB_TOP_K_BY_SECTION.get(section_id, EMB_TOP_K))

            hits = dense_retriever.search(
                q_emb,
                top_k=top_k,
                section_id=section_id,
                language=lang,
            )

            # --- собираем прецеденты как list[dict] с полем "text"
            top_rows = []
            for idx, score in hits:
                m = dense_index.meta[idx]
                key = _make_doc_key(m)

                txt_list = text_lookup.get(key)
                txt = ""
                if txt_list:
                    # берём первый  
                    txt = txt_list[0]

                if not txt:
                    # запасной вариант: если есть text_preview или похожее
                    txt = (m.get("text") or m.get("text_preview") or "").strip()

                if txt:
                    top_rows.append({"text": txt, "score": float(score), "meta": m})

            top_rows = trim_precedents(top_rows)
            precedents_block = format_precedents_for_prompt(top_rows, lang=lang)
            

            # нумерация 
            target_subclauses = int(FORM_TARGET_SUBCLAUSES.get(section_id, 16))
            numbering_instruction = form_based_numbering_instruction(
                section_no=section_no,
                lang=lang,
                target_subclauses=target_subclauses,
            )

            consistency = build_consistency_context(state=state, target_section_id=section_id)

            
            guard = embeddings_guard_instruction(section_id=section_id, lang=lang)

            prompt = (
                consistency.strip()
                + "\n\n"
                + guard.strip()
                + "\n\n"
                + precedents_block.strip()
                + "\n\n"
                + checklist.strip() 
                + "\n\n"
                + base_prompt.strip()
                + "\n\n"
                + numbering_instruction.strip()
                + "\n"
            )
           

            base_validator = form_section_validator(
                section_no=section_no,
                min_chars_no_spaces=900,
                min_items=10,
            )

            validator_after = wrap_validator_after_format(
                validator=base_validator,
                section_no=section_no,
                lang=lang,
                debug_cnt_path=debug_dir / f"{section_id}_items_cnt_last.txt",
            )

            retry_instruction = retry_form_based(
                section_no=section_no,
                lang=lang,
                target_subclauses=target_subclauses,
            )

            generated, err, used = llm.generate_with_retry(
                system=_system_generic(form_input),
                user=prompt,
                validator=validator_after,
                retry_instruction=retry_instruction,   
                save_bad_path=debug_dir / f"{section_id}_llm_bad.txt",             
            )
            if err:
                raise RuntimeError(f"LLM generation failed ({section_id}): {err}")

            if form_input.get("language_mode") == "ru":
                generated = postprocess_ru_section(generated, section_id)

                        
            generated = sanitize_text(generated, lang=lang)         
            generated = drop_exact_duplicate_lines(generated)            
            generated = semantic_deduplicate_embeddings(
                generated,
                embedder=emb_cache["embedder"],
                threshold=0.90,
            )

            generated = ensure_numbered_lines(generated, section_no=section_no) 

            generated = apply_antiloop_shingles(
                generated,
                debug_dir=debug_dir,
                section_id=section_id,
                section_no=section_no,
                lang=lang,
                repair_sem_threshold=0.92,
            )

            state = update_state_from_section(
                state=state,
                section_id=section_id,
                section_text=generated,
                form=form_input,
            )
            state.save(state_path)

            sections_out.append(make_section_block(section_no=section_no, title=title, body_numbered=generated))
            generated_ids.add(section_id)
            continue

        # =========================================================
        # FORM-BASED sections
        # =========================================================
        def strip_markdown_basic(s: str) -> str:
            return (s or "").replace("**", "").replace("__", "").replace("###", "").replace("##", "").replace("#", "").strip()
        
        if need_generate and section_id in FORM_ONLY_SECTION_IDS:
            print(f"DEBUG: form-based generation for {section_id}...")

            base_prompt = FORM_BASED_BUILDERS[section_id](form_input, None)
            lang = _lang(form_input)

            target_subclauses = int(FORM_TARGET_SUBCLAUSES.get(section_id, 16))
            checklist = get_section_checklist(section_id, lang)

            numbering_instruction = form_based_numbering_instruction(
                section_no=section_no,
                lang=lang,
                target_subclauses=target_subclauses,
            )

            consistency = build_consistency_context(state=state, target_section_id=section_id)

            prompt = (
                consistency.strip()
                + "\n\n"
                + (checklist.strip() + "\n\n" if checklist else "")
                + "\n\n"
                + base_prompt.strip()
                + "\n\n"
                + numbering_instruction.strip()
                + "\n"
            )

            # debug: сохраняем и base, и финальный prompt
            (debug_dir / f"{section_id}_base_prompt.txt").write_text(base_prompt, encoding="utf-8")
            (debug_dir / f"{section_id}_prompt.txt").write_text(prompt, encoding="utf-8")

            min_chars_no_spaces = int(FORM_SECTION_MIN_CHARS[section_id])
            min_items = max(8, target_subclauses - 2)

            base_validator = form_section_validator(
                section_no=section_no,
                min_chars_no_spaces=min_chars_no_spaces,
                min_items=min_items,
            )

            validator_after = wrap_validator_after_format(
                validator=base_validator,
                section_no=section_no,
                lang=lang,
                debug_cnt_path=debug_dir / f"{section_id}_items_cnt_last.txt",
            )

            retry_instruction = retry_form_based(
                section_no=section_no,
                lang=lang,
                target_subclauses=target_subclauses,
            )

            generated, err, used = llm.generate_with_retry(
                system=_system_generic(form_input),
                user=prompt,
                validator=validator_after,
                retry_instruction=retry_instruction,
                save_bad_path=debug_dir / f"{section_id}_llm_bad.txt",
            )
            (debug_dir / f"{section_id}_llm_used_attempts.txt").write_text(str(used), encoding="utf-8")

            if err:
                if SOFT_FAIL_SECTIONS:
                    _soft_fail_use_last_attempt(
                        section_id=section_id,
                        section_no=section_no,
                        title=title,
                        err=str(err),
                        last_text=generated,
                    )
                    continue
                raise RuntimeError(f"LLM output validation failed ({section_id}): {err}")

            if form_input.get("language_mode") == "ru":
                generated = postprocess_ru_section(generated, section_id)

            generated = strip_markdown_basic(generated)
            generated = sanitize_text(generated, lang=lang)
            generated = drop_exact_duplicate_lines(generated)           
            generated = semantic_deduplicate(generated)
            generated = ensure_numbered_lines(generated, section_no=section_no)
            generated = apply_antiloop_shingles(
                generated,
                debug_dir=debug_dir,
                section_id=section_id,
                section_no=section_no,
                lang=lang,
            )

            # debug final count
            final_cnt = len(re.findall(rf"(?m)^\s*{section_no}\.\d+\.\s+", generated))
            (debug_dir / f"{section_id}_final_items_cnt.txt").write_text(str(final_cnt), encoding="utf-8")

            state = update_state_from_section(
                state=state,
                section_id=section_id,
                section_text=generated,
                form=form_input,
            )
            state.save(state_path)

            sections_out.append(make_section_block(section_no=section_no, title=title, body_numbered=generated))
            generated_ids.add(section_id)
            continue

        # =========================================================
        # other sections: placeholder
        # =========================================================
        placeholder = f"{section_no}.1. (Раздел пока не реализован.)"
        sections_out.append(make_section_block(section_no=section_no, title=title, body_numbered=placeholder))

    # post coverage
    report = postcheck_coverage(plan, generated_sections=generated_ids, form=form_input)
    (debug_dir / "coverage_report.json").write_text(
        json.dumps(
            {
                "required_total": report.required_total,
                "present_required": report.present_required,
                "missing_required": report.missing_required,
                "present_optional": report.present_optional,
                "unknown_present": report.unknown_present,
                "completion_ratio": report.completion_ratio,
                "notes": report.notes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"DEBUG: coverage required={report.present_required}/{report.required_total} ratio={report.completion_ratio:.2f}")
    if report.missing_required:
        print("DEBUG: missing required sections:", report.missing_required)

    return "\n\n".join(sections_out)


def main() -> int:
    root = Path(__file__).parent

    form_path = root / "form_input.json"
    if not form_path.exists():
        print("ERROR: form_input.json not found (expected in repo root)", file=sys.stderr)
        return 1

    schema_path = root / "src" / "form_schema" / "contract_form_v2.schema.json"
    if not schema_path.exists():
        print(f"ERROR: schema not found: {schema_path}", file=sys.stderr)
        return 1

    form_data = json.loads(form_path.read_text(encoding="utf-8"))

    issues = validate_form(form_data, schema_path=schema_path)
    if issues:
        print("❌ Form validation failed:")
        for issue in issues:
            print(f"- {issue.path}: {issue.message}")
        return 1

    print("✅ Form validated successfully")

    contract_text = generate_contract(form_data)

    title = contract_title(form_data)
    contract_text = title + "\n\n" + contract_text

    txt_path = root / "out.txt"
    docx_path = root / "contract.docx"

    txt_path.write_text(contract_text, encoding="utf-8")
    txt_to_docx(txt_path, docx_path)

    print(f"📄 Contract generated: {txt_path}")
    print(f"📝 DOCX generated: {docx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
