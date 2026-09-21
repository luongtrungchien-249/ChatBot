"""Kịch bản kiểm tra cấu hình output cho từng dạng tìm kiếm.

Cho phép chạy offline kiểm tra trực quan format output của:
  1. web_search (Tavily)
  2. paper_search (OpenAlex, arXiv, Semantic Scholar, Crossref)
  3. search_knowledge_base (Internal RAG)
  4. youtube_stats (YouTube Data API v3)
  5. youtube_search (YouTube Data API v3)

Cách chạy:
  python ops/inspect_search_outputs.py --all
  python ops/inspect_search_outputs.py --tool web
  python ops/inspect_search_outputs.py --tool paper
  python ops/inspect_search_outputs.py --tool knowledge
  python ops/inspect_search_outputs.py --tool youtube_stats
  python ops/inspect_search_outputs.py --tool youtube_search
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Đảm bảo import được src/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from agents.domain.knowledge import RetrievedChunk
from tools.guard import wrap_observation
from tools.knowledge_search import _dinh_dang as format_knowledge
from tools.paper_search import Paper
from tools.web_search import _parse_domain
from tools.youtube import _dinh_dang as format_youtube, _parse_duration


def sample_web_output() -> str:
    """Tạo mẫu output cho web_search."""
    query = "trí tuệ nhân tạo tạo sinh 2026 xu hướng"
    results = [
        {
            "title": "Báo cáo Toàn cảnh AI và Generative AI năm 2026",
            "url": "https://techinsight.vn/ai-trends-2026",
            "score": 0.9412,
            "published_date": "2026-03-15",
            "content": (
                "Các mô hình nền tảng trong năm 2026 chuyển dịch mạnh mẽ từ single-turn reasoning "
                "sang agentic multi-step workflows. Doanh nghiệp tập trung tối ưu hóa chi phí token "
                "và bảo vệ dữ liệu nội bộ bằng giải pháp Hybrid RAG kết hợp reranker cục bộ."
            ),
        },
        {
            "title": "Xu hướng công nghệ AI Agent tự động hóa quy trình",
            "url": "https://genai-vietnam.org/articles/agentic-ai",
            "score": 0.8875,
            "published_date": "2026-02-28",
            "content": (
                "Kiến trúc ReAct kết hợp Guardrails đa tầng trở thành tiêu chuẩn công nghiệp "
                "nhằm ngăn chặn prompt injection và rò rỉ thông tin nhạy cảm qua đầu ra LLM."
            ),
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"=== KẾT QUẢ TÌM KIẾM WEB ===\n"
        f'Truy vấn: "{query}"\n'
        f"Số kết quả: {len(results)}\n"
        f"Thời điểm: {now}"
    )

    blocks: list[str] = []
    for i, r in enumerate(results, start=1):
        url = str(r.get("url") or "")
        domain = _parse_domain(url)
        lines = [
            f"[{i}] {r.get('title')}",
            f"URL: {url}",
        ]
        if domain:
            lines.append(f"Domain: {domain}")
        if r.get("score") is not None:
            lines.append(f"Điểm liên quan: {r['score']:.2f}")
        if r.get("published_date"):
            lines.append(f"Ngày xuất bản: {r['published_date']}")
        lines.append(f"Nội dung:\n{r.get('content')}")
        blocks.append("\n".join(lines))

    return header + "\n\n" + "\n\n".join(blocks)


def sample_paper_output() -> str:
    """Tạo mẫu output cho paper_search."""
    query = "Retrieval-Augmented Generation evaluation metrics"
    papers = [
        Paper(
            title="A Systematic Survey on Evaluation Paradigms for Retrieval-Augmented Generation",
            year=2025,
            doi="10.1145/3640457.3688123",
            url="https://doi.org/10.1145/3640457.3688123",
            abstract=(
                "We provide a comprehensive overview of evaluation frameworks for RAG systems, "
                "categorizing benchmarks across retrieval accuracy, generation faithfulness, "
                "and robustness against poisoned context."
            ),
            citations=342,
            source="OpenAlex, Semantic Scholar",
            authors="Nguyen Van A, John Smith, Emily Chen et al. (5 tác giả)",
            venue="ACM Computing Surveys 2025",
        ),
        Paper(
            title="FastRerank: Lightweight Cross-Encoders for Real-Time Neural Retrieval",
            year=2026,
            doi=None,
            url="https://arxiv.org/abs/2601.09876",
            abstract=(
                "This paper presents FastRerank, a distilled cross-encoder architecture achieving "
                "98% of MonoT5 quality while operating with 4x lower latency on commodity hardware."
            ),
            citations=18,
            source="arXiv",
            authors="Le Thi B, Tran C",
            venue="arXiv",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"=== KẾT QUẢ TÌM KIẾM BÀI BÁO ===\n"
        f'Truy vấn: "{query}"\n'
        f"Tổng bài (sau khử trùng): {len(papers)}\n"
        f"Nguồn: OpenAlex ✓ | arXiv ✓ | Semantic Scholar ✓ | Crossref ✓\n"
        f"Thời điểm: {now}"
    )

    blocks: list[str] = []
    for i, p in enumerate(papers, start=1):
        lines = [f"[{i}] {p.title}"]
        if p.authors:
            lines.append(f"Tác giả: {p.authors}")
        lines.append(
            f"Năm: {p.year or 'không rõ'} | Trích dẫn: "
            f"{p.citations if p.citations is not None else 'không rõ'} | "
            f"Tìm thấy trên: {p.source}"
        )
        if p.venue:
            lines.append(f"Tạp chí/Hội nghị: {p.venue}")
        if p.doi:
            lines.append(f"DOI: {p.doi}")
        if p.url:
            lines.append(f"URL: {p.url}")
        if p.abstract:
            lines.append(f"Tóm tắt: {p.abstract}")
        blocks.append("\n".join(lines))

    return header + "\n\n" + "\n\n".join(blocks)


def sample_knowledge_output() -> str:
    """Tạo mẫu output cho search_knowledge_base."""
    query = "quy trình thanh toán công tác phí"
    chunks = [
        RetrievedChunk(
            chunk_id="qd-finance-2026-c04",
            doc_title="Quy chế Chi tiêu Nội bộ 2026 (QĐ-88/2026/QĐ-TC)",
            section="Chương III: Chế độ công tác phí > Điều 12. Định mức lưu trú",
            page=14,
            content=(
                "Cán bộ nhân viên đi công tác tại các thành phố trực thuộc Trung ương được thanh toán "
                "tiền phòng tối đa 1.200.000 VNĐ/đêm theo hóa đơn tài chính hợp lệ. Các khoản phụ cấp "
                "lưu trú được chi trả 250.000 VNĐ/ngày theo phê duyệt kế hoạch công tác."
            ),
            score=0.915,
            distance=0.1824,
        ),
        RetrievedChunk(
            chunk_id="hd-travel-2026-c02",
            doc_title="Sổ tay Hướng dẫn Thủ tục Thanh toán Điện tử",
            section="Mục 2. Hồ sơ tạm ứng và thanh toán công tác",
            page=5,
            content=(
                "Hồ sơ đề nghị thanh toán công tác phí phải gửi về phòng Tài chính - Kế toán trong "
                "vòng 07 ngày làm việc kể từ ngày kết thúc chuyến công tác, đính kèm vé máy bay/tàu xe "
                "và bảng kê hành trình."
            ),
            score=0.864,
            distance=0.2215,
        ),
    ]

    return format_knowledge(chunks, query)


def sample_youtube_stats_output() -> str:
    """Tạo mẫu output cho youtube_stats."""
    video_item = {
        "id": "dQw4w9WgXcQ",
        "snippet": {
            "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
            "channelTitle": "Rick Astley",
            "publishedAt": "2009-10-25T06:57:33Z",
            "description": (
                "The official video for 'Never Gonna Give You Up' by Rick Astley. "
                "Taken from the album 'Whenever You Need Somebody' – deluxe 2CD and digital deluxe out now! "
                "Stream Rick Astley here: https://rickastley.lnk.to/stream"
            ),
        },
        "statistics": {
            "viewCount": "1580245100",
            "likeCount": "17850000",
            "commentCount": "2450120",
        },
        "contentDetails": {
            "duration": "PT3M33S",
        },
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"=== SỐ LIỆU VIDEO YOUTUBE ===\n"
        f"Thời điểm tra cứu: {now}"
    )

    body = format_youtube(video_item)
    footer = (
        "Day la so lieu tai THOI DIEM TRA CUU va se thay doi. "
        "YouTube khong con cong bo so luot khong thich tu 12/2021."
    )
    return header + "\n\n" + body + "\n\n" + footer


def sample_youtube_search_output() -> str:
    """Tạo mẫu output cho youtube_search."""
    query = "hướng dẫn xây dựng chatbot RAG với python"
    items = [
        {
            "id": "abc123vid01",
            "snippet": {
                "title": "Tự Xây Dựng Chatbot RAG Toàn Diện Từ Con Số 0 Với Python & LangChain",
                "channelTitle": "AI Engineering Hub",
                "publishedAt": "2026-01-20T14:00:00Z",
                "description": (
                    "Video hướng dẫn từng bước thiết kế RAG agent chuyên nghiệp: từ chunking văn bản, "
                    "hybrid search (BM25 + vector), cross-encoder rerank đến bảo vệ đầu ra."
                ),
            },
            "statistics": {
                "viewCount": "48500",
                "likeCount": "2100",
                "commentCount": "340",
            },
            "contentDetails": {
                "duration": "PT42M15S",
            },
        },
        {
            "id": "xyz789vid02",
            "snippet": {
                "title": "Tối Ưu Hóa RAG: Reranking và Triệt Tiêu Hallucination Trong Thực Tế",
                "channelTitle": "DevOps & AI Vietnam",
                "publishedAt": "2026-02-10T09:30:00Z",
                "description": (
                    "Phân tích so sánh chi tiết hiệu năng giữa bi-encoders và cross-encoders, "
                    "kỹ thuật calibration khoảng cách cosine để quyết định khi nào cần hỏi lại người dùng."
                ),
            },
            "statistics": {
                "viewCount": "29100",
                "likeCount": "1450",
                "commentCount": "195",
            },
            "contentDetails": {
                "duration": "PT28M40S",
            },
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"=== KẾT QUẢ TÌM KIẾM YOUTUBE ===\n"
        f'Truy vấn: "{query}"\n'
        f"Số video tìm được: {len(items)}\n"
        f"Xếp theo: Độ liên quan (YouTube)\n"
        f"Thời điểm: {now}"
    )

    blocks: list[str] = []
    for i, it in enumerate(items, start=1):
        blocks.append(f"[{i}] {format_youtube(it)}")

    footer = (
        "Kết quả xếp theo ĐỘ LIÊN QUAN của YouTube, không phải theo lượt thích. "
        "Hay doi chieu tieu de voi thu ban dang tim; lech thi noi ro la khong chac cung "
        "mot video. So lieu la tai THOI DIEM TRA CUU."
    )
    return header + "\n\n" + "\n\n".join(blocks) + "\n\n" + footer


def print_section(title: str, content: str, tool_source: str) -> None:
    wrapped = wrap_observation(
        tool_name=title.lower().replace(" ", "_"),
        source=tool_source,
        content=content,
        trace_id="inspect-trace",
    )
    chars = len(content)
    tokens_est = chars // 4

    print("=" * 80)
    print(f"  {title.upper()} (Độ dài: {chars:,} ký tự, ~{tokens_est:,} tokens)")
    print("=" * 80)
    print(content)
    print("-" * 80)
    print("  [Quan sát sau khi qua guard wrap_observation (đưa vào Prompt)]:")
    print("-" * 80)
    print(wrapped[:350] + ("\n... [còn lại đã trích xuất an toàn] ...\n" if len(wrapped) > 350 else ""))
    print("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiểm tra mẫu output cho từng dạng tìm kiếm.")
    parser.add_argument(
        "--tool",
        choices=["web", "paper", "knowledge", "youtube_stats", "youtube_search"],
        help="Dạng tìm kiếm cụ thể cần kiểm tra.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Kiểm tra toàn bộ 5 dạng tìm kiếm.",
    )

    args = parser.parse_args()

    if not args.all and not args.tool:
        args.all = True

    print("\n" + "#" * 80)
    print("  KIỂM TRA CẤU HÌNH OUTPUT CÁC DẠNG TÌM KIẾM (SEARCH TOOLS OUTPUT INSPECTION)")
    print("#" * 80 + "\n")

    if args.all or args.tool == "web":
        print_section("1. Web Search Output", sample_web_output(), "Tavily")

    if args.all or args.tool == "paper":
        print_section(
            "2. Paper Search Output",
            sample_paper_output(),
            "OpenAlex + arXiv + Semantic Scholar + Crossref",
        )

    if args.all or args.tool == "knowledge":
        print_section("3. Knowledge Base Search Output", sample_knowledge_output(), "Tai lieu noi bo")

    if args.all or args.tool == "youtube_stats":
        print_section("4. YouTube Video Stats Output", sample_youtube_stats_output(), "YouTube Data API v3")

    if args.all or args.tool == "youtube_search":
        print_section("5. YouTube Search Output", sample_youtube_search_output(), "YouTube Data API v3")


if __name__ == "__main__":
    main()
