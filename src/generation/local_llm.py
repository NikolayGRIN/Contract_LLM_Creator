# src/generation/local_llm.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import time
from llama_cpp import Llama


@dataclass
class LLMConfig:
    model_path: Path

    # context
    n_ctx: int = 8192
    n_threads: int = 4
    n_gpu_layers: int = 0

    # sampling (base)
    temperature: float = 0.35
    top_p: float = 0.92
    top_k: int = 40    
    typical_p: float = 1.0

    # anti-repetition / anti-brevity-ish
    repeat_penalty: float = 1.05
    presence_penalty: float = 0.10
    frequency_penalty: float = 0.10

    max_tokens: int = 1200

    # retry
    max_retries: int = 2
    retry_temperature: float = 0.45
    retry_top_p: float = 0.95
    retry_top_k: int = 40    
    retry_typical_p: float = 1.0

    retry_repeat_penalty: float = 1.1
    retry_presence_penalty: float = 0.1
    retry_frequency_penalty: float = 0.1


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
        return self._chat_once(
            system=system,
            user=user,
            temperature=self.cfg.temperature,
            top_p=self.cfg.top_p,
            top_k=self.cfg.top_k,          
            typical_p=self.cfg.typical_p,
            repeat_penalty=self.cfg.repeat_penalty,
            presence_penalty=self.cfg.presence_penalty,
            frequency_penalty=self.cfg.frequency_penalty,
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
        attempt = 0
        last_text = ""
        last_err: Optional[str] = None

        while attempt <= self.cfg.max_retries:
            if attempt == 0:
                prompt = user
                temperature = self.cfg.temperature
                top_p = self.cfg.top_p
                top_k = self.cfg.top_k             
                typical_p = self.cfg.typical_p
                repeat_penalty = self.cfg.repeat_penalty
                presence_penalty = self.cfg.presence_penalty
                frequency_penalty = self.cfg.frequency_penalty
            else:
                prompt = user
                if retry_instruction:
                    prompt += "\n\n" + retry_instruction.strip()

                prev = last_text
                if len(prev) > 2000:
                    prev = prev[-2000:]
                prompt += "\n\n=== PREVIOUS DRAFT (LAST 2000 CHARS) ===\n" + prev + "\n"

                temperature = self.cfg.retry_temperature
                top_p = self.cfg.retry_top_p
                top_k = self.cfg.retry_top_k               
                typical_p = self.cfg.retry_typical_p
                repeat_penalty = self.cfg.retry_repeat_penalty
                presence_penalty = self.cfg.retry_presence_penalty
                frequency_penalty = self.cfg.retry_frequency_penalty

            text = self._chat_once(
                system=system,
                user=prompt,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,               
                typical_p=typical_p,
                repeat_penalty=repeat_penalty,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
            )
            last_text = text

            if validator is None:
                return text, None, attempt + 1

            err = validator(text)

            if err is not None and save_bad_path is not None:
                save_bad_path.parent.mkdir(parents=True, exist_ok=True)
                save_bad_path.write_text(
                    f"ATTEMPT: {attempt+1}/{self.cfg.max_retries+1}\nERROR: {err}\n\n{text}",
                    encoding="utf-8",
                )

            retryable = {"too_short", "too_few_list_items", "repetition_detected"}
            is_consistency = isinstance(err, str) and err.startswith("Consistency:")

            if err is None:
                return text, None, attempt + 1

            if (err not in retryable) and (not is_consistency):
                return text, err, attempt + 1

            last_err = err
            attempt += 1

        return last_text, last_err, attempt

    def _chat_once(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        top_p: float,
        top_k: int,      
        typical_p: float,
        repeat_penalty: float,
        presence_penalty: float,
        frequency_penalty: float,
    ) -> str:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        start_time = time.perf_counter()   # 👈 старт

        res: Dict[str, Any] = self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            typical_p=typical_p,
            max_tokens=self.cfg.max_tokens,
            repeat_penalty=repeat_penalty,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            stop=["\n\n\n", "### END", "</s>"]
        )

        elapsed = time.perf_counter() - start_time   # 👈 стоп


        # --- DEBUG TOKENS ---
        usage = res.get("usage") or {}
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        tt = usage.get("total_tokens")

        if pt is not None:
            tps = (ct / elapsed) if elapsed > 0 else 0

            print(
                f"DEBUG tokens: prompt={pt} completion={ct} total={tt} | "
                f"time={elapsed:.2f}s | speed={tps:.1f} tok/s "
                f"(n_ctx={self.cfg.n_ctx}, max_tokens={self.cfg.max_tokens})"
            )

        return (res["choices"][0]["message"]["content"] or "").strip()