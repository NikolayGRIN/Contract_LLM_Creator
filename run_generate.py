from __future__ import annotations

from pathlib import Path
import json
import sys
import importlib

from src.validation.form_validate import validate_form

from src.validation.payment_terms_validator import payment_terms_validator
from src.validation.delivery_terms_validator import delivery_terms_validator

from src.retrieval.bm25 import (
    load_corpus_sections_jsonl,
    retrieve_payment_terms_bm25,
    retrieve_delivery_terms_bm25,
)

from src.cleaning.precedent_cleaner import (
    clean_precedents_payment_terms,
    clean_precedents_delivery_terms,
)

from src.generation.payment_terms_generate import build_payment_terms_prompt
from src.generation.delivery_terms_generate import build_delivery_terms_prompt

#SKIP_SECTIONS = {"payment_terms"}     # временно пропускаем payment_terms, чтобы генерировать только delivery_terms
#ONLY_SECTIONS = None                 


def llm_generate_stub(section_id: str, precedents: list[str] | None = None) -> str:
    block = f"[{section_id.upper()}]\n"
    if precedents:
        block += "=== RETRIEVED PRECEDENTS ===\n"
        for i, p in enumerate(precedents, start=1):
            block += f"\n--- Example {i} ---\n{p.strip()}\n"
        block += "\n=== END PRECEDENTS ===\n"
    block += "\n(Section text will be generated here)\n"
    return block


def get_generation_order() -> list[str]:
    return [
        "payment_terms",
        "delivery_terms",
        "liability_penalties",
        "disputes_governing_law",
    ]



# единый бэкенд (llama-cpp-python + GGUF) для ноутбука и Colab

def make_llm(*, root: Path):
    
    from src.generation.local_llm import LocalLLM, LLMConfig
    
    cfg = importlib.import_module("src.config")

    model_path_str = getattr(cfg, "LOCAL_GGUF_MODEL_PATH", None) or getattr(cfg, "LOCAL_MODEL_PATH", None)
    if not model_path_str:
        raise RuntimeError("src/config.py must define LOCAL_GGUF_MODEL_PATH (or LOCAL_MODEL_PATH)")

    model_path = Path(str(model_path_str))
    if not model_path.is_absolute():
        model_path = root / model_path
    if not model_path.exists():
        raise FileNotFoundError(f"GGUF model not found: {model_path}")

    # Опциональные параметры из конфигурации 
    n_ctx = int(getattr(cfg, "N_CTX", 4096))
    n_threads = int(getattr(cfg, "N_THREADS", 8))
    temperature = float(getattr(cfg, "TEMPERATURE", 0.3))
    top_p = float(getattr(cfg, "TOP_P", 0.92))
    max_tokens = int(getattr(cfg, "MAX_TOKENS", 1600))
    n_gpu_layers = getattr(cfg, "N_GPU_LAYERS", None)

    cfg_kwargs = dict(
        model_path=model_path,
        n_ctx=n_ctx,
        n_threads=n_threads,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
    if n_gpu_layers is not None:
        cfg_kwargs["n_gpu_layers"] = int(n_gpu_layers)

    return LocalLLM(LLMConfig(**cfg_kwargs))



# Вспомогательные функции для двуязычных промптов

def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


def _system_payment(form_input: dict) -> str:
    if _lang(form_input) == "en":
        return (
            "You are a careful legal drafting assistant. "
            "Strictly follow the user parameters and constraints. "
            "Write in a formal legal style. "
            "Do not invent facts. "
            "Do not copy amounts, currencies, rates, countries, company names, clause numbers, or bank details from precedents."
        )
    return (
        "Ты — аккуратный юридический ассистент. "
        "Строго следуй параметрам и ограничениям из запроса пользователя. "
        "Пиши формально-деловым стилем. "
        "Не выдумывай факты. "
        "Не копируй реквизиты, суммы, валюты, ставки, страны и номера пунктов из прецедентов."
    )


def _retry_payment(form_input: dict, *, min_items: int = 20) -> str:
    if _lang(form_input) == "en":
        return (
            "The previous draft failed validation. "
            f"You MUST output AT LEAST {min_items} subclauses formatted strictly as 1.1., 1.2., ... each on a new line. "
            "DO NOT rewrite existing subclauses; add new ones without repetition. "
            "Every new subclause must add a distinct aspect within Payment Terms only. "
            "Do not include bank details if they are not allowed by the form. "
            "Keep a formal legal style and increase the content without duplicates."
            "Avoid repeating the same clause opening more than twice."
            "Rewrite clauses using varied sentence structures (passive voice, conditional clauses, impersonal formulations)."
        )
    return (
        "Предыдущий вариант не прошёл автоматическую проверку. "
        f"Нужно НЕ МЕНЕЕ {min_items} подпунктов формата 1.1., 1.2., ... каждый с новой строки. "
        "ВАЖНО: не переписывай и не повторяй уже написанные подпункты. "
        "Каждый новый подпункт должен добавлять новый аспект (без повторов) и оставаться в рамках Payment Terms. "
        "Не добавляй банковские реквизиты (если запрещено формой). "
        "Соблюдай юридический стиль и увеличь объём без повторов."
    )


def _system_delivery(form_input: dict) -> str:
    if _lang(form_input) == "en":
        return (
            "You are a careful legal drafting assistant. "
            "Strictly follow the user parameters and constraints. "
            "Write in a formal legal style. "
            "Do not invent facts. "
            "Do not copy addresses, specific dates, Incoterms, company names, or clause numbers from precedents."
        )
    return (
        "Ты — аккуратный юридический ассистент. "
        "Строго следуй параметрам и ограничениям из запроса пользователя. "
        "Пиши формально-деловым стилем. "
        "Не выдумывай факты. "
        "Не копируй адреса, сроки, Incoterms, компании и номера пунктов из прецедентов."
    )


def _retry_delivery(form_input: dict, *, min_items: int = 20) -> str:
    if _lang(form_input) == "en":
        return (
            "The previous draft failed validation. "
            f"You MUST output AT LEAST {min_items} subclauses formatted strictly as 2.1., 2.2., ... each on a new line. "
            "DO NOT rewrite existing subclauses; add new ones without repetition. "
            "Every new subclause must add a distinct aspect within Delivery Terms only. "
            "Do not add payment terms, penalties, or dispute resolution. "
            "Keep a formal legal style and increase the content without duplicates."
        )
    return (
        "Предыдущий вариант не прошёл автоматическую проверку. "
        f"Нужно НЕ МЕНЕЕ {min_items} подпунктов формата 2.1., 2.2., ... каждый с новой строки. "
        "ВАЖНО: не переписывай и не повторяй уже написанные подпункты. "
        "Каждый новый подпункт должен добавлять новый аспект (без повторов) и оставаться в рамках Delivery Terms. "
        "Не добавляй оплату/штрафы/споры. Соблюдай юридический стиль и увеличь объём без повторов."
    )


# Основной пайплайн

def generate_contract(form_input: dict) -> str:
    root = Path(__file__).parent

    corpus_path = root / "data" / "corpus_sections.jsonl"
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus file not found: {corpus_path}")

    debug_dir = root / "debug"
    debug_dir.mkdir(exist_ok=True)

    llm = make_llm(root=root)
    corpus_rows = load_corpus_sections_jsonl(corpus_path)

    sections: list[str] = []

    for section_id in get_generation_order():
        

        # if ONLY_SECTIONS is not None and section_id not in ONLY_SECTIONS:
        #      continue

        # if section_id in SKIP_SECTIONS:
        #      print(f"DEBUG: skipping section: {section_id}")
        #      sections.append(llm_generate_stub(section_id, precedents=None))
        #      continue
        # =========================================================
        # Условия оплаты (1.x) — двуязычный, 20+ пунктов
        # =========================================================
        if section_id == "payment_terms":
            print("DEBUG: BM25 retrieval for payment_terms...")

            precedents_raw = retrieve_payment_terms_bm25(
                form_input,
                corpus_rows,
                top_k=7,       
                max_docs=800,
            )
            print(f"DEBUG: retrieved {len(precedents_raw)} raw precedents")

            (debug_dir / "payment_terms_precedents_raw.txt").write_text(
                ("\n\n" + ("=" * 60) + "\n\n").join(precedents_raw),
                encoding="utf-8",
            )

            precedents_clean, rep = clean_precedents_payment_terms(
                precedents_raw,
                min_chars=120,
                max_chars=1800,
            )
            print(
                "DEBUG: cleaner report:",
                f"in={rep.input_count}, out={rep.output_count}, "
                f"dropped_empty={rep.dropped_empty}, dropped_dups={rep.dropped_duplicates}, "
                f"replacements={rep.total_replacements}",
            )

            (debug_dir / "payment_terms_precedents_clean.txt").write_text(
                ("\n\n" + ("=" * 60) + "\n\n").join(precedents_clean),
                encoding="utf-8",
            )

            prompt = build_payment_terms_prompt(form_input, precedents_clean)
            (debug_dir / "payment_terms_prompt.txt").write_text(prompt, encoding="utf-8")

            validator = payment_terms_validator(
                bank_details_included=form_input["payment"]["bank_details_included"],
                late_payment_penalty_enabled=form_input["payment"]["late_payment_penalty_enabled"],
                min_chars_no_spaces=900,
                min_subclauses=20,
            )

            generated, err, used = llm.generate_with_retry(
                system=_system_payment(form_input),
                user=prompt,
                validator=validator,
                retry_instruction=_retry_payment(form_input, min_items=20),
                save_bad_path=debug_dir / "payment_terms_llm_bad.txt",
            )

            if err:
                raise RuntimeError(f"LLM output validation failed (payment_terms): {err}")

            (debug_dir / "payment_terms_llm_used_attempts.txt").write_text(str(used), encoding="utf-8")
            sections.append("[PAYMENT_TERMS]\n" + generated)
            continue

        
        # Условия поставки (2.x) — двуязычный, 20+ пунктов
        
        if section_id == "delivery_terms":
            print("DEBUG: BM25 retrieval for delivery_terms...")

            precedents_raw = retrieve_delivery_terms_bm25(
                form_input,
                corpus_rows,
                top_k=7,
                max_docs=1200,
            )
            print(f"DEBUG: retrieved {len(precedents_raw)} raw precedents")

            (debug_dir / "delivery_terms_precedents_raw.txt").write_text(
                ("\n\n" + ("=" * 60) + "\n\n").join(precedents_raw),
                encoding="utf-8",
            )

            precedents_clean, rep = clean_precedents_delivery_terms(
                precedents_raw,
                min_chars=120,
                max_chars=2200,
            )
            print(
                "DEBUG: cleaner report:",
                f"in={rep.input_count}, out={rep.output_count}, "
                f"dropped_empty={rep.dropped_empty}, dropped_dups={rep.dropped_duplicates}, "
                f"replacements={rep.total_replacements}",
            )

            (debug_dir / "delivery_terms_precedents_clean.txt").write_text(
                ("\n\n" + ("=" * 60) + "\n\n").join(precedents_clean),
                encoding="utf-8",
            )

            prompt = build_delivery_terms_prompt(form_input, precedents_clean)
            (debug_dir / "delivery_terms_prompt.txt").write_text(prompt, encoding="utf-8")

            validator = delivery_terms_validator(
                min_chars_no_spaces=1100,
                min_subclauses=20,
                prefix="2",
            )

            generated, err, used = llm.generate_with_retry(
                system=_system_delivery(form_input),
                user=prompt,
                validator=validator,
                retry_instruction=_retry_delivery(form_input, min_items=20),
                save_bad_path=debug_dir / "delivery_terms_llm_bad.txt",
            )

            if err:
                raise RuntimeError(f"LLM output validation failed (delivery_terms): {err}")

            (debug_dir / "delivery_terms_llm_used_attempts.txt").write_text(str(used), encoding="utf-8")
            sections.append("[DELIVERY_TERMS]\n" + generated)
            continue

        
        sections.append(llm_generate_stub(section_id, precedents=None))

    return "\n\n".join(sections)


def main() -> int:
    root = Path(__file__).parent

    
    # - form_input.json in repo root (для Colab)
    # - data/form_input.json для локального ПК
    form_path_candidates = [
        #root / "form_input.json",
        root / "data" / "form_input.json",
    ]
    form_path = next((p for p in form_path_candidates if p.exists()), None)
    if not form_path:
        print("ERROR: form_input.json не найден", file=sys.stderr)
        return 1

    schema_path = root / "src" / "form_schema" / "contract_form_v1.schema.json"
    if not schema_path.exists():
        print(f"ERROR: schema не найден: {schema_path}", file=sys.stderr)
        return 1

    form_data = json.loads(form_path.read_text(encoding="utf-8"))

    issues = validate_form(form_data, schema_path=schema_path)
    if issues:
        print("Form validation failed:")
        for issue in issues:
            print(f"- {issue.path}: {issue.message}")
        return 1

    print("Form validated successfully")

    contract_text = generate_contract(form_data)

    print("DEBUG: generation finished, writing out.txt")
    out_path = root / "out.txt"
    out_path.write_text(contract_text, encoding="utf-8")

    print(f"Contract generated: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
