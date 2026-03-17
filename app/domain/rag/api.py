"""RAG domain API router."""

from fastapi import APIRouter

from app.domain.rag.schemas import (
    CollectionInfo,
    DocumentIngest,
    DocumentIngestResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)

router = APIRouter()


def _get_rag_service():
    """Get RAG service instance."""
    from app.main import rag_service
    return rag_service


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngest,
    collection: str = "default",
) -> DocumentIngestResponse:
    """Ingest and vectorize document."""
    service = _get_rag_service()
    return await service.ingest_document(request, collection_name=collection)


@router.post("/query", response_model=RAGQueryResponse)
async def query_documents(request: RAGQueryRequest) -> RAGQueryResponse:
    """RAG search."""
    service = _get_rag_service()
    return await service.query(
        query=request.query,
        top_k=request.top_k,
        collection_name=request.collection,
    )


@router.get("/collections", response_model=list[CollectionInfo])
async def list_collections() -> list[CollectionInfo]:
    """List collections."""
    service = _get_rag_service()
    return await service.list_collections()


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str) -> dict[str, str]:
    """Delete a collection."""
    service = _get_rag_service()
    await service.delete_collection(collection_name)
    return {"status": "deleted", "collection": collection_name}
