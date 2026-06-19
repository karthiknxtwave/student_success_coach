import streamlit as st
import chromadb
from openai import OpenAI

# ---------------------------------------------------------------------------
# CONFIG — edit these to change collection name or result count
# ---------------------------------------------------------------------------
COLLECTION_NAME = "setup_guide"
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TOP_K = 4
# ---------------------------------------------------------------------------


def _get_client() -> chromadb.HttpClient:
    """Return a ChromaDB cloud client using credentials from st.secrets."""
    return chromadb.HttpClient(
        ssl=True,
        host="api.trychroma.com",
        tenant=st.secrets["chroma"]["CHROMA_TENANT"],
        database=st.secrets["chroma"]["CHROMA_DATABASE"],
        headers={"x-chroma-token": st.secrets["chroma"]["CHROMA_API_KEY"]},
    )


def _get_collection() -> chromadb.Collection:
    """Return the collection, creating it if it doesn't exist yet."""
    client = _get_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)


def _embed(text: str) -> list[float]:
    """Embed a single string using OpenAI text-embedding-3-small."""
    openai_client = OpenAI(api_key=st.secrets["app"]["OPENAI_API_KEY"])
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> str | None:
    """
    Embed the query and return the top_k most relevant chunks as a
    single joined string, or None if the collection is empty.
    """
    collection = _get_collection()

    if collection.count() == 0:
        return None

    query_embedding = _embed(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents"],
    )

    chunks = results["documents"][0]
    return "\n\n---\n\n".join(chunks) if chunks else None