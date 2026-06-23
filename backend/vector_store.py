import os

from dotenv import load_dotenv
from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_classic.storage import LocalFileStore
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers.bm25 import BM25Retriever
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────

EMBEDDING_DIM = 3072  # models/gemini-embedding-001

# ── Singletons ────────────────────────────────────────────────────────────────

base_embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
embedding_file_store = LocalFileStore("./embedding_cache/")
embeddings = CacheBackedEmbeddings.from_bytes_store(
    base_embeddings,
    embedding_file_store,
    namespace="gemini-embedding-001",
    query_embedding_cache=True,
    key_encoder="blake2b",
)

qdrant_client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"],
    timeout=120,
)


# ── Collection ───────────────────────────────────────────────────────────────

def get_collection_name(session_id: str) -> str:
    return f"papeer_{session_id.replace('-', '_')}"


def get_vectorstore(session_id: str) -> QdrantVectorStore:
    collection_name = get_collection_name(session_id)
    if not qdrant_client.collection_exists(collection_name):
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=embeddings,
    )


# ── Public API ───────────────────────────────────────────────────────────────

def add_paper(docs: list[Document], session_id: str) -> None:
    get_vectorstore(session_id).add_documents(docs)


def list_papers(session_id: str) -> list[str]:
    collection_name = get_collection_name(session_id)
    if not qdrant_client.collection_exists(collection_name):
        return []
    seen: set[str] = set()
    titles: list[str] = []
    offset = None
    while True:
        points, offset = qdrant_client.scroll(
            collection_name=collection_name,
            with_payload=True,
            limit=100,
            offset=offset,
        )
        for point in points:
            title = (point.payload or {}).get("metadata", {}).get("title")
            if title and title not in seen:
                seen.add(title)
                titles.append(title)
        if offset is None:
            break
    return titles


def delete_paper(title: str, session_id: str) -> None:
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    collection_name = get_collection_name(session_id)
    if not qdrant_client.collection_exists(collection_name):
        return
    qdrant_client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="metadata.title",
                    match=MatchValue(value=title)
                )
            ]
        )
    )


def delete_session_collection(session_id: str) -> None:
    collection_name = get_collection_name(session_id)
    if qdrant_client.collection_exists(collection_name):
        qdrant_client.delete_collection(collection_name)


def get_all_documents(session_id: str) -> list[Document]:
    collection_name = get_collection_name(session_id)
    if not qdrant_client.collection_exists(collection_name):
        return []
    docs = []
    offset = None
    while True:
        points, offset = qdrant_client.scroll(
            collection_name=collection_name,
            with_payload=True,
            limit=100,
            offset=offset,
        )
        for point in points:
            payload = point.payload or {}
            page_content = payload.get("page_content", "")
            metadata = payload.get("metadata", {})
            docs.append(Document(page_content=page_content, metadata=metadata))
        if offset is None:
            break
    return docs


def get_hybrid_retriever(session_id: str, k: int = 4):
    collection_name = get_collection_name(session_id)
    if not qdrant_client.collection_exists(collection_name):
        return None

    dense_vectorstore = get_vectorstore(session_id)
    dense_retriever = dense_vectorstore.as_retriever(search_kwargs={"k": k})

    docs = get_all_documents(session_id)
    if not docs:
        return dense_retriever

    sparse_retriever = BM25Retriever.from_documents(docs)
    sparse_retriever.k = k

    # Combine dense and sparse retrievers (0.7 dense / 0.3 sparse)
    ensemble_retriever = EnsembleRetriever(
        retrievers=[dense_retriever, sparse_retriever],
        weights=[0.7, 0.3],
    )
    return ensemble_retriever


def search(query: str, session_id: str, k: int = 4) -> list[Document]:
    retriever = get_hybrid_retriever(session_id, k=k)
    if not retriever:
        return []
    return retriever.invoke(query)

