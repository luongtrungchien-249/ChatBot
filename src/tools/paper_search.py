"""Tim bai bao khoa hoc tren BON nguon, chay SONG SONG roi hop nhat.

Bon nguon bu nhau chu khong thua:
  OpenAlex          rong nhat (~250 trieu cong trinh), co so trich dan
  arXiv             preprint CS/AI/toan/vat ly, co full text PDF
  Semantic Scholar  co TLDR tom tat san
  Crossref          metadata DOI chuan nhat, nhung thuong thieu abstract

asyncio.gather(return_exceptions=True) chu khong phai gather thuong: MOT NGUON CHET
KHONG DUOC LAM HONG CA LOI GOI. Ba nguon con lai van du de tra loi.
"""

import asyncio
import re
from collections.abc import Coroutine
from dataclasses import dataclass, replace
from typing import Any

import httpx

from agents.ports.llm import CallContext
from agents.ports.logger import LoggerPort
from agents.ports.tool import ToolDefinition, ToolRequirements
from config import get_settings
from infra.http import get_http

_TIMEOUT_S = 15.0
_PER_SOURCE_TIMEOUT_S = 10.0

#: Han cho MEM: da co ket qua roi thi khong doi nguon cham nua.
#:
#: `asyncio.gather` doi CA BON nguon, nen do tre cua ca lan tim bang do tre cua nguon
#: CHAM NHAT. Do that trong log: nguon khoe tra ve sau 2,4-3,2s, nhung ca lan goi lai
#: mat dung 10.016ms va 10.014ms — tuc mot nguon treo den het `_PER_SOURCE_TIMEOUT_S`
#: va ba nguon kia ngoi cho no. Duong nay nam trong vong ReAct, tren duong phan hoi.
#:
#: 6s la han MEM: het 6 giay ma DA co it nhat mot nguon tra ve thi lay luon, huy phan
#: con lai. Chua co gi thi van cho tiep den `_PER_SOURCE_TIMEOUT_S` — thieu mot bai
#: bao con hon khong co bai nao.
_SOFT_DEADLINE_S = 6.0

#: Retry MOT lan khi bi 429, va chi khi bi 429.
#:
#: Semantic Scholar khong co khoa thi dung chung mot han muc voi ca thien ha, nen 429
#: la chuyen thuong xuyen chu khong phai su co. Doi mot nhip thuong qua duoc.
#:
#: Khong retry cac ma khac: 4xx khac thi gui lai y het van hong, con 5xx thi ba nguon
#: con lai da du de tra loi — khong dang keo dai do tre cua ca lan tim.
_RETRY_429_DELAY_S = 1.2

PAPER_SEARCH_DEFINITION = ToolDefinition(
    name="paper_search",
    description=(
        "Tìm bài báo khoa học, công trình nghiên cứu, preprint. Dùng khi người dùng hỏi về "
        "nghiên cứu, papers, state of the art, hoặc muốn dẫn nguồn học thuật. Tìm đồng thời "
        "trên OpenAlex, arXiv, Semantic Scholar và Crossref. Truy vấn nên viết bằng TIẾNG ANH "
        "vì phần lớn công trình bằng tiếng Anh."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Từ khoá tìm kiếm, nên bằng tiếng Anh. "
                    'Ví dụ: "retrieval augmented generation Vietnamese".'
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Số bài cần lấy sau khi hợp nhất, từ 1 đến 15. Mặc định 8.",
                "minimum": 1,
                "maximum": 15,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    requirements=ToolRequirements(
        api_key="SEMANTIC_SCHOLAR_API_KEY (tuy chon — khong co thi rate limit thap hon)",
        rate_limit="OpenAlex/arXiv/Crossref khong gioi han thuc te; S2 thap neu khong key",
        cost_per_call="Mien phi",
        timeout_ms=int(_TIMEOUT_S * 1000),
    ),
    returns="Danh sach bai bao da khu trung theo DOI, gom tieu de, nam, DOI/URL, tom tat.",
    failure_modes=(
        "Mot nguon chet -> ghi log, van tra ve ket qua cua ba nguon con lai",
        "Ca bon nguon chet -> tra ve loi, model noi la khong tra cuu duoc",
        "Truy van tieng Viet -> it ket qua; description da dan model viet tieng Anh",
        "Semantic Scholar khong co khoa -> 429 thuong xuyen (dung chung han muc). "
        "Da retry mot lan; van hong thi ba nguon kia van du.",
    ),
)


@dataclass(frozen=True, slots=True)
class Paper:
    title: str
    source: str
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    citations: int | None = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


async def _get_json(
    client: httpx.AsyncClient, url: str, headers: dict[str, str] | None = None
) -> Any:
    # timeout theo TUNG lan goi: client dung chung khong dat timeout mac dinh, vi mot
    # vong long-poll 25 giay va mot lan tra cuu 10 giay khong dung chung mot con so.
    response = await client.get(url, headers=headers or {}, timeout=_PER_SOURCE_TIMEOUT_S)
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        await asyncio.sleep(_RETRY_429_DELAY_S)
        response = await client.get(url, headers=headers or {}, timeout=_PER_SOURCE_TIMEOUT_S)
    if response.status_code != httpx.codes.OK:
        raise RuntimeError(f"HTTP {response.status_code}")
    return response.json()


def _reconstruct_abstract(index: Any) -> str | None:
    """OpenAlex tra abstract duoi dang inverted index: {tu: [vi tri]}. Dung lai."""
    if not isinstance(index, dict):
        return None
    words: dict[int, str] = {}
    for word, positions in index.items():
        if isinstance(positions, list):
            for pos in positions:
                if isinstance(pos, int):
                    words[pos] = word
    if not words:
        return None
    return _clean(" ".join(words[i] for i in sorted(words)))


async def _from_openalex(client: httpx.AsyncClient, query: str, n: int) -> list[Paper]:
    data = await _get_json(client, f"https://api.openalex.org/works?search={query}&per_page={n}")
    papers: list[Paper] = []
    for w in data.get("results") or []:
        title = w.get("display_name")
        if not isinstance(title, str):
            continue
        doi_url = w.get("doi")
        papers.append(
            Paper(
                title=_clean(title),
                year=w.get("publication_year"),
                doi=doi_url.replace("https://doi.org/", "") if isinstance(doi_url, str) else None,
                url=doi_url if isinstance(doi_url, str) else None,
                abstract=_reconstruct_abstract(w.get("abstract_inverted_index")),
                citations=w.get("cited_by_count"),
                source="OpenAlex",
            )
        )
    return papers


async def _from_arxiv(client: httpx.AsyncClient, query: str, n: int) -> list[Paper]:
    response = await client.get(
        f"http://export.arxiv.org/api/query?search_query=all:{query}&max_results={n}",
        timeout=_PER_SOURCE_TIMEOUT_S,
    )
    if response.status_code != httpx.codes.OK:
        raise RuntimeError(f"HTTP {response.status_code}")

    # Atom cua arXiv don gian va on dinh; khong dang keo mot parser XML vao chi de
    # doc bon truong. Neu sau nay can doc sau hon thi hay doi.
    papers: list[Paper] = []
    for entry in response.text.split("<entry>")[1:]:
        title_match = re.search(r"<title>([\s\S]*?)</title>", entry)
        if title_match is None:
            continue
        summary = re.search(r"<summary>([\s\S]*?)</summary>", entry)
        ident = re.search(r"<id>([\s\S]*?)</id>", entry)
        published = re.search(r"<published>(\d{4})", entry)
        papers.append(
            Paper(
                title=_clean(title_match.group(1)),
                year=int(published.group(1)) if published else None,
                url=_clean(ident.group(1)) if ident else None,
                abstract=_clean(summary.group(1)) if summary else None,
                source="arXiv",
            )
        )
    return papers


async def _from_semantic_scholar(client: httpx.AsyncClient, query: str, n: int) -> list[Paper]:
    fields = "title,abstract,year,externalIds,citationCount,url,tldr"
    key = get_settings().SEMANTIC_SCHOLAR_API_KEY
    data = await _get_json(
        client,
        f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&fields={fields}&limit={n}",
        headers={"x-api-key": key} if key else None,
    )
    papers: list[Paper] = []
    for p in data.get("data") or []:
        title = p.get("title")
        if not isinstance(title, str):
            continue
        ids = p.get("externalIds") or {}
        tldr = p.get("tldr") or {}
        # TLDR ngan va sat y hon abstract — uu tien khi co.
        summary = tldr.get("text") or p.get("abstract")
        papers.append(
            Paper(
                title=_clean(title),
                year=p.get("year"),
                doi=ids.get("DOI"),
                url=p.get("url"),
                abstract=_clean(summary) if isinstance(summary, str) else None,
                citations=p.get("citationCount"),
                source="Semantic Scholar",
            )
        )
    return papers


async def _from_crossref(client: httpx.AsyncClient, query: str, n: int) -> list[Paper]:
    data = await _get_json(
        client,
        f"https://api.crossref.org/works?query={query}&rows={n}",
        # Crossref uu tien request co lien he ("polite pool") — nhanh va on dinh hon.
        headers={"User-Agent": "CP-Assistant/0.1 (mailto:admin@example.com)"},
    )
    papers: list[Paper] = []
    for w in data.get("message", {}).get("items") or []:
        titles = w.get("title")
        if not (isinstance(titles, list) and titles and isinstance(titles[0], str)):
            continue
        parts = (w.get("issued") or {}).get("date-parts")
        year = (
            parts[0][0]
            if isinstance(parts, list) and parts and isinstance(parts[0], list)
            else None
        )
        abstract = w.get("abstract")
        papers.append(
            Paper(
                title=_clean(titles[0]),
                year=year if isinstance(year, int) else None,
                doi=w.get("DOI"),
                url=w.get("URL"),
                abstract=_clean(re.sub(r"<[^>]+>", "", abstract))
                if isinstance(abstract, str)
                else None,
                citations=w.get("is-referenced-by-count"),
                source="Crossref",
            )
        )
    return papers


def _merge(groups: list[list[Paper]]) -> list[Paper]:
    """Khu trung theo DOI truoc, roi den tieu de chuan hoa.

    Giu ban co nhieu thong tin nhat.
    """
    by_key: dict[str, Paper] = {}
    for paper in (p for group in groups for p in group):
        key = (
            f"doi:{paper.doi.lower()}"
            if paper.doi
            else "title:" + re.sub(r"[^a-z0-9]+", "", paper.title.lower())
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = paper
            continue
        # Hop nhat: giu truong nao co gia tri, cong don ten nguon.
        by_key[key] = replace(
            existing,
            doi=existing.doi or paper.doi,
            url=existing.url or paper.url,
            abstract=existing.abstract or paper.abstract,
            citations=existing.citations if existing.citations is not None else paper.citations,
            year=existing.year or paper.year,
            source=existing.source
            if paper.source in existing.source
            else f"{existing.source}, {paper.source}",
        )

    # Nhieu trich dan len truoc; bai chua co trich dan (preprint moi) xuong duoi.
    return sorted(
        by_key.values(), key=lambda p: p.citations if p.citations is not None else -1, reverse=True
    )


async def _fan_out(
    coros: tuple[Coroutine[Any, Any, list[Paper]], ...],
    names: tuple[str, ...],
    trace_id: str,
    logger: LoggerPort | None,
) -> list[list[Paper] | BaseException]:
    """Chay bon nguon song song, nhung KHONG doi nguon cham nhat neu da co ket qua.

    Khac `asyncio.gather`: gather doi tat ca, nen mot nguon treo 10 giay lam ca lan
    tim mat 10 giay du ba nguon kia da xong tu giay thu ba.

    Nguon bi huy tra ve TimeoutError — cho goi da xu ly BaseException nhu mot nguon
    that bai, nen no vao thang duong "mot nguon chet khong lam hong ca loi goi".
    """
    tasks = [asyncio.create_task(c, name=n) for c, n in zip(coros, names, strict=True)]

    done, pending = await asyncio.wait(tasks, timeout=_SOFT_DEADLINE_S)

    # Chua nguon nao THANH CONG thi cho tiep — thieu mot bai bao con hon khong co bai
    # nao. `done` co the chi chua nhung task da nem loi.
    if pending and not any(t.exception() is None for t in done):
        them, pending = await asyncio.wait(
            pending,
            timeout=_PER_SOURCE_TIMEOUT_S - _SOFT_DEADLINE_S,
            return_when=asyncio.FIRST_COMPLETED,
        )
        done |= them

    for task in pending:
        task.cancel()
    if pending and logger is not None:
        logger.info(
            "bo qua nguon cham — da co ket qua tu nguon khac",
            trace_id=trace_id,
            bo_qua=[t.get_name() for t in pending],
        )

    ket_qua: list[list[Paper] | BaseException] = []
    for task in tasks:
        if task in pending:
            ket_qua.append(TimeoutError(f"{task.get_name()} qua cham, da bo qua"))
        else:
            loi = task.exception()
            ket_qua.append(loi if loi is not None else task.result())
    return ket_qua


async def run_paper_search(
    payload: dict[str, Any], ctx: CallContext, logger: LoggerPort | None = None
) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("paper_search can tham so query")

    raw_max = payload.get("max_results")
    max_results = min(max(raw_max, 1), 15) if isinstance(raw_max, int) else 8
    per_source = min(max_results + 2, 15)

    # Pool dung chung cho ca process (infra/http.py). Bon nguon chay song song tren
    # cung mot pool — do la ly do _LIMITS o do de max_connections rong.
    client = get_http()
    names = ("OpenAlex", "arXiv", "Semantic Scholar", "Crossref")
    outcomes = await _fan_out(
        (
            _from_openalex(client, query, per_source),
            _from_arxiv(client, query, per_source),
            _from_semantic_scholar(client, query, per_source),
            _from_crossref(client, query, per_source),
        ),
        names,
        ctx.trace_id,
        logger,
    )

    ok: list[list[Paper]] = []
    failed: list[str] = []
    for name, outcome in zip(names, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            failed.append(name)
            if logger is not None:
                logger.warning(
                    "mot nguon paper_search that bai — van tra ve phan con lai",
                    trace_id=ctx.trace_id,
                    source=name,
                    err=str(outcome)[:200],
                )
        else:
            ok.append(outcome)

    if not ok:
        raise RuntimeError(f"Ca bon nguon deu that bai: {', '.join(failed)}")

    papers = _merge(ok)[:max_results]
    if not papers:
        return f'Khong tim thay bai bao nao cho truy van "{query}".'

    blocks: list[str] = []
    for i, p in enumerate(papers, start=1):
        lines = [
            f"[{i}] {p.title}",
            f"Nam: {p.year or 'khong ro'} | Trich dan: "
            f"{p.citations if p.citations is not None else 'khong ro'} | Nguon: {p.source}",
        ]
        if p.doi:
            lines.append(f"DOI: {p.doi}")
        if p.url:
            lines.append(f"URL: {p.url}")
        if p.abstract:
            lines.append(f"Tom tat: {p.abstract[:700]}")
        blocks.append("\n".join(lines))

    note = f"\n\n(Luu y: khong lay duoc ket qua tu {', '.join(failed)}.)" if failed else ""
    return "\n\n".join(blocks) + note
