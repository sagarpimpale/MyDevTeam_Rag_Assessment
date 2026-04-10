import uuid
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import HumanMessage, SystemMessage

from vectorstore import clear_collection, store_chunks, query_chunks
from providers import get_ollama_embeddings, get_llm

# ── Chunking ──────────────────────────────────────────────────────────────────

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text(text: str) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    raw_chunks = splitter.split_text(text)
    return [
        {
            "text": chunk,
            "chunk_index": i,
        }
        for i, chunk in enumerate(raw_chunks)
    ]


# ── Ingestion ─────────────────────────────────────────────────────────────────

def ingest_document(text: str, filename: str) -> int:
    """Chunk, embed, and store a document. Returns number of chunks stored."""
    clear_collection()

    chunks = chunk_text(text)
    embedder = get_ollama_embeddings()

    texts = [c["text"] for c in chunks]
    embeddings = embedder.embed_documents(texts)

    records = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        records.append(
            {
                "id": str(uuid.uuid4()),
                "text": chunk["text"],
                "embedding": embedding,
                "metadata": {
                    "filename": filename,
                    "chunk_index": chunk["chunk_index"],
                },
            }
        )

    store_chunks(records)
    return len(records)


# ── Retrieval + Generation ────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful assistant that answers questions strictly based on the provided document context.
- Answer using only the information present in the context below.
- If the answer is not in the context, say so clearly.
- Be concise and factual. Do not make up information.
- Format your response using markdown: use numbered lists, bullet points, and bold headings where appropriate.
- For multi-part answers, use clear sections with headings.
- Never write your answer as a single wall of text."""


def build_prompt(question: str, context_chunks: list[dict]) -> str:
    context_text = "\n\n---\n\n".join(
        f"[Chunk {i+1}]: {c['text']}" for i, c in enumerate(context_chunks)
    )
    return f"""Context from the document:

{context_text}

---

Question: {question}

Answer based on the context above:"""


def answer_question(
    question: str,
    provider: str,
    model: str | None = None,
    n_chunks: int = 4,
) -> dict:
    """
    Returns:
        {
            "answer": str,
            "citations": [{"chunk_index": int, "text": str, "filename": str}]
        }
    """
    # Embed the question
    embedder = get_ollama_embeddings()
    question_embedding = embedder.embed_query(question)

    # Retrieve relevant chunks
    retrieved = query_chunks(question_embedding, n_results=n_chunks)

    if not retrieved:
        return {
            "answer": "No document has been uploaded yet. Please upload a document first.",
            "citations": [],
        }

    # Build prompt
    prompt = build_prompt(question, retrieved)

    # Get LLM and generate answer
    llm = get_llm(provider, model)

    if provider == "gemini":
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        response = llm.invoke(messages)
        answer = response.content
    else:
        # Ollama via OllamaLLM (string in, string out)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        answer = llm.invoke(full_prompt)

    # Format citations
    citations = [
        {
            "chunk_index": c["metadata"].get("chunk_index", i),
            "text": c["text"],
            "filename": c["metadata"].get("filename", "document"),
        }
        for i, c in enumerate(retrieved)
    ]

    return {"answer": answer, "citations": citations}