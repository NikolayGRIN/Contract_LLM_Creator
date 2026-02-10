# src/validation/section_quality_guards.py
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


# =========================================================
# 1) Form sanitization (не даём '' и пустым строкам протекать в промпт)
# =========================================================

def sanitize_form(form: Dict[str, Any]) -> Dict[str, Any]:
    """
    Делает "мягкую" очистку form_input:
    - удаляет пустые строки, '""', "''"
    - удаляет None
    - удаляет пустые dict/list после очистки
    - НЕ меняет типы чисел/булевых
    - не падает
    """
    def clean_scalar(x: Any) -> Any:
        if isinstance(x, str):
            s = x.strip()
            if s == "" or s in ("''", '""'):
                return None
            return s
        return x

    def walk(obj: Any) -> Any:
        try:
            obj = clean_scalar(obj)

            if obj is None:
                return None

            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    vv = walk(v)
                    if vv is None:
                        continue
                    out[k] = vv
                return out if out else None

            if isinstance(obj, list):
                out_list = []
                for v in obj:
                    vv = walk(v)
                    if vv is None:
                        continue
                    out_list.append(vv)
                return out_list if out_list else None

            return obj
        except Exception:
            # никогда не падаем на санитизации
            return obj

    cleaned = walk(form)
    return cleaned if isinstance(cleaned, dict) else (form or {})


# =========================================================
# 2) Guards: forbidden topics + repetition
# =========================================================

_word_re = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)

def _normalize(text: str) -> str:
    t = (text or "").replace("\u00A0", " ")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def split_sentences(text: str) -> List[str]:
    """
    Простое разбиение на предложения: достаточно для метрики повторов.
    """
    t = _normalize(text)
    if not t:
        return []
    # сохраняем смысл, но не усложняем
    parts = re.split(r"(?<=[.!?])\s+", t)
    sents = [p.strip() for p in parts if p and p.strip()]
    return sents

def sentence_unique_ratio(text: str) -> float:
    sents = split_sentences(text)
    if len(sents) < 5:
        return 1.0
    uniq = len(set(sents))
    return uniq / max(1, len(sents))

def has_forbidden_topics(
    text: str,
    forbidden: List[str],
    *,
    threshold: int = 2,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Возвращает (bad, details). bad=True если найдено >= threshold совпадений.
    forbidden: список "стемов"/подстрок (lowercase) — без регэкспов.
    """
    low = _normalize(text).lower()
    hits = [w for w in forbidden if w in low]
    bad = len(hits) >= int(threshold)
    return bad, {"hits": hits, "hits_count": len(hits), "threshold": int(threshold)}

def repetition_bad(
    text: str,
    *,
    min_unique_ratio: float = 0.78,
) -> Tuple[bool, Dict[str, Any]]:
    """
    bad=True если уникальность предложений слишком низкая.
    """
    r = float(sentence_unique_ratio(text))
    bad = r < float(min_unique_ratio)
    return bad, {"sentence_unique_ratio": r, "min_unique_ratio": float(min_unique_ratio)}

def _tokenize_words(text: str) -> List[str]:
    return _word_re.findall((_normalize(text)).lower())

def shingle_stats(text: str, *, k_words: int = 5) -> Dict[str, int]:
    """
    Возвращает частоты k-word shingles (по словам).
    """
    words = _tokenize_words(text)
    if len(words) < k_words:
        return {}
    counts: Dict[str, int] = {}
    for i in range(0, len(words) - k_words + 1):
        sh = " ".join(words[i:i + k_words])
        counts[sh] = counts.get(sh, 0) + 1
    return counts

def shingle_loop_bad(
    text: str,
    *,
    k_words: int = 5,
    max_occ: int = 2,
    max_overused_shingles: int = 2,
) -> Tuple[bool, Dict[str, Any]]:
    """
    bad=True если в тексте есть слишком много "переповторяемых" шинглов.
    Переповторяемый шингл: встречается >= max_occ раз.
    """
    counts = shingle_stats(text, k_words=k_words)
    if not counts:
        return False, {"k_words": k_words, "overused": [], "overused_count": 0}

    overused = sorted(
        [(sh, c) for sh, c in counts.items() if c >= int(max_occ)],
        key=lambda x: x[1],
        reverse=True,
    )
    bad = len(overused) > int(max_overused_shingles)
    # не раздуваем debug: топ-10
    return bad, {
        "k_words": int(k_words),
        "max_occ": int(max_occ),
        "max_overused_shingles": int(max_overused_shingles),
        "overused_count": len(overused),
        "overused_top": overused[:10],
    }


@dataclass
class GuardProfile:
    """
    Настройки guard для секции.
    """
    # ВАЖНО: чтобы fallback мог не передавать forbidden — даём дефолт []
    forbidden: List[str]
    forbidden_threshold: int = 2

    # repetition
    check_repetition: bool = True
    min_unique_ratio: float = 0.78

    # ✅ PATCH: нужен, потому что ты передаёшь его в default_profile_for_section()
    max_duplicate_sentences: int = 1

    # optionally: minimum size check
    check_min_chars: bool = False
    min_chars_no_spaces: int = 0

    # shingle anti-loop
    check_shingles: bool = True
    shingle_k_words: int = 5
    shingle_max_occ: int = 2
    shingle_max_overused: int = 2


def default_profile_for_section(section_id: str, language_mode: str = "ru") -> GuardProfile:
    """
    Строгие профили качества по каждому разделу договора.
    """
    sid = (section_id or "").lower()

    # -------------------------------------------------------
    # 1. DEFINITIONS
    # -------------------------------------------------------
    if sid == "definitions":
        return GuardProfile(
            forbidden=[
                "оплата", "платеж", "штраф", "гарантия", "арбитраж",
                "payment", "penalty", "liability", "arbitration"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.85,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_k_words=5,
            shingle_max_occ=3,
            shingle_max_overused=1,
        )

    # -------------------------------------------------------
    # 2. SUBJECT
    # -------------------------------------------------------
    if sid == "subject_of_contract":
        return GuardProfile(
            forbidden=[
                "штраф", "ответственност", "арбитраж", "форс",
                "penalty", "liability", "force majeure"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.82,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_max_occ=3,
            shingle_max_overused=2,
        )

    # -------------------------------------------------------
    # 3. PRICE
    # -------------------------------------------------------
    if sid == "price_and_taxes":
        return GuardProfile(
            forbidden=[
                "гарант", "арбитраж", "форс",
                "warranty", "arbitration", "force majeure"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.80,
            max_duplicate_sentences=1,
            check_shingles=True,
            shingle_max_occ=3,
            shingle_max_overused=2,
        )

    # -------------------------------------------------------
    # 4. PAYMENT
    # -------------------------------------------------------
    if sid == "payment_terms":
        return GuardProfile(
            forbidden=[
                "гарант", "форс", "арбитраж",
                "warranty", "force majeure", "arbitration"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.88,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_k_words=5,
            shingle_max_occ=3,
            shingle_max_overused=1,
        )

    # -------------------------------------------------------
    # 5. DELIVERY
    # -------------------------------------------------------
    if sid == "delivery_terms":
        return GuardProfile(
            forbidden=[
                "гарант", "арбитраж", "штраф",
                "warranty", "arbitration", "penalty"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.86,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_max_occ=3,
            shingle_max_overused=1,
        )

    # -------------------------------------------------------
    # 6. ACCEPTANCE
    # -------------------------------------------------------
    if sid == "acceptance_and_inspection":
        return GuardProfile(
            forbidden=[
                "арбитраж", "форс", "штраф",
                "arbitration", "force majeure", "penalty"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.85,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_max_occ=3,
            shingle_max_overused=1,
        )

    # -------------------------------------------------------
    # 7. WARRANTIES
    # -------------------------------------------------------
    if sid == "warranties":
        return GuardProfile(
            forbidden=[
                "оплата", "арбитраж", "форс",
                "payment", "arbitration", "force majeure"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.88,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_max_occ=3,
            shingle_max_overused=1,
        )

    # -------------------------------------------------------
    # 8. LIABILITY
    # -------------------------------------------------------
    if sid == "liability_and_penalties":
        return GuardProfile(
            forbidden=[],
            forbidden_threshold=999,
            min_unique_ratio=0.92,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_k_words=5,
            shingle_max_occ=2,
            shingle_max_overused=0,
        )

    # -------------------------------------------------------
    # 9. FORCE MAJEURE
    # -------------------------------------------------------
    if sid == "force_majeure":
        return GuardProfile(
            forbidden=[
                "оплата", "гарант", "штраф",
                "payment", "warranty", "penalty"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.90,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_max_occ=3,
            shingle_max_overused=1,
        )

    # -------------------------------------------------------
    # 10. GOVERNING LAW
    # -------------------------------------------------------
    if sid == "governing_law_and_disputes":
        return GuardProfile(
            forbidden=[
                "гарант", "оплата", "поставка",
                "warranty", "payment", "delivery"
            ],
            forbidden_threshold=1,
            min_unique_ratio=0.88,
            max_duplicate_sentences=0,
            check_shingles=True,
            shingle_max_occ=3,
            shingle_max_overused=1,
        )

    # -------------------------------------------------------
    # fallback (✅ PATCH: forbidden обязателен)
    # -------------------------------------------------------
    return GuardProfile(
        forbidden=[],
        forbidden_threshold=999,
        check_repetition=True,
        min_unique_ratio=0.80,
        max_duplicate_sentences=1,
        check_shingles=True,
        shingle_max_occ=3,
        shingle_max_overused=2,
    )


# =========================================================
# 4) Validation: собрать ошибки, но не падать
# =========================================================

def validate_section_text(
    *,
    section_id: str,
    language_mode: str,
    text: str,
    profile: Optional[GuardProfile] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Возвращает: (ok, errors, debug)
    Никогда не бросает исключения.
    """
    try:
        prof = profile or default_profile_for_section(section_id, language_mode)
        t = _normalize(text)

        errors: List[str] = []
        dbg: Dict[str, Any] = {"section_id": section_id, "language_mode": language_mode}

        # forbidden topics
        if prof.forbidden and prof.forbidden_threshold < 999:
            bad, det = has_forbidden_topics(t, prof.forbidden, threshold=prof.forbidden_threshold)
            dbg["forbidden"] = det
            if bad:
                errors.append(
                    f"forbidden_topics: hits={det.get('hits_count')} >= {det.get('threshold')} ({det.get('hits')})"
                )

        # repetition
        if prof.check_repetition:
            bad, det = repetition_bad(t, min_unique_ratio=prof.min_unique_ratio)
            dbg["repetition"] = det
            if bad:
                errors.append(
                    f"repetition_low_unique: ratio={det.get('sentence_unique_ratio'):.3f} < {det.get('min_unique_ratio'):.3f}"
                )

        # shingle anti-loop
        if getattr(prof, "check_shingles", False):
            bad, det = shingle_loop_bad(
                t,
                k_words=prof.shingle_k_words,
                max_occ=prof.shingle_max_occ,
                max_overused_shingles=prof.shingle_max_overused,
            )
            dbg["shingles"] = det
            if bad:
                errors.append(
                    f"shingle_loop: overused_count={det.get('overused_count')} > {det.get('max_overused_shingles')}"
                )

        # optional min chars
        if prof.check_min_chars and prof.min_chars_no_spaces > 0:
            no_spaces = len(re.sub(r"\s+", "", t))
            dbg["min_chars"] = {"no_spaces": no_spaces, "min_required": prof.min_chars_no_spaces}
            if no_spaces < prof.min_chars_no_spaces:
                errors.append(f"too_short: chars_no_spaces={no_spaces} < {prof.min_chars_no_spaces}")

        return (len(errors) == 0), errors, dbg

    except Exception as e:
        # fail-open: не блокируем пайплайн
        return True, [], {"warning": f"validate_section_text failed-open: {e}"}


# =========================================================
# 5) Guarded generation loop: НЕ падает, ретраи, best-effort
# =========================================================

@dataclass
class GuardedResult:
    text: str
    ok: bool
    attempts: int
    errors: List[str]
    debug: Dict[str, Any]


def guarded_generate(
    *,
    section_id: str,
    language_mode: str,
    generate_fn: Callable[[int], str],
    # generate_fn(attempt_index) -> text
    profile: Optional[GuardProfile] = None,
    max_attempts: int = 6,
    sleep_sec: float = 0.0,
    # стратегия "не падать": если всё плохо — вернуть лучший вариант
    # лучший = минимум ошибок, а при равенстве — выше unique_ratio
) -> GuardedResult:
    """
    generate_fn: функция, которая генерирует текст секции.
      Ей передаётся attempt_index (0..), чтобы ты мог внутри
      менять prompt/параметры (например усиливать запреты на 2+ попытке).

    Возвращает GuardedResult и никогда не кидает исключений.
    """
    best_text = ""
    best_errors: List[str] = ["no_attempts"]
    best_dbg: Dict[str, Any] = {}
    best_score = -1e9  # больше = лучше

    attempts = 0

    for attempt in range(int(max_attempts)):
        attempts = attempt + 1
        try:
            text = generate_fn(attempt)
        except Exception as e:
            # генератор упал — не падаем, идём дальше
            text = ""
            ok = False
            errors = [f"generate_fn_exception: {e}"]
            dbg = {"exception": str(e)}
        else:
            ok, errors, dbg = validate_section_text(
                section_id=section_id,
                language_mode=language_mode,
                text=text,
                profile=profile,
            )

        # scoring для "best-effort":
        # - меньше ошибок -> лучше
        # - выше unique_ratio -> лучше
        rep = dbg.get("repetition", {})
        uniq = rep.get("sentence_unique_ratio", 0.0) if isinstance(rep, dict) else 0.0
        score = -10.0 * len(errors) + float(uniq)

        if score > best_score:
            best_score = score
            best_text = text
            best_errors = errors
            best_dbg = dbg

        if ok:
            return GuardedResult(
                text=text,
                ok=True,
                attempts=attempts,
                errors=[],
                debug=dbg,
            )

        if sleep_sec and sleep_sec > 0:
            try:
                time.sleep(float(sleep_sec))
            except Exception:
                pass

    # если не получилось — не падаем: возвращаем лучший найденный
    return GuardedResult(
        text=best_text,
        ok=False,
        attempts=attempts,
        errors=best_errors,
        debug=best_dbg,
    )

def _dedup_sentences(text: str, *, max_dup: int) -> str:
    sents = split_sentences(text)
    if not sents:
        return text

    counts: Dict[str, int] = {}
    out: List[str] = []
    for s in sents:
        key = re.sub(r"\s+", " ", s.strip().lower())
        counts[key] = counts.get(key, 0) + 1
        if counts[key] <= max_dup + 1:  # max_dup=0 => оставить только 1 раз
            out.append(s.strip())

    # склеиваем обратно “мягко”
    return " ".join(out).strip()


def validate_and_fix_section(
    *,
    section_id: str,
    language_mode: str,
    text: str,
    profile: Optional[GuardProfile] = None,
) -> str:
    """
    Best-effort постобработка. Ничего не “роняет” и не удаляет секцию целиком.
    Регенерации НЕ делает (для этого guarded_generate).
    """
    try:
        prof = profile or default_profile_for_section(section_id, language_mode)
        t0 = text or ""
        t = _normalize(t0)

        # 1) dedup предложений (используем max_duplicate_sentences)
        t = _dedup_sentences(t, max_dup=int(prof.max_duplicate_sentences))

        # 2) если после чистки стало пусто — возвращаем оригинал (fail-open)
        if not t.strip() and t0.strip():
            return t0.strip()

        return t.strip()
    except Exception:
        return (text or "").strip()
