from __future__ import annotations

from typing import Optional
import importlib
import os


def is_llama_cpp_available() -> bool:
    try:
        importlib.import_module("llama_cpp")
        return True
    except Exception:
        return False


def make_llm(*, root: str):
    """
    Универсальная фабрика LLM.
    Работает:
    - в Google Colab (llama_cpp установлен)
    - локально (если llama_cpp установлен)
    - корректно падает с понятной ошибкой, если нет
    """

    if is_llama_cpp_available():
        from src.generation.local_llm import LocalLLM, LLMConfig

        model_path = os.getenv(
            "LLM_MODEL_PATH",
            os.path.join(root, "models", "llama.gguf"),
        )

        return LocalLLM(
            LLMConfig(
                model_path=model_path,
                n_ctx=4096,
                temperature=0.2,
                top_p=0.9,
                repeat_penalty=1.1,
            )
        )

    raise RuntimeError(
        "LLM backend недоступен: модуль llama_cpp не найден.\n"
        "Установи llama-cpp-python или запусти код в Google Colab."
    )
