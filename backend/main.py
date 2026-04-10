import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from utils import parse_file
from rag import ingest_document, answer_question
from providers import get_chat_ollama_models, get_gemini_model_name, get_ollama_models

app = FastAPI(title="RAG Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_doc_loaded: dict = {"filename": None, "chunks": 0}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/providers")
def get_providers():
    """Return available providers and models."""
    chat_models = get_chat_ollama_models()
    print(f"[main] Ollama chat models found: {chat_models}")
    return {
        "providers": [
            {
                "id": "ollama",
                "name": "Ollama (Local)",
                "models": chat_models,
                "requires_model_selection": True,
            },
            {
                "id": "gemini",
                "name": "Gemini (Google)",
                "models": [get_gemini_model_name()],
                "requires_model_selection": False,
            },
        ]
    }


@app.get("/debug/ollama")
def debug_ollama():
    """Debug endpoint — shows raw Ollama model list."""
    all_models = get_ollama_models()
    chat_models = get_chat_ollama_models()
    return {"all_models": all_models, "chat_models": chat_models}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    allowed_extensions = {"pdf", "txt"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Only PDF and TXT are allowed.",
        )

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max size is 20MB.")

    try:
        text = parse_file(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from the file.",
        )

    try:
        chunk_count = ingest_document(text, file.filename)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {str(e)}")

    _doc_loaded["filename"] = file.filename
    _doc_loaded["chunks"] = chunk_count

    return {
        "message": "Document uploaded and processed successfully.",
        "filename": file.filename,
        "chunks": chunk_count,
    }


class ChatRequest(BaseModel):
    question: str
    provider: str
    model: str | None = None


@app.post("/chat")
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if req.provider not in ("ollama", "gemini"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    if req.provider == "ollama" and not req.model:
        raise HTTPException(status_code=400, detail="Model is required for Ollama.")

    if not _doc_loaded["filename"]:
        raise HTTPException(
            status_code=400, detail="No document uploaded. Please upload a document first."
        )

    try:
        result = answer_question(
            question=req.question,
            provider=req.provider,
            model=req.model,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

    return {
        "answer": result["answer"],
        "citations": result["citations"],
        "document": _doc_loaded["filename"],
    }


@app.get("/status")
def status():
    return {
        "document_loaded": _doc_loaded["filename"] is not None,
        "filename": _doc_loaded["filename"],
        "chunks": _doc_loaded["chunks"],
    }


# ── Serve frontend ────────────────────────────────────────────────────────────

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))