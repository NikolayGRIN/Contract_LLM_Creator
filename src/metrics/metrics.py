from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ============================================================
# Helpers
# ============================================================

_SPACE_RE = re.compile(r"\s+")
_PLACEHOLDER_RE = re.compile(r"\[[A-Z_]+\]")
_SENT_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_MULTI_SENTENCE_IN_LINE_RE = re.compile(r"[.!?]\s+[A-ZА-ЯЁ]")  # ".... Xxxxx"
_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9']+")


def _now() -> float:
    return time.perf_counter()


def _strip_spaces(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _norm_ws(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = s.replace("\r\n", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _token_estimate(text: str) -> int:
    """
    Очень грубая оценка "токенов" без внешних библиотек:
    - для английского ~1 токен на ~0.75 слова
    - для русского ~1 токен на ~0.9 слова
    Здесь используем просто слова; это для относительных сравнений.
    """
    words = _WORD_RE.findall(text or "")
    return max(1, int(len(words) * 0.85))


def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _split_sentences(text: str) -> List[str]:
    t = _norm_ws(text)
    if not t:
        return []
    parts = [p.strip() for p in _SENT_BOUNDARY_RE.split(t) if p.strip()]
    return parts


def _avg(nums: Sequence[float]) -> float:
    return sum(nums) / len(nums) if nums else 0.0


def _stdev(nums: Sequence[float]) -> float:
    if len(nums) < 2:
        return 0.0
    m = _avg(nums)
    v = sum((x - m) ** 2 for x in nums) / (len(nums) - 1)
    return math.sqrt(v)


def _safe_div(a: float, b: float) -> float:
    return (a / b) if b else 0.0


# ============================================================
# Data Models
# ============================================================

@dataclass
class RetrievalMetrics:
    k: int = 0
    unique_docs: int = 0
    unique_ratio: float = 0.0          # unique_docs / k
    score_min: float = 0.0
    score_max: float = 0.0
    score_mean: float = 0.0
    score_stdev: float = 0.0
    score_gap_1_2: float = 0.0         # score[0] - score[1]
    mrr: Optional[float] = None        # if relevant_ids provided
    recall_at_k: Optional[float] = None
    hit_at_1: Optional[bool] = None

@dataclass
class GenerationMetrics:
    nonempty_lines: int = 0
    sentences: int = 0
    chars_no_spaces: int = 0
    words: int = 0

    avg_words_per_line: float = 0.0
    avg_chars_per_line: float = 0.0
    sentences_per_line: float = 0.0

    multi_sentence_lines: int = 0
    multi_sentence_ratio: float = 0.0  # multi_sentence_lines / lines

    exact_dup_lines: int = 0
    unique_line_ratio: float = 0.0     # unique_lines / lines

    prefix_diversity_3w: float = 0.0   # unique prefixes / lines
    prefix_diversity_5w: float = 0.0

@dataclass
class ValidatorMetrics:
    attempts_used: int = 0
    validation_error: Optional[str] = None
    passed: bool = False
    retryable_error: Optional[bool] = None

@dataclass
class TextQualityMetrics:
    placeholders_found: int = 0
    forbidden_hits: Dict[str, int] = field(default_factory=dict)
    out_of_scope_hits: Dict[str, int] = field(default_factory=dict)
    boilerplate_hits: Dict[str, int] = field(default_factory=dict)

    # simplistic repetition fingerprints (prefix loops)
    repeated_prefix_8w_max: int = 0

@dataclass
class PerformanceMetrics:
    duration_sec: float = 0.0
    tokens_est: int = 0
    tokens_per_sec: float = 0.0
    chars_per_sec: float = 0.0

@dataclass
class SectionMetrics:
    section_id: str
    section_no: Optional[int] = None
    retrieval: Optional[RetrievalMetrics] = None
    generation: Optional[GenerationMetrics] = None
    validator: Optional[ValidatorMetrics] = None
    text_quality: Optional[TextQualityMetrics] = None
    performance: Optional[PerformanceMetrics] = None
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RunMetrics:
    run_id: str
    started_at: float
    finished_at: float = 0.0
    total_duration_sec: float = 0.0
    sections: List[SectionMetrics] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Default rules for text quality (tune later)
# ============================================================

DEFAULT_FORBIDDEN = {
    # cross-section / generally forbidden in Payment Terms, etc.
    "governing_law": r"\b(governing\s+law|applicable\s+law|применим(ое|ого)\s+прав(о|а))\b",
    "jurisdiction": r"\b(jurisdiction|arbitration|арбитраж|подсудност|юрисдикц)\b",
    "force_majeure": r"\b(force\s+majeure|форс[- ]?мажор|непреодолим(ая|ой)\s+сил(а|ы))\b",
    "confidentiality": r"\b(confidential|конфиденциал|коммерческ(ая|ой)\s+тайн)\b",
    "termination": r"\b(termination|расторжен|прекращен|срок\s+действия)\b",
}

DEFAULT_BOILERPLATE = {
    "in_accordance_law_ru": r"\bв\s+соответствии\s+с\s+действующ\w*\s+законодательств\w*\b",
    "negotiate_ru": r"\bвести\s+переговор\w*\b",
    "damages_ru": r"\bвозмещени\w*\s+убытк\w*\b",
}

# Optional: per-section out-of-scope patterns can be passed in config
DEFAULT_OUT_OF_SCOPE = {}


# ============================================================
# Core computations
# ============================================================

def compute_retrieval_metrics(
    results: Sequence[Dict[str, Any]],
    *,
    k: int,
    relevant_ids: Optional[Sequence[str]] = None,
    id_key_candidates: Tuple[str, ...] = ("doc_id", "id", "source_id", "path"),
    score_key_candidates: Tuple[str, ...] = ("score", "bm25", "rank_score"),
) -> RetrievalMetrics:
    """
    results: list of dicts (top-k), each ideally has doc_id/path and score.
    relevant_ids: optional ground truth list (for offline eval).
    """
    top = list(results[:k])
    met = RetrievalMetrics(k=len(top))

    # doc ids
    doc_ids = []
    for r in top:
        did = None
        for key in id_key_candidates:
            if key in r and r[key]:
                did = str(r[key])
                break
        doc_ids.append(did or "")

    unique_docs = len(set([d for d in doc_ids if d]))
    met.unique_docs = unique_docs
    met.unique_ratio = _safe_div(unique_docs, max(1, len(top)))

    # scores
    scores = []
    for r in top:
        s = None
        for key in score_key_candidates:
            if key in r and r[key] is not None:
                try:
                    s = float(r[key])
                except Exception:
                    s = None
                break
        if s is not None:
            scores.append(s)

    if scores:
        met.score_min = min(scores)
        met.score_max = max(scores)
        met.score_mean = _avg(scores)
        met.score_stdev = _stdev(scores)
        if len(scores) >= 2:
            met.score_gap_1_2 = scores[0] - scores[1]

    # recall/mrr if ground truth
    if relevant_ids:
        rel = set(str(x) for x in relevant_ids)
        ranks = []
        hits = 0
        for i, did in enumerate(doc_ids, start=1):
            if did and did in rel:
                hits += 1
                ranks.append(i)
        met.recall_at_k = _safe_div(hits, len(rel)) if rel else 0.0
        met.hit_at_1 = bool(doc_ids and doc_ids[0] in rel)
        met.mrr = (1.0 / min(ranks)) if ranks else 0.0

    return met


def compute_generation_metrics(text: str) -> GenerationMetrics:
    t = text or ""
    lines = _split_lines(t)
    sents = _split_sentences(t)
    words = _WORD_RE.findall(t)

    gm = GenerationMetrics()
    gm.nonempty_lines = len(lines)
    gm.sentences = len(sents)
    gm.chars_no_spaces = len(_strip_spaces(t))
    gm.words = len(words)

    if lines:
        gm.avg_words_per_line = _avg([len(_WORD_RE.findall(ln)) for ln in lines])
        gm.avg_chars_per_line = _avg([len(_strip_spaces(ln)) for ln in lines])

        # multi-sentence lines
        multi = sum(1 for ln in lines if _MULTI_SENTENCE_IN_LINE_RE.search(ln))
        gm.multi_sentence_lines = multi
        gm.multi_sentence_ratio = _safe_div(multi, len(lines))

        # exact duplicates
        norm_lines = [re.sub(r"\s+", " ", ln).strip().lower() for ln in lines]
        unique_lines = len(set(norm_lines))
        gm.exact_dup_lines = len(lines) - unique_lines
        gm.unique_line_ratio = _safe_div(unique_lines, len(lines))

        # prefix diversity (3w/5w)
        def pref(n: int) -> str:
            return ""

        p3 = []
        p5 = []
        for ln in lines:
            ws = [w.lower() for w in _WORD_RE.findall(ln)]
            p3.append(" ".join(ws[:3]) if ws else "")
            p5.append(" ".join(ws[:5]) if ws else "")
        gm.prefix_diversity_3w = _safe_div(len(set([x for x in p3 if x])), len(lines))
        gm.prefix_diversity_5w = _safe_div(len(set([x for x in p5 if x])), len(lines))

        # sentences per line (rough)
        gm.sentences_per_line = _safe_div(len(sents), len(lines))

    return gm


def compute_text_quality_metrics(
    text: str,
    *,
    forbidden_patterns: Optional[Dict[str, str]] = None,
    out_of_scope_patterns: Optional[Dict[str, str]] = None,
    boilerplate_patterns: Optional[Dict[str, str]] = None,
) -> TextQualityMetrics:
    t = text or ""
    low = t.lower()

    forbidden_patterns = forbidden_patterns or DEFAULT_FORBIDDEN
    out_of_scope_patterns = out_of_scope_patterns or DEFAULT_OUT_OF_SCOPE
    boilerplate_patterns = boilerplate_patterns or DEFAULT_BOILERPLATE

    tq = TextQualityMetrics()
    tq.placeholders_found = len(_PLACEHOLDER_RE.findall(t))

    def _count_hits(patterns: Dict[str, str]) -> Dict[str, int]:
        hits: Dict[str, int] = {}
        for name, pat in patterns.items():
            try:
                c = len(re.findall(pat, low, flags=re.IGNORECASE))
            except re.error:
                c = 0
            if c:
                hits[name] = c
        return hits

    tq.forbidden_hits = _count_hits(forbidden_patterns)
    tq.out_of_scope_hits = _count_hits(out_of_scope_patterns)
    tq.boilerplate_hits = _count_hits(boilerplate_patterns)

    # repetition prefix fingerprint (8 words)
    lines = _split_lines(t)
    fp_counts: Dict[str, int] = {}
    for ln in lines:
        ln_low = re.sub(r"[^a-zа-я0-9\s]", " ", ln.lower())
        ws = [w for w in ln_low.split() if w]
        fp = " ".join(ws[:8])
        if fp:
            fp_counts[fp] = fp_counts.get(fp, 0) + 1
    tq.repeated_prefix_8w_max = max(fp_counts.values()) if fp_counts else 0

    return tq


def compute_performance_metrics(
    *,
    duration_sec: float,
    text: str,
) -> PerformanceMetrics:
    pm = PerformanceMetrics()
    pm.duration_sec = max(0.0, float(duration_sec))
    pm.tokens_est = _token_estimate(text or "")
    pm.tokens_per_sec = _safe_div(pm.tokens_est, pm.duration_sec)
    pm.chars_per_sec = _safe_div(len(text or ""), pm.duration_sec)
    return pm


def compute_validator_metrics(*, attempts_used: int, err: Optional[str]) -> ValidatorMetrics:
    vm = ValidatorMetrics()
    vm.attempts_used = int(attempts_used or 0)
    vm.validation_error = err
    vm.passed = (err is None)
    # naive retryable class
    if err is None:
        vm.retryable_error = None
    else:
        vm.retryable_error = err in {"too_short", "too_few_list_items", "repetition_detected", "merged_sentences_detected"}
    return vm


# ============================================================
# Collector (optional, удобная интеграция в run_generate.py)
# ============================================================

class MetricsCollector:
    """
    Простая "шина" метрик: ты зовёшь start_section/end_section, а потом dump_json().

    Не требует вмешиваться в бизнес-логику.
    """
    def __init__(self, *, run_id: str):
        self.run = RunMetrics(run_id=run_id, started_at=_now())
        self._section_started_at: Dict[str, float] = {}

    def start_section(self, section_id: str) -> None:
        self._section_started_at[section_id] = _now()

    def end_section(
        self,
        *,
        section_id: str,
        section_no: Optional[int],
        generated_text: str,
        attempts_used: int,
        validation_err: Optional[str],
        retrieval_results: Optional[Sequence[Dict[str, Any]]] = None,
        retrieval_k: int = 0,
        retrieval_relevant_ids: Optional[Sequence[str]] = None,
        forbidden_patterns: Optional[Dict[str, str]] = None,
        out_of_scope_patterns: Optional[Dict[str, str]] = None,
        boilerplate_patterns: Optional[Dict[str, str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> SectionMetrics:
        started = self._section_started_at.get(section_id, None)
        duration = (_now() - started) if started is not None else 0.0

        sm = SectionMetrics(section_id=section_id, section_no=section_no, extra=extra or {})

        if retrieval_results is not None and retrieval_k:
            sm.retrieval = compute_retrieval_metrics(
                retrieval_results, k=retrieval_k, relevant_ids=retrieval_relevant_ids
            )

        sm.generation = compute_generation_metrics(generated_text)
        sm.validator = compute_validator_metrics(attempts_used=attempts_used, err=validation_err)
        sm.text_quality = compute_text_quality_metrics(
            generated_text,
            forbidden_patterns=forbidden_patterns,
            out_of_scope_patterns=out_of_scope_patterns,
            boilerplate_patterns=boilerplate_patterns,
        )
        sm.performance = compute_performance_metrics(duration_sec=duration, text=generated_text)

        self.run.sections.append(sm)
        return sm

    def finish(self, *, extra: Optional[Dict[str, Any]] = None) -> None:
        self.run.finished_at = _now()
        self.run.total_duration_sec = self.run.finished_at - self.run.started_at
        if extra:
            self.run.extra.update(extra)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self.run)

    def dump_json(self, path: str, *, indent: int = 2) -> None:
        self.finish()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=indent)


# ============================================================
# Convenience: one-shot section metrics (без collector)
# ============================================================

def compute_section_metrics(
    *,
    section_id: str,
    section_no: Optional[int],
    text: str,
    duration_sec: float,
    attempts_used: int,
    validation_err: Optional[str],
    retrieval_results: Optional[Sequence[Dict[str, Any]]] = None,
    retrieval_k: int = 0,
    retrieval_relevant_ids: Optional[Sequence[str]] = None,
    forbidden_patterns: Optional[Dict[str, str]] = None,
    out_of_scope_patterns: Optional[Dict[str, str]] = None,
    boilerplate_patterns: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> SectionMetrics:
    sm = SectionMetrics(section_id=section_id, section_no=section_no, extra=extra or {})
    if retrieval_results is not None and retrieval_k:
        sm.retrieval = compute_retrieval_metrics(
            retrieval_results, k=retrieval_k, relevant_ids=retrieval_relevant_ids
        )
    sm.generation = compute_generation_metrics(text)
    sm.validator = compute_validator_metrics(attempts_used=attempts_used, err=validation_err)
    sm.text_quality = compute_text_quality_metrics(
        text,
        forbidden_patterns=forbidden_patterns,
        out_of_scope_patterns=out_of_scope_patterns,
        boilerplate_patterns=boilerplate_patterns,
    )
    sm.performance = compute_performance_metrics(duration_sec=duration_sec, text=text)
    return sm
