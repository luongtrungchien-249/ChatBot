"""Tim kiem web qua Tavily.

Chon Tavily vi no tra ve NOI DUNG DA TRICH XUAT san, khong chi title + snippet nhu
SERP thuong. Bot duoc mot vong fetch trang roi boc HTML — vong do vua cham, vua la
them mot be mat de dinh HTML rac vao prompt.
"""

from datetime import UTC
from typing import Any

import httpx

from agents.ports.llm import CallContext
from agents.ports.tool import ToolDefinition, ToolRequirements
from config import get_settings
from infra.http import get_http

_ENDPOINT = "https://api.tavily.com/search"
_TIMEOUT_S = 12.0

WEB_SEARCH_DEFINITION = ToolDefinition(
    name="web_search",
    description=(
        "Tìm kiếm thông tin trên internet. Dùng khi câu hỏi cần thông tin thời sự, giá cả, "
        "sự kiện gần đây, hoặc bất cứ điều gì không có trong tài liệu nội bộ. KHÔNG dùng cho "
        "câu hỏi về quy định, quy trình nội bộ của tổ chức — dùng search_knowledge_base "
        "cho việc đó."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Câu truy vấn đầy đủ ngữ cảnh. Viết như đang gõ vào ô tìm kiếm.",
            },
            "max_results": {
                "type": "integer",
                "description": "Số kết quả cần lấy, từ 1 đến 10. Mặc định 5.",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    requirements=ToolRequirements(
        api_key="TAVILY_API_KEY",
        rate_limit="Goi mien phi: 1.000 luot/thang",
        cost_per_call="~$0,008 khi vuot goi mien phi",
        timeout_ms=int(_TIMEOUT_S * 1000),
    ),
    returns="Danh sach ket qua, moi cai gom tieu de, URL va doan noi dung da trich xuat.",
    failure_modes=(
        "Khong co TAVILY_API_KEY -> cong cu khong duoc khai trong specs()",
        "Het quota -> HTTP 429, tra ve loi, model tu noi la khong tra cuu duoc",
        "Timeout 12s -> tra ve loi, vong ReAct van tiep tuc voi cac cong cu khac",
    ),
)


def is_web_search_available() -> bool:
    return get_settings().TAVILY_API_KEY != ""


def _parse_domain(url: str) -> str:
    """Rut domain tu URL. Khong import urllib de giu nhe — regex du cho HTTP(S)."""
    import re as _re

    match = _re.search(r"https?://([^/?#]+)", url)
    return match.group(1) if match else ""


async def run_web_search(payload: dict[str, Any], _ctx: CallContext) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("web_search can tham so query")

    raw_max = payload.get("max_results")
    max_results = min(max(raw_max, 1), 10) if isinstance(raw_max, int) else 5

    response = await get_http().post(
        _ENDPOINT,
        headers={"Authorization": f"Bearer {get_settings().TAVILY_API_KEY}"},
        timeout=_TIMEOUT_S,
        json={
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            # Tu tong hop trong vong ReAct de con giu trich dan.
            "include_answer": False,
        },
    )

    if response.status_code != httpx.codes.OK:
        raise RuntimeError(f"Tavily tra ve {response.status_code}: {response.text[:200]}")

    results: list[dict[str, Any]] = response.json().get("results") or []
    if not results:
        return "Khong tim thay ket qua nao cho truy van nay."

    from datetime import datetime

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"=== KẾT QUẢ TÌM KIẾM WEB ===\n"
        f"Truy vấn: \"{query}\"\n"
        f"Số kết quả: {len(results)}\n"
        f"Thời điểm: {now}"
    )

    blocks: list[str] = []
    for i, r in enumerate(results, start=1):
        url = r.get("url") or ""
        title = r.get("title") or "(khong co tieu de)"
        content = (r.get("content") or "").strip()
        score = r.get("score")
        published = r.get("published_date")
        domain = _parse_domain(url)

        lines = [f"[{i}] {title}", f"URL: {url}"]
        if domain:
            lines.append(f"Domain: {domain}")
        if score is not None:
            lines.append(f"Điểm liên quan: {score:.2f}")
        if published:
            lines.append(f"Ngày xuất bản: {published}")
        lines.append(f"Nội dung:\n{content}")
        blocks.append("\n".join(lines))

    return header + "\n\n" + "\n\n".join(blocks)
