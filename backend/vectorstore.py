import chromadb
from chromadb.config import Settings

# In-memory ChromaDB client — resets on server restart
_client = chromadb.Client(Settings(anonymized_telemetry=False))
COLLECTION_NAME = "rag_documents"


def get_collection():
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def clear_collection():
    try:
        _client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass


def store_chunks(chunks: list[dict]):
    """
    chunks: list of {"id": str, "text": str, "embedding": list[float], "metadata": dict}
    """
    collection = get_collection()
    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=[c["embedding"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )


def query_chunks(embedding: list[float], n_results: int = 4) -> list[dict]:
    collection = get_collection()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append(
            {
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
        )
    return chunks
