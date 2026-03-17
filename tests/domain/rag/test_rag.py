"""rag 도메인 테스트."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.domain.rag.schemas import DocumentIngest, RAGQueryRequest, RAGResult
from app.domain.rag.service import RAGService


class TestRAGService:
    """RAG 서비스 테스트."""

    @pytest.fixture
    async def rag_service(self, tmp_dir: Path):
        """테스트용 RAG 서비스."""
        service = RAGService()
        with patch("app.domain.rag.service.settings") as mock_settings:
            mock_settings.rag_db_path = str(tmp_dir / "chromadb")
            mock_settings.rag_embedding_model = "intfloat/multilingual-e5-small"
            mock_settings.rag_chunk_size = 200
            mock_settings.rag_chunk_overlap = 20
            await service.initialize()
        yield service
        await service.shutdown()

    @pytest.mark.asyncio
    async def test_ingest_document(self, rag_service: RAGService):
        """문서 수집."""
        doc = DocumentIngest(
            content="거실 조명은 Tapo L530이며 IP는 192.168.0.10입니다.",
            source="test.txt",
        )
        result = await rag_service.ingest_document(doc)
        assert result.chunks_count >= 1
        assert result.source == "test.txt"
        assert len(result.document_id) == 12

    @pytest.mark.asyncio
    async def test_query_documents(self, rag_service: RAGService):
        """문서 검색."""
        doc = DocumentIngest(
            content="거실 조명은 Tapo L530이며 IP는 192.168.0.10입니다.",
            source="devices.txt",
        )
        await rag_service.ingest_document(doc)

        result = await rag_service.query(query="거실 조명 IP", top_k=3)
        assert len(result.results) >= 1
        assert "192.168.0.10" in result.results[0].content
        assert result.results[0].score > 0

    @pytest.mark.asyncio
    async def test_query_empty_collection(self, rag_service: RAGService):
        """빈 컬렉션 검색."""
        result = await rag_service.query(query="아무거나", top_k=3)
        assert result.results == []

    @pytest.mark.asyncio
    async def test_list_collections(self, rag_service: RAGService):
        """컬렉션 목록."""
        doc = DocumentIngest(content="테스트 문서", source="test.txt")
        await rag_service.ingest_document(doc)

        collections = await rag_service.list_collections()
        assert len(collections) >= 1
        assert collections[0].name == "default"
        assert collections[0].documents_count >= 1

    @pytest.mark.asyncio
    async def test_delete_collection(self, rag_service: RAGService):
        """컬렉션 삭제."""
        doc = DocumentIngest(content="삭제될 문서", source="test.txt")
        await rag_service.ingest_document(doc)

        await rag_service.delete_collection("default")

        collections = await rag_service.list_collections()
        names = [c.name for c in collections]
        assert "default" not in names

    @pytest.mark.asyncio
    async def test_multiple_collections(self, rag_service: RAGService):
        """여러 컬렉션."""
        doc1 = DocumentIngest(content="장치 정보", source="a.txt")
        doc2 = DocumentIngest(content="레시피 정보", source="b.txt")

        await rag_service.ingest_document(doc1, collection_name="devices")
        await rag_service.ingest_document(doc2, collection_name="recipes")

        collections = await rag_service.list_collections()
        names = {c.name for c in collections}
        assert "devices" in names
        assert "recipes" in names


class TestRAGChunking:
    """텍스트 청킹 테스트."""

    def test_split_short_text(self):
        """짧은 텍스트는 1개 청크."""
        service = RAGService()
        with patch("app.domain.rag.service.settings") as mock_settings:
            mock_settings.rag_chunk_size = 500
            mock_settings.rag_chunk_overlap = 50
            chunks = service._split_text("짧은 텍스트")
        assert len(chunks) == 1

    def test_split_long_text(self):
        """긴 텍스트 분할."""
        service = RAGService()
        paragraphs = [f"문단 {i}입니다. " * 20 for i in range(10)]
        long_text = "\n\n".join(paragraphs)

        with patch("app.domain.rag.service.settings") as mock_settings:
            mock_settings.rag_chunk_size = 200
            mock_settings.rag_chunk_overlap = 20
            chunks = service._split_text(long_text)
        assert len(chunks) > 1


class TestRAGSchemas:
    """RAG 스키마 테스트."""

    def test_document_ingest(self):
        """문서 수집 스키마."""
        doc = DocumentIngest(content="내용", source="file.txt")
        assert doc.content == "내용"
        assert doc.metadata == {}

    def test_rag_query_request(self):
        """검색 요청 스키마."""
        req = RAGQueryRequest(query="검색어")
        assert req.top_k == 5
        assert req.collection == "default"

    def test_rag_result(self):
        """검색 결과 스키마."""
        result = RAGResult(content="결과", source="test.txt", score=0.95)
        assert result.score == 0.95
