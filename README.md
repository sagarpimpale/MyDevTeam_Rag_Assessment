# DocChat — RAG Document Assistant

A document-based chat system built with FastAPI, LangChain, and ChromaDB. Upload a PDF or TXT file and ask questions about it using Ollama (local) or Gemini (Google) as the LLM provider.

---

## Architecture

```
User
 │
 ▼
Frontend (HTML/CSS/JS)
 │  ├── POST /upload   → parse → chunk → embed (Ollama) → ChromaDB
 │  ├── POST /chat     → embed question → retrieve chunks → LLM → answer + citations
 │  └── GET  /providers → list Ollama models + Gemini
 ▼
FastAPI Backend
 ├── utils.py        — PDF and TXT text extraction
 ├── rag.py          — chunking, embedding, retrieval, answer generation
 ├── providers.py    — Ollama + Gemini LangChain wrappers
 └── vectorstore.py  — ChromaDB in-memory store
```

### RAG Flow

1. **Upload** — File is parsed and raw text is extracted
2. **Chunk** — Text is split into overlapping chunks (800 tokens, 100 overlap) using `RecursiveCharacterTextSplitter`
3. **Embed** — Each chunk is embedded using a local Ollama embedding model (`nomic-embed-text` preferred)
4. **Store** — Embeddings + chunks stored in ChromaDB (in-memory, cosine similarity)
5. **Query** — User's question is embedded, top-4 similar chunks retrieved
6. **Generate** — Retrieved chunks + question sent to selected LLM, answer returned with source citations

---

## Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running locally
- A Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))

### 1. Pull an Ollama model

You need at least one model for chat. For embeddings, `nomic-embed-text` is recommended:

```bash
ollama pull nomic-embed-text   # for embeddings (recommended)
ollama pull llama3.2           # or any chat model you prefer
```

> **Note:** If no dedicated embedding model is found, the system falls back to using the first available Ollama model for embeddings.

### 2. Clone and install

```bash
cd rag-chat
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_gemini_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
```

### 4. Run the server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Usage

1. **Upload** a PDF or TXT file using the drop zone or browse button
2. **Select provider** — Ollama (local) or Gemini (Google)
3. If Ollama is selected, **choose a model** from the dropdown (auto-populated from your local Ollama)
4. **Ask questions** about your document
5. Answers include **source citations** — click any citation card to expand the full chunk text

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/providers` | GET | Returns available providers and Ollama models |
| `/upload` | POST | Upload and ingest a PDF or TXT file |
| `/chat` | POST | Ask a question, get an answer with citations |
| `/status` | GET | Check if a document is currently loaded |

### POST /chat

```json
{
  "question": "What is the main topic of this document?",
  "provider": "ollama",
  "model": "llama3.2"
}
```

Response:
```json
{
  "answer": "The document discusses...",
  "citations": [
    {
      "chunk_index": 3,
      "text": "...relevant chunk text...",
      "filename": "document.pdf"
    }
  ],
  "document": "document.pdf"
}
```

---

## Project Structure

```
rag-chat/
├── backend/
│   ├── main.py          # FastAPI app and all routes
│   ├── rag.py           # Core RAG logic
│   ├── providers.py     # Ollama + Gemini LangChain setup
│   ├── vectorstore.py   # ChromaDB operations
│   └── utils.py         # PDF + TXT parsing
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .env.example
├── requirements.txt
└── README.md
```

---

## LLM Providers

| Provider | Type | Model | Notes |
|----------|------|-------|-------|
| Ollama | Local | Any pulled model | Fully offline, model list auto-detected |
| Gemini | Cloud | gemini-1.5-flash | Requires API key, free tier available |

**Embeddings** always use Ollama locally (prefers `nomic-embed-text`, falls back to any available model).

---

## Notes

- Only one document is active at a time — uploading a new file replaces the previous one
- ChromaDB runs in-memory; data is lost when the server restarts
- File size limit: 20MB
- Supported formats: `.pdf`, `.txt`
- Scanned/image-based PDFs are not supported (no OCR)
