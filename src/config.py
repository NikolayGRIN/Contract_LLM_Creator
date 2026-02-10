from __future__ import annotations
from pathlib import Path
import os

# Один и тот же код должен работать и локально, и в Colab.
# backend по умолчанию "local".
LLM_BACKEND = os.getenv("LLM_BACKEND", "local")  # "local" | "colab"

# Локальный путь к GGUF (можно относительный от корня репо)
LOCAL_GGUF_MODEL_PATH = os.getenv(
    "LOCAL_GGUF_MODEL_PATH",
    str(Path("models") / "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"),
)

LOCAL_GGUF_EMBED_MODEL_PATH = os.getenv(
    "LOCAL_GGUF_EMBED_MODEL_PATH",
    str(Path("models") / "bge-m3-q4_k_m.gguf"),
)

# ----------------------------
# llama-cpp generation params
# ----------------------------

# Context / compute
N_CTX = int(os.getenv("N_CTX", "8192"))
N_THREADS = int(os.getenv("N_THREADS", "8"))
N_GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "0"))

# Sampling (base)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.4"))
TOP_P = float(os.getenv("TOP_P", "0.92"))
TOP_K = int(os.getenv("TOP_K", "40"))
TYPICAL_P = float(os.getenv("TYPICAL_P", "1.0"))

# Anti-repetition penalties (base)
REPEAT_PENALTY = float(os.getenv("REPEAT_PENALTY", "1.1"))
PRESENCE_PENALTY = float(os.getenv("PRESENCE_PENALTY", "0.1"))
FREQUENCY_PENALTY = float(os.getenv("FREQUENCY_PENALTY", "0.1"))

# Output length
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1100"))

# Retry behavior
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
RETRY_TEMPERATURE = float(os.getenv("RETRY_TEMPERATURE", "0.45"))
RETRY_TOP_P = float(os.getenv("RETRY_TOP_P", "0.94"))
RETRY_TOP_K = int(os.getenv("RETRY_TOP_K", "45"))
RETRY_TYPICAL_P = float(os.getenv("RETRY_TYPICAL_P", "1.0"))

RETRY_REPEAT_PENALTY = float(os.getenv("RETRY_REPEAT_PENALTY", "1.12"))
RETRY_PRESENCE_PENALTY = float(os.getenv("RETRY_PRESENCE_PENALTY", "0.1"))
RETRY_FREQUENCY_PENALTY = float(os.getenv("RETRY_FREQUENCY_PENALTY", "0.1"))