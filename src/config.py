from __future__ import annotations
from pathlib import Path
import os

# Один и тот же код должен работать и локально, и в Colab.
# backend по умолчанию "local".
LLM_BACKEND = os.getenv("LLM_BACKEND", "local")  # "local" | "colab"

# Локальный путь к GGUF 
LOCAL_GGUF_MODEL_PATH = os.getenv(
    "LOCAL_GGUF_MODEL_PATH",
    str(Path("models") / "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"),
)
