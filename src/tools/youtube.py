"""Số liệu một video YouTube — qua API CHÍNH THỨC, không phải cào trang.

VÌ SAO CÔNG CỤ NÀY TỒN TẠI. Người dùng hỏi số lượt thích của một video; bot chỉ có
`web_search`, và một trang kết quả tìm kiếm không mang con số đó một cách đáng tin. Bot
đã trả lời đúng cách — nói thẳng là không lấy được thay vì đoán — nhưng thứ nó thiếu là
NĂNG LỰC, không phải lời lẽ. Đây là năng lực đó.

VÌ SAO KHÔNG CÀO TRANG. Trang xem video của YouTube dựng bằng JavaScript và số liệu nằm
trong một khối JSON nhúng mà cấu trúc đổi vài lần mỗi năm. Cào nó sẽ hỏng IM LẶNG: một
ngày nào đó bộ tách trả về con số ở nhầm trường, và bot đọc ra một con số SAI với đầy đủ
vẻ tự tin. Với một trợ lý mà luật số một là "không bịa", đó là kiểu hỏng tệ nhất. API
chính thức trả JSON có hợp đồng: hỏng thì hỏng ồn ào bằng mã HTTP.

BA ĐIỀU VỀ DỮ LIỆU MÀ MODEL PHẢI BIẾT, nếu không nó sẽ tự lấp chỗ trống:

  1. `likeCount` CÓ THỂ KHÔNG TỒN TẠI. Người đăng có quyền ẩn số lượt thích. Khi đó
     API không trả trường đó — khác hẳn "bằng 0". Công cụ nói rõ là ĐÃ ẨN.
  2. SỐ LƯỢT KHÔNG THÍCH KHÔNG CÒN TỒN TẠI. YouTube gỡ nó khỏi API công khai từ tháng
     12/2021. Mọi con số "dislike" trên mạng đều là ước lượng của bên thứ ba. Hỏi thì
     phải nói là không có, đừng đưa ước lượng ra như số thật.
  3. Số liệu là ẢNH CHỤP tại thời điểm gọi. Video đang lan truyền thì con số đổi từng
     phút, nên câu trả lời phải nói rõ đó là số lúc tra cứu.

Hạn mức: 10.000 đơn vị/ngày miễn phí, `videos.list` tốn 1 đơn vị mỗi lần — tức khoảng
10.000 lượt tra một ngày. Thực tế không chạm tới.
"""

import re
from typing import Any

import httpx

from agents.ports.llm import CallContext
from agents.ports.tool import ToolDefinition, ToolRequirements
from config import get_settings
from infra.http import get_http

_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
_ENDPOINT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
_TIMEOUT_S = 10.0

#: `videos.list` nhận tối đa 50 id một lần. Chặn thấp hơn nhiều: một câu hỏi trong
#: khung chat hiếm khi cần hơn năm video, và mỗi video thêm vào là thêm chữ trong prompt.
_MAX_VIDEO = 5

#: Mọi dạng URL YouTube dẫn tới một video. Id luôn là 11 ký tự.
#:
#: Nhận cả id trần: người dùng hay dán mỗi cái id, và bắt họ dán URL đầy đủ là bắt họ
#: làm việc cho máy.
_DANG_URL = [
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),          # watch?v=
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),      # youtu.be/
    re.compile(r"/shorts/([A-Za-z0-9_-]{11})"),        # /shorts/
    re.compile(r"/embed/([A-Za-z0-9_-]{11})"),         # /embed/
    re.compile(r"/live/([A-Za-z0-9_-]{11})"),          # /live/
    re.compile(r"^([A-Za-z0-9_-]{11})$"),              # id tran
]

YOUTUBE_STATS_DEFINITION = ToolDefinition(
    name="youtube_stats",
    description=(
        "Lấy số liệu CHÍNH THỨC và HIỆN TẠI của video YouTube: lượt xem, lượt thích, số "
        "bình luận, tiêu đề, kênh, ngày đăng. "
        "DÙNG TRONG HAI TRƯỜNG HỢP: (1) người dùng đưa link hoặc ID video; (2) BẤT CỨ KHI "
        "NÀO bạn vừa tìm được tên hoặc link video từ web_search và cần con số đúng — số "
        "like trên các trang tổng hợp, blog xếp hạng hay Wikipedia thường là số CŨ và "
        "lệch nhau giữa các nguồn, còn công cụ này đọc thẳng từ YouTube. "
        "Đã tìm ra video mà không gọi công cụ này để đối chiếu là đưa cho người dùng một "
        "con số bạn biết là có thể sai. "
        "Nhận nhiều video một lần, ngăn bằng dấu phẩy. "
        "KHÔNG tìm được video theo từ khoá — phải có link hoặc ID; muốn tìm thì dùng "
        "web_search trước. "
        "Số lượt KHÔNG THÍCH không tồn tại: YouTube đã gỡ khỏi API từ 12/2021."
    ),
    parameters={
        "type": "object",
        "properties": {
            "video": {
                "type": "string",
                "description": (
                    "Link video hoặc ID 11 ký tự. Nhận mọi dạng: youtube.com/watch?v=..., "
                    "youtu.be/..., /shorts/..., /embed/..., hoặc ID trần. "
                    "Nhiều video thì ngăn bằng dấu phẩy, tối đa 5."
                ),
            }
        },
        "required": ["video"],
        "additionalProperties": False,
    },
    requirements=ToolRequirements(
        api_key="YOUTUBE_API_KEY",
        rate_limit="10.000 don vi/ngay; videos.list ton 1 don vi moi lan",
        cost_per_call="Mien phi trong han muc",
        timeout_ms=int(_TIMEOUT_S * 1000),
    ),
    returns=(
        "Tieu de, kenh, ngay dang, luot xem, luot thich, so binh luan cho tung video. "
        "Neu nguoi dang da an luot thich thi noi ro la DA AN, khong doan."
    ),
    failure_modes=(
        "Khong co YOUTUBE_API_KEY -> cong cu khong duoc khai trong specs()",
        "Link sai hoac khong phai YouTube -> bao loi ro rang, khong doan id",
        "Video rieng tu / da xoa -> API tra ve danh sach rong, cong cu noi khong tim thay",
        "Het han muc -> HTTP 403, model tu noi la khong tra cuu duoc",
    ),
)


YOUTUBE_SEARCH_DEFINITION = ToolDefinition(
    name="youtube_search",
    description=(
        "Tìm video YouTube theo TÊN hoặc TỪ KHOÁ, và trả về kèm số liệu chính thức hiện "
        "tại (lượt xem, lượt thích, bình luận). "
        "DÙNG NGAY khi bạn có TÊN video mà không có link. ĐỪNG gọi web_search để đi tìm "
        "link YouTube — đó là việc của công cụ này và nó làm xong trong MỘT bước, còn "
        "web_search thường tốn vài lượt mà vẫn không ra link. "
        "Có nhiều video cần tra thì gọi công cụ này nhiều lần, mỗi lần một tên. "
        "Đã có sẵn link hoặc ID thì dùng youtube_stats. "
        "Tìm kiếm khớp theo độ liên quan, nên hãy đưa tên càng đầy đủ càng tốt (kèm tên "
        "kênh nếu biết) và LUÔN đối chiếu tiêu đề trả về với tiêu đề bạn đang tìm — "
        "nếu lệch thì nói rõ là không chắc cùng một video."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    'Tên video, càng đầy đủ càng tốt. Ví dụ: "Despacito Luis Fonsi Daddy Yankee".'
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Số video cần lấy, từ 1 đến 5. Mặc định 3.",
                "minimum": 1,
                "maximum": 5,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    requirements=ToolRequirements(
        api_key="YOUTUBE_API_KEY",
        # Day la con so quan trong nhat cua cong cu nay.
        rate_limit="search.list ton 100 don vi + videos.list 1 -> ~99 lan tim moi ngay",
        cost_per_call="Mien phi trong han muc, nhung DAT gap 101 lan youtube_stats",
        timeout_ms=int(_TIMEOUT_S * 1000),
    ),
    returns="Danh sach video khop, moi cai kem tieu de, kenh, ngay dang va so lieu hien tai.",
    failure_modes=(
        "Khong co YOUTUBE_API_KEY -> cong cu khong duoc khai trong specs()",
        "Khong tim thay -> tra ve cau noi ro la khong co, khong doan",
        "Het han muc (99 lan/ngay) -> HTTP 403",
    ),
)


def is_youtube_available() -> bool:
    return get_settings().YOUTUBE_API_KEY != ""


def tach_id(raw: str) -> str | None:
    """Rút ID video từ một chuỗi bất kỳ. `None` khi không nhận ra.

    Trả về None thay vì đoán bừa: gửi một id sai lên API sẽ nhận về danh sách rỗng, và
    "không tìm thấy video" là một câu trả lời SAI cho một cái link viết đúng.
    """
    raw = raw.strip()
    for mau in _DANG_URL:
        khop = mau.search(raw)
        if khop:
            return khop.group(1)
    return None


def _so(gia_tri: Any) -> int | None:
    """API trả số dưới dạng CHUỖI. Trường vắng mặt = bị ẩn, khác hẳn bằng 0."""
    if gia_tri is None:
        return None
    try:
        return int(gia_tri)
    except (TypeError, ValueError):
        return None


def _dinh_dang(item: dict[str, Any]) -> str:
    snippet = item.get("snippet") or {}
    thong_ke = item.get("statistics") or {}

    tieu_de = snippet.get("title") or "(khong co tieu de)"
    kenh = snippet.get("channelTitle") or "(khong ro kenh)"
    ngay = (snippet.get("publishedAt") or "")[:10]

    xem = _so(thong_ke.get("viewCount"))
    thich = _so(thong_ke.get("likeCount"))
    binh_luan = _so(thong_ke.get("commentCount"))

    dong = [f"{tieu_de}", f"Kenh: {kenh}" + (f" | Dang ngay: {ngay}" if ngay else "")]
    dong.append(f"Luot xem: {xem:,}".replace(",", ".") if xem is not None else "Luot xem: khong co")
    # Phan biet AN voi BANG KHONG. Gop lai la day model toi cho bia mot con so.
    dong.append(
        f"Luot thich: {thich:,}".replace(",", ".")
        if thich is not None
        else "Luot thich: NGUOI DANG DA AN — khong co con so nao, dung doan"
    )
    dong.append(
        f"Binh luan: {binh_luan:,}".replace(",", ".")
        if binh_luan is not None
        else "Binh luan: da tat hoac bi an"
    )
    dong.append(f"Link: https://www.youtube.com/watch?v={item.get('id', '')}")
    return "\n".join(dong)


async def run_youtube_stats(payload: dict[str, Any], _ctx: CallContext) -> str:
    raw = payload.get("video")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("youtube_stats can tham so video (link hoac ID)")

    phan = [p for p in raw.split(",") if p.strip()][:_MAX_VIDEO]
    ids: list[str] = []
    khong_nhan_ra: list[str] = []
    for p in phan:
        vid = tach_id(p)
        (ids.append(vid) if vid else khong_nhan_ra.append(p.strip()[:60]))

    if not ids:
        # Noi ro la KHONG DOC DUOC LINK, khac han "khong tim thay video". Hai cau do
        # dan nguoi dung di hai huong khac nhau.
        return (
            "Khong doc duoc ID video tu chuoi da cho: "
            + ", ".join(khong_nhan_ra)
            + ". Hay gui link dang youtube.com/watch?v=... hoac youtu.be/... "
            "Hay noi thang voi nguoi dung la link chua dung, dung doan noi dung video."
        )

    response = await get_http().get(
        _ENDPOINT,
        params={
            "part": "snippet,statistics",
            "id": ",".join(ids),
            "key": get_settings().YOUTUBE_API_KEY,
        },
        timeout=_TIMEOUT_S,
    )
    if response.status_code != httpx.codes.OK:
        raise RuntimeError(f"YouTube API tra ve {response.status_code}: {response.text[:200]}")

    items: list[dict[str, Any]] = response.json().get("items") or []
    if not items:
        return (
            "Khong tim thay video nao voi ID da cho. Video co the da bi xoa, dat rieng tu, "
            "hoac ID sai. Hay noi thang, dung suy doan noi dung."
        )

    khoi = [_dinh_dang(it) for it in items]

    # Id gui di ma khong quay ve: video rieng tu hoac da xoa. Im lang bo qua se lam
    # nguoi dung tuong bot da tra cuu du.
    thieu = [i for i in ids if i not in {it.get("id") for it in items}]
    if thieu:
        khoi.append(f"Khong lay duoc du lieu cho: {', '.join(thieu)} (rieng tu hoac da xoa).")
    if khong_nhan_ra:
        khoi.append(f"Khong doc duoc link: {', '.join(khong_nhan_ra)}.")

    khoi.append(
        "Day la so lieu tai THOI DIEM TRA CUU va se thay doi. "
        "YouTube khong con cong bo so luot khong thich tu 12/2021."
    )
    return "\n\n".join(khoi)


async def _lay_thong_ke(ids: list[str]) -> list[dict[str, Any]]:
    """videos.list cho mot loat id. Tach rieng vi ca hai cong cu deu dung."""
    response = await get_http().get(
        _ENDPOINT,
        params={
            "part": "snippet,statistics",
            "id": ",".join(ids),
            "key": get_settings().YOUTUBE_API_KEY,
        },
        timeout=_TIMEOUT_S,
    )
    if response.status_code != httpx.codes.OK:
        raise RuntimeError(f"YouTube API tra ve {response.status_code}: {response.text[:200]}")
    items: list[dict[str, Any]] = response.json().get("items") or []
    return items


async def run_youtube_search(payload: dict[str, Any], _ctx: CallContext) -> str:
    """Tim theo ten roi lay so lieu that — HAI lan goi API trong mot lan goi cong cu.

    `search.list` KHONG tra ve thong ke, chi tra ve id va snippet. Nen phai goi tiep
    `videos.list`. Gop hai buoc vao mot cong cu chu khong bat model tu noi: bat no goi
    hai cong cu lien tiep la them mot vong ReAct, tuc them mot lan goi model va vai giay
    do tre, cho mot viec khong co quyet dinh nao o giua.

    HAN MUC: search.list ton 100 don vi, videos.list ton 1 — tuc ~99 lan tim moi ngay,
    so voi ~10.000 lan cua youtube_stats. Do la ly do mo ta cua cong cu nay noi thang
    "co link roi thi dung youtube_stats".
    """
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("youtube_search can tham so query")

    raw_max = payload.get("max_results")
    so_luong = min(max(raw_max, 1), 5) if isinstance(raw_max, int) else 3

    response = await get_http().get(
        _ENDPOINT_SEARCH,
        params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": so_luong,
            "key": get_settings().YOUTUBE_API_KEY,
        },
        timeout=_TIMEOUT_S,
    )
    if response.status_code != httpx.codes.OK:
        raise RuntimeError(f"YouTube API tra ve {response.status_code}: {response.text[:200]}")

    ids = [
        it["id"]["videoId"]
        for it in (response.json().get("items") or [])
        if isinstance(it.get("id"), dict) and it["id"].get("videoId")
    ]
    if not ids:
        return (
            f"Khong tim thay video nao khop voi: {query}. "
            "Hay noi thang la khong tim thay, dung doan ten hay so lieu."
        )

    items = await _lay_thong_ke(ids)
    if not items:
        return f"Tim thay video nhung khong lay duoc so lieu cho: {query}."

    khoi = [_dinh_dang(it) for it in items]
    khoi.append(
        "Ket qua sap theo DO LIEN QUAN cua YouTube, khong phai theo luot thich. "
        "Hay doi chieu tieu de voi thu ban dang tim; lech thi noi ro la khong chac cung "
        "mot video. So lieu la tai THOI DIEM TRA CUU."
    )
    return "\n\n".join(khoi)
