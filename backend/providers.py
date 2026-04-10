import os
import httpx
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Models that are embedding-only and CANNOT do chat generation
EMBED_ONLY_KEYWORDS = ["nomic-embed-text", "mxbai-embed-large", "all-minilm"]


# ── Ollama ────────────────────────────────────────────────────────────────────

def get_ollama_models() -> list[str]:
    """Return ALL pulled Ollama models."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns {"models": [...]} where each item has a "name" field
        models = data.get("models", [])
        names = [m["name"] for m in models if "name" in m]
        return names
    except Exception as e:
        print(f"[providers] Failed to reach Ollama at {OLLAMA_BASE_URL}: {e}")
        return []


def get_chat_ollama_models() -> list[str]:
    """Return models capable of chat (filters out embedding-only models)."""
    all_models = get_ollama_models()
    chat_models = [
        m for m in all_models
        if not any(kw in m.lower() for kw in EMBED_ONLY_KEYWORDS)
    ]
    # If filtering removed everything (e.g. user only has embed models),
    # return all models so the UI isn't empty
    return chat_models if chat_models else all_models


def get_embed_ollama_model() -> str:
    """Return the best available embedding model name."""
    all_models = get_ollama_models()
    if not all_models:
        raise RuntimeError(
            "No Ollama models found. Run: ollama pull nomic-embed-text"
        )
    # Prefer dedicated embedding models
    for kw in EMBED_ONLY_KEYWORDS:
        match = next((m for m in all_models if kw in m.lower()), None)
        if match:
            return match
    # Fall back to first available (chat models support embeddings too)
    return all_models[0]


def get_ollama_llm(model: str) -> OllamaLLM:
    return OllamaLLM(model=model, base_url=OLLAMA_BASE_URL)


def get_ollama_embeddings() -> OllamaEmbeddings:
    model = get_embed_ollama_model()
    print(f"[providers] Using embedding model: {model}")
    return OllamaEmbeddings(model=model, base_url=OLLAMA_BASE_URL)


# ── Gemini ────────────────────────────────────────────────────────────────────

def get_gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def get_gemini_llm() -> ChatGoogleGenerativeAI:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return ChatGoogleGenerativeAI(
        model=get_gemini_model_name(),
        google_api_key=GEMINI_API_KEY,
        temperature=0.3,
    )


# ── Provider factory ──────────────────────────────────────────────────────────

def get_llm(provider: str, model: str | None = None):
    if provider == "ollama":
        if not model:
            raise ValueError("Model name required for Ollama")
        return get_ollama_llm(model)
    elif provider == "gemini":
        return get_gemini_llm()
    else:
        raise ValueError(f"Unknown provider: {provider}")