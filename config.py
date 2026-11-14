"""Constants for paths, model, prices and limits. Secrets come from .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "drills.db"
DB_URL = f"sqlite:///{DB_PATH}"

PROVIDER = "anthropic"  # "anthropic" | "openai" | "local"
MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-5"}
# (input, output) USD per million tokens
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (3.0, 15.0),
    "gpt-5": (1.25, 10.0),
}

MAX_HINTS = 3
MIN_ANSWER_CHARS = 15
DESIRED_RETENTION = 0.9

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Any OpenAI-compatible server (LM Studio, Ollama, vLLM, llama.cpp ...). Set these in .env.
LOCAL_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL")  # e.g. http://localhost:1234/v1
LOCAL_MODEL = os.getenv("LOCAL_LLM_MODEL")
LOCAL_API_KEY = os.getenv("LOCAL_LLM_API_KEY") or "not-needed"
