"""RAG service (ChromaDB + Sentence Transformers)."""

import uuid
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from loguru import logger

from app.config import settings
from app.domain.rag.schemas import (
    CollectionInfo,
    DocumentIngest,
    DocumentIngestResponse,
    RAGQueryResponse,
    RAGResult,
)


class RAGService:
    """RAG search service."""

    def __init__(self) -> None:
        self._client: chromadb.ClientAPI | None = None
        self._embedding_fn: SentenceTransformerEmbeddingFunction | None = None

    async def initialize(self) -> None:
        """Initialize ChromaDB client and embedding model."""
        db_path = Path(settings.rag_db_path)
        db_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(db_path))
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=settings.rag_embedding_model,
        )
        logger.info(
            f"RAG initialized: db={db_path}, embedding={settings.rag_embedding_model}"
        )

    def _get_collection(self, name: str = "default") -> chromadb.Collection:
        """Get or create collection."""
        if not self._client or not self._embedding_fn:
            raise RuntimeError("RAG service not initialized")
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks."""
        chunk_size = settings.rag_chunk_size
        chunk_overlap = settings.rag_chunk_overlap
        chunks: list[str] = []

        paragraphs = text.split("\n\n")
        current_chunk = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            if len(current_chunk) + len(paragraph) <= chunk_size:
                current_chunk += ("\n\n" + paragraph) if current_chunk else paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                if chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        if current_chunk:
            chunks.append(current_chunk)

        return chunks if chunks else [text]

    async def ingest_document(
        self,
        document: DocumentIngest,
        *,
        collection_name: str = "default",
    ) -> DocumentIngestResponse:
        """Ingest and vectorize document."""
        collection = self._get_collection(collection_name)
        chunks = self._split_text(document.content)
        doc_id = uuid.uuid4().hex[:12]

        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": document.source,
                "doc_id": doc_id,
                "chunk_index": str(i),
                **document.metadata,
            }
            for i in range(len(chunks))
        ]

        collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )
        logger.info(f"Document ingested: source={document.source}, chunks={len(chunks)}")

        return DocumentIngestResponse(
            document_id=doc_id,
            chunks_count=len(chunks),
            source=document.source,
        )

    async def query(
        self,
        *,
        query: str,
        top_k: int = 5,
        collection_name: str = "default",
    ) -> RAGQueryResponse:
        """Vector similarity search."""
        collection = self._get_collection(collection_name)
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        rag_results: list[RAGResult] = []
        if results["documents"] and results["distances"]:
            for doc, dist, meta in zip(
                results["documents"][0],
                results["distances"][0],
                results["metadatas"][0] if results["metadatas"] else [{}],
            ):
                score = 1.0 - dist  # cosine distance -> similarity
                rag_results.append(
                    RAGResult(
                        content=doc,
                        source=meta.get("source", ""),
                        score=round(score, 4),
                        metadata={k: str(v) for k, v in meta.items()},
                    )
                )

        logger.info(f"RAG query: query='{query[:50]}', results={len(rag_results)}")
        return RAGQueryResponse(results=rag_results, query=query)

    async def list_collections(self) -> list[CollectionInfo]:
        """List all collections."""
        if not self._client:
            raise RuntimeError("RAG service not initialized")

        collections = self._client.list_collections()
        return [
            CollectionInfo(
                name=col.name,
                documents_count=col.count(),
            )
            for col in collections
        ]

    async def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        if not self._client:
            raise RuntimeError("RAG service not initialized")
        self._client.delete_collection(name)
        logger.info(f"Collection deleted: {name}")

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
        self._embedding_fn = None
        logger.info("RAG service shutdown")
