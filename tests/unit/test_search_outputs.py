"""Kiểm thử định dạng output cấu trúc cho 5 dạng công cụ tìm kiếm.

Đảm bảo:
  1. Mỗi dạng công cụ có header, body và trường thông tin chuyên biệt.
  2. Mọi trường thông tin khả dụng đều hiện diện rõ ràng.
  3. Đi qua guard wrap_observation an toàn, không bị cắt xén bất thường.
"""

from typing import Any
import pytest

from agents.domain.knowledge import RetrievedChunk
from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext
from tools.guard import wrap_observation
from tools.knowledge_search import _dinh_dang as format_knowledge
from tools.paper_search import Paper, _format_authors
from tools.web_search import _parse_domain
from tools.youtube import _dinh_dang as format_youtube, _parse_duration

CTX = CallContext(
    scope=ThreadScope(platform="cli", thread_id="t1"), sender_id="u1", trace_id="tr"
)


class TestWebSearchOutput:
    def test_domain_parser(self) -> None:
        assert _parse_domain("https://vnexpress.net/thoi-su/bai-viet.html") == "vnexpress.net"
        assert _parse_domain("http://sub.domain.org/path?a=1") == "sub.domain.org"
        assert _parse_domain("invalid-url") == ""

    async def test_web_search_output_structure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx
        from tools import web_search

        class FakeClient:
            async def post(self, url: str, **kwargs: Any) -> httpx.Response:
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "title": "AI Trends 2026",
                                "url": "https://example.com/ai-2026",
                                "content": "Noi dung ve AI agents va RAG.",
                                "score": 0.952,
                                "published_date": "2026-01-15",
                            }
                        ]
                    },
                )

        monkeypatch.setattr(web_search, "get_http", lambda: FakeClient())
        monkeypatch.setattr(
            web_search,
            "get_settings",
            lambda: type("Settings", (), {"TAVILY_API_KEY": "test-key"})(),
        )

        out = await web_search.run_web_search({"query": "ai trends"}, CTX)

        # Header
        assert "=== KẾT QUẢ TÌM KIẾM WEB ===" in out
        assert 'Truy vấn: "ai trends"' in out
        assert "Số kết quả: 1" in out
        assert "Thời điểm: " in out

        # Fields
        assert "[1] AI Trends 2026" in out
        assert "URL: https://example.com/ai-2026" in out
        assert "Domain: example.com" in out
        assert "Điểm liên quan: 0.95" in out
        assert "Ngày xuất bản: 2026-01-15" in out
        assert "Nội dung:\nNoi dung ve AI agents va RAG." in out

        # Wrap observation
        wrapped = wrap_observation(
            tool_name="web_search", source="Tavily", content=out, trace_id="t"
        )
        assert "<ket_qua_cong_cu" in wrapped
        assert "=== KẾT QUẢ TÌM KIẾM WEB ===" in wrapped


class TestPaperSearchOutput:
    def test_format_authors(self) -> None:
        assert _format_authors([{"name": "Alice"}, {"name": "Bob"}]) == "Alice, Bob"
        long_list = [{"name": f"Author {i}"} for i in range(5)]
        formatted = _format_authors(long_list, max_show=3)
        assert formatted is not None
        assert "Author 0, Author 1, Author 2 et al. (5 tác giả)" in formatted

    def test_paper_dataclass_fields(self) -> None:
        p = Paper(
            title="A survey on RAG",
            source="OpenAlex, arXiv",
            year=2025,
            doi="10.1234/5678",
            url="https://doi.org/10.1234/5678",
            abstract="Summary of survey",
            citations=120,
            authors="Alice, Bob",
            venue="NeurIPS 2025",
        )
        assert p.authors == "Alice, Bob"
        assert p.venue == "NeurIPS 2025"
        assert p.citations == 120


class TestKnowledgeSearchOutput:
    def test_knowledge_output_structure(self) -> None:
        chunks = [
            RetrievedChunk(
                chunk_id="chunk-001",
                doc_title="Quy chế công tác",
                section="Điều 5: Định mức",
                page=10,
                content="Chi phí công tác tối đa...",
                score=0.92,
                distance=0.154,
            )
        ]

        out = format_knowledge(chunks, query="chi phi cong tac")

        # Header
        assert "=== KẾT QUẢ TRA CỨU TÀI LIỆU NỘI BỘ ===" in out
        assert 'Truy vấn gốc: "chi phi cong tac"' in out
        assert "Số đoạn tìm được: 1" in out
        assert "Phương pháp: hybrid (vector + BM25 + rerank)" in out
        assert "Thời điểm: " in out

        # Fields
        assert "[1] Nguồn: Quy chế công tác" in out
        assert "Mục: Điều 5: Định mức" in out
        assert "Trang: 10" in out
        assert "Điểm liên quan: 0.92" in out
        assert "Khoảng cách cosine: 0.1540" in out
        assert "ID đoạn: chunk-001" in out
        assert "Nội dung:\nChi phí công tác tối đa..." in out


class TestYouTubeOutput:
    def test_parse_duration(self) -> None:
        assert _parse_duration("PT1H2M34S") == "1:02:34"
        assert _parse_duration("PT3M33S") == "3:33"
        assert _parse_duration("PT45S") == "0:45"
        assert _parse_duration(None) is None

    def test_youtube_format_with_duration_and_description(self) -> None:
        item = {
            "id": "vid123",
            "snippet": {
                "title": "Tutorial Python Agent",
                "channelTitle": "Dev Channel",
                "publishedAt": "2026-02-01T10:00:00Z",
                "description": "A comprehensive tutorial on building agents.",
            },
            "statistics": {
                "viewCount": "12500",
                "likeCount": "890",
                "commentCount": "45",
            },
            "contentDetails": {
                "duration": "PT15M20S",
            },
        }

        out = format_youtube(item)

        assert "Tutorial Python Agent" in out
        assert "Kenh: Dev Channel | Dang ngay: 2026-02-01" in out
        assert "Thoi luong: 15:20" in out
        assert "Luot xem: 12.500" in out
        assert "Luot thich: 890" in out
        assert "Binh luan: 45" in out
        assert "Link: https://www.youtube.com/watch?v=vid123" in out
        assert "Mo ta: A comprehensive tutorial on building agents." in out
