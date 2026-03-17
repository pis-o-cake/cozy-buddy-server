"""RAG domain schemas."""

from pydantic import BaseModel, Field


class DocumentIngest(BaseModel):
    """Document ingest request."""

    content: str = Field(..., min_length=1, description="Document content")
    source: str = Field(default="", description="Source (filename, URL, etc.)")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class DocumentIngestResponse(BaseModel):
    """Document ingest response."""

    document_id: str
    chunks_count: int
    source: str


class RAGQueryRequest(BaseModel):
    """RAG query request."""

    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    collection: str = Field(default="default", description="Collection name")


class RAGQueryResponse(BaseModel):
    """RAG query response."""

    results: list["RAGResult"]
    query: str


class RAGResult(BaseModel):
    """RAG search result item."""

    content: str
    source: str
    score: float
    metadata: dict[str, str] = Field(default_factory=dict)


class CollectionInfo(BaseModel):
    """Collection info."""

    name: str
    documents_count: int
