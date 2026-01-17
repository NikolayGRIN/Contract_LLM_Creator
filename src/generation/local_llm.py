from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import re
from collections import Counter

from llama_cpp import Llama


@dataclass
class LLMConfig:
    model_path: Path
    n_ctx: int = 4096
    n_threads: int = 8
    n_gpu_layers: int = 0  # CPU
    temperature: float = 0.25
    top_p: float = 0.9
    max_tokens: int = 1200

    # ✅ универсальный retry
    max_retries: int = 2
    retry_temperature: float = 0.35
    retry_top_p: float = 0.92


_PLACEHOLDER_RE = re.compile(r"\[[A-Z_]+\]")

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SPACE_RE = re.compile(r"\s+")

# Нумерованные подпункты вида "1) ...", "2) ..." и т.п.
_LIST_ITEM_RE = re.compile(r"(?m)^\s*\d{1,3}\)\s+")


def _norm_sentence(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("ё", "е")
    s = _SPACE_RE.sub(" ", s)
    s = re.sub(r"[«»\"()]", "", s)
    s = re.sub(r"[,:;]+", ",", s)
    return s


def _len_no_spaces(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _split_units_for_repetition(text: str) -> List[str]:
    """
    Возвращает "юниты" для анализа повторов
    """
    t = (text or "").strip()
    if not t:
        return []

    if _LIST_ITEM_RE.search(t):
        # Разбиваем по началу каждого подпункта, сохраняя текст подпункта целиком
        parts = re.split(r"(?m)^\s*(?=\d{1,3}\)\s+)", t)
        parts = [p.strip() for p in parts if p.strip()]
        return parts
    
    sents = [s.strip() for s in _SENT_SPLIT_RE.split(t) if s.strip()]
    return sents


def detect_repetition(text: str, *, min_unit_len: int = 40) -> bool:
    """
    True, если есть повторы "единиц" (подпунктов или предложений) 2+ раза
    после нормализации.
    """
    units = _split_units_for_repetition(text)
    if len(units) < 6:
        return False

    norm = [_norm_sentence(u) for u in units if len(u.strip()) >= min_unit_len]
    if len(norm) < 6:
        return False

    counts = Counter(norm)
    return any(c >= 2 for c in counts.values())


class LocalLLM:
    def __init__(self, cfg: LLMConfig):
        if not cfg.model_path.exists():
            raise FileNotFoundError(f"GGUF model not found: {cfg.model_path}")

        self.cfg = cfg
        self.llm = Llama(
            model_path=str(cfg.model_path),
            n_ctx=cfg.n_ctx,
            n_threads=cfg.n_threads,
            n_gpu_layers=cfg.n_gpu_layers,
            verbose=False,
        )

    def chat(self, system: str, user: str) -> str:
        """
        Универсальный chat (совместим с llama-cpp-python 0.3.16).
        """
        return self._chat_once(
            system=system,
            user=user,
            temperature=self.cfg.temperature,
            top_p=self.cfg.top_p,
        )

    def generate_with_retry(
        self,
        *,
        system: str,
        user: str,
        validator: Optional[Callable[[str], Optional[str]]] = None,
        retry_instruction: str = "",
        save_bad_path: Optional[Path] = None,
    ) -> tuple[str, Optional[str], int]:
        """
        Универсальная генерация с валидацией и ретраями.

        Returns: (text, err_code, attempts_used)
          - err_code == None => успех
        """
        attempt = 0
        last_text = ""
        last_err: Optional[str] = None

        while attempt <= self.cfg.max_retries:
            if attempt == 0:
                prompt = user
                temperature = self.cfg.temperature
                top_p = self.cfg.top_p
            else:
                prompt = user
                if retry_instruction:
                    prompt += "\n\n" + retry_instruction.strip() + "\n"
                temperature = self.cfg.retry_temperature
                top_p = self.cfg.retry_top_p

            text = self._chat_once(
                system=system,
                user=prompt,
                temperature=temperature,
                top_p=top_p,
            )

            last_text = text

            if validator is None:
                return text, None, attempt + 1

            err = validator(text)
            retryable = {"too_short", "repetition_detected"}
            if err is None:
                return text, None, attempt + 1

            if err not in retryable:
                # не ретраим “логические” ошибки, чтобы не тратить 5–10 минут
                if save_bad_path is not None:
                    save_bad_path.parent.mkdir(parents=True, exist_ok=True)
                    save_bad_path.write_text(text, encoding="utf-8")
                return text, err, attempt + 1

            attempt += 1

        if save_bad_path is not None:
            save_bad_path.parent.mkdir(parents=True, exist_ok=True)
            save_bad_path.write_text(last_text, encoding="utf-8")

        return last_text, last_err, attempt

    def _chat_once(self, *, system: str, user: str, temperature: float, top_p: float) -> str:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        res: Dict[str, Any] = self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=self.cfg.max_tokens,
        )
        return (res["choices"][0]["message"]["content"] or "").strip()



#  Валидатор: Payment Terms

def payment_terms_validator(
    *,
    bank_details_included: bool,
    late_payment_penalty_enabled: bool,
    min_chars_no_spaces: int = 750,   # считаем без пробелов
) -> Callable[[str], Optional[str]]:
    
    def _validate(text: str) -> Optional[str]:
        if not text:
            return "too_short"

        #  длина без пробелов (как в требованиях)
        if _len_no_spaces(text) < min_chars_no_spaces:
            return "too_short"

        #  ожидаем нумерованный список 20+ подпунктов 
        items = re.findall(r"(?m)^\s*\d{1,3}\)\s+", text)
        if len(items) < 20:
            return "too_few_list_items"

        # Нельзя оставлять плейсхолдеры из cleaner/precedents
        if _PLACEHOLDER_RE.search(text):
            return "contains_placeholders"

        low = text.lower()

        # Термины сторон должны быть единообразны (без Покупатель+Заказчик и т.п.)
        has_buyer = "покупател" in low
        has_supplier = "поставщик" in low
        has_customer = "заказчик" in low
        has_contractor = "исполнител" in low
        has_seller = "продавец" in low
        if (has_buyer and has_customer) or (has_supplier and has_contractor) or (has_buyer and has_seller):
            return "mixed_party_terms"

        #  1) Повторы (предложения/подпункты)
        if detect_repetition(text):
            return "repetition_detected"

        #  1b) Запрет boilerplate и ухода в другие секции (споры/убытки/переговоры и т.п.)
        boilerplate_patterns = [
            r"\bв\s+соответствии\s+с\s+действующ\w*\s+законодательств\w*\b",
            r"\bсторон[аы]\s+обяз(уется|уются)\b.*\bсоблюдат\w*\b",
            r"\bвправе\s+требоват\w*\b",
            r"\bвозможн(ые|ых)\s+последств(ия|ий)\b",
            r"\bв\s+случае\s+неисполнени\w*\b.*\bубытк\w*\b",
            r"\bвозмещени\w*\s+убытк\w*\b",
            r"\bв\s+случае\s+возникновени\w*\s+спор\w*\b",
            r"\bвести\s+переговор\w*\b",
        ]
        if any(re.search(p, low) for p in boilerplate_patterns):
            return "contains_boilerplate"

        # 2) Запрещённые "вне scope" темы для Payment Terms
        # Запрещаем НЕ отдельные слова ("уведомление", "претензия"), а устойчивые маркеры других секций (право/подсудность/форс-мажор).
        out_of_scope_patterns = [
            
            r"\bприменим(ое|ого)\s+прав(о|а)\b",
            r"\bподсудност[ьи]\b",
            r"\bюрисдикц(ия|ии)\b",
            r"\bарбитражн(ый|ого)\s+суд\b",
            r"\bтретейск(ий|ого)\s+суд\b",
            r"\bсудебн(ый|ого)\s+поряд(ок|ке)\b",
            r"\bмест[оа]\s+рассмотрени[яе]\s+спор(ов|а)\b",

          
            r"\bфорс[- ]?мажор\b",
            r"\bнепреодолим(ая|ой)\s+сил(а|ы)\b",

        
            r"\bконфиденциал(ьн|)\w*\b",
            r"\bкоммерческ(ая|ой)\s+тайн(а|ы)\b",

   
            r"\bрасторжен(ие|ия)\b",
            r"\bсрок\s+действия\b",
            r"\bпрекращен(ие|ия)\b",

         
            r"\bраздел\s+уведомлени(я|й)\b",
            r"\bнастоящ(ие|ий)\s+уведомлени(я|е)\s+направля(ется|ются)\s+по\s+адрес(у|ам)\b",
        ]
        if any(re.search(p, low) for p in out_of_scope_patterns):
            return "contains_out_of_scope_topics"

        #  3) Неустойка/штрафы только если включены флагом формы
        if not late_payment_penalty_enabled:
            if any(x in low for x in ["пеня", "неустойк", "штраф", "санкц"]):
                return "contains_penalty"

        #  4) Банковские реквизиты (если не включены — запрещаем явные реквизиты/маркеры)
        if not bank_details_included:
            forbidden = [
                "банковские реквизиты",
                "р/с", "к/с", "корр", "корр.счет", "корреспондентск",
                "бик", "iban", "swift", "bic",
                "account no", "account number", "bank code", "routing number",
                # важно: не допускаем “сообщать об изменениях реквизитов”
                "банковских реквизит",
            ]
            if any(x in low for x in forbidden):
                return "contains_bank_details"

            # Дополнительно: длинные числа похожи на номера счетов / IBAN
            if re.search(r"\d{12,}", low):
                return "contains_bank_details"

        # ✅ 5) Логическая проверка "дата оплаты":
        # не допускаем одновременно "списание" и "зачисление" как две разные дефиниции
        has_debit = any(x in low for x in ["дата списан", "днем списан", "днём списан", "момент списан"])
        has_credit = any(x in low for x in ["дата зачисл", "днем зачисл", "днём зачисл", "момент зачисл"])
        if has_debit and has_credit:
            return "conflicting_payment_date_definition"

        return None

    return _validate
