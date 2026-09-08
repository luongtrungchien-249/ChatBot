"""Cong cu `search_knowledge_base` — tra cuu tai lieu noi bo.

Di qua CONG CU chu khong pre-fetch o mot stage rieng: model tu quyet dinh khi nao
can tra tai lieu. Phan loai cung ("cau nay co ve hoi ve quy dinh") vua cung nhac vua
sai o dung nhung ca kho — con model thi doc ca doan hoi thoai truoc do.

Khong khai trong specs() khi CSDL chua co chunk nao. Cung luat voi web_search khi
thieu khoa: cho model thay mot cong cu roi de no tra ve rong lien tuc la day no
bia ra noi dung tai lieu.
"""

from typing import Any

from agents.ports.llm import CallContext
from agents.ports.tool import ToolDefinition, ToolRequirements
from infra.db import fetch
from infra.logger import get_logger

_log = get_logger()

#: So chunk lay ra sau rerank. 3-5 la khoang plan chot: it va DUNG, khong nhieu.
_DEFAULT_K = 5

KNOWLEDGE_SEARCH_DEFINITION = ToolDefinition(
    name="search_knowledge_base",
    description=(
        "Tra cứu kho tài liệu mà tổ chức này đã nạp vào hệ thống. Kho có thể chứa BẤT KỲ "
        "loại tài liệu nào họ quan tâm: quy định, quy trình, chính sách, sổ tay, cẩm nang "
        "chuyên môn, sách công thức nấu ăn, hướng dẫn kỹ thuật. "
        "BẠN KHÔNG BIẾT TRONG KHO CÓ GÌ CHO TỚI KHI TRA. "
        "Vì vậy hãy gọi công cụ này TRƯỚC khi trả lời bất cứ câu hỏi có dữ kiện nào — kể cả "
        "câu bạn nghĩ mình đã biết đáp án. Trả lời từ trí nhớ trong khi tài liệu của họ có "
        "sẵn câu trả lời là bỏ phí đúng thứ họ đã nạp vào, và câu của bạn sẽ không có nguồn. "
        "Không tìm thấy thì công cụ sẽ nói rõ bước tiếp theo. "
        "Riêng tin tức, giá cả, sự kiện đang diễn ra thì dùng thẳng web_search."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Câu hỏi đầy đủ ngữ cảnh, viết bằng tiếng Việt như người dùng đã hỏi. "
                    "Giữ nguyên mã số, tên riêng, thuật ngữ."
                ),
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    requirements=ToolRequirements(
        rate_limit="Khong gioi han — truy van chay tren Postgres cua chinh ta",
        cost_per_call="Mot lan embed cau hoi (~$0,000001) + mot lan rerank",
        timeout_ms=10_000,
    ),
    returns="Cac doan tai lieu lien quan, moi doan kem ten tai lieu va muc de trich dan.",
    failure_modes=(
        "Chua nap tai lieu nao -> cong cu khong duoc khai trong specs()",
        "Moi ket qua duoi RERANK_MIN_SCORE -> tra ve 'khong tim thay', KHONG phai loi",
        "Rerank hong -> giu thu tu RRF va ghi log ERROR, van tra ve ket qua",
    ),
)

#: CSDL co tai lieu khong. Do luc khoi dong process — xem refresh_availability().
_has_documents = False


async def refresh_availability() -> bool:
    """Dem chunk mot lan luc khoi dong.

    Khong dem o moi lan goi specs(): do la mot cau SQL cho MOI tin nhan de tra loi
    mot cau hoi chi doi sau moi lan nap tai lieu. Nap tai lieu xong thi khoi dong
    lai worker — `cli ingest` co nhac dieu do.
    """
    global _has_documents
    try:
        rows = await fetch("SELECT EXISTS (SELECT 1 FROM kb_chunk) AS co")
        _has_documents = bool(rows[0]["co"]) if rows else False
    except Exception as error:
        # Bang chua ton tai (chua migrate) khong phai su co — chi nghia la chua co gi.
        _log.warning("khong dem duoc kb_chunk, coi nhu chua co tai lieu", err=str(error))
        _has_documents = False
    return _has_documents


def is_knowledge_search_available() -> bool:
    return _has_documents


async def run_knowledge_search(payload: dict[str, Any], ctx: CallContext) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("search_knowledge_base can tham so query")

    from knowledge.retrieve.service import knowledge

    # PHAM VI di cung cau hoi, y het hop dong cua memory_fact: mot nhom chi doc
    # duoc tai lieu 'chung' va tai lieu cua chinh no. Truoc day khong co tham so
    # nay — moi nhom doc duoc toan bo moi tai lieu.
    chunks = await knowledge.search(ctx.scope, query, _DEFAULT_K)
    if not chunks:
        # Cau nay di thang vao prompt, va no la don bay manh nhat cua ca luong: no
        # den DUNG khoanh khac model vua thay ket qua rong.
        #
        # Phan nhanh theo LOAI CAU HOI chu khong theo "co tim thay hay khong", vi hai
        # loai co hai cai gia rat khac nhau:
        #
        #   - Cau hoi noi bo ("chinh sach nghi phep nam"): web tra ve luat lao dong
        #     chung — hop ly, co nguon, va SAI voi to chuc nay. Nguoi dung se hanh
        #     dong theo. Te hon han viec khong tra loi.
        #   - Cau hoi kien thuc chung ("cach lam bun cha"): web dung la cho de tra.
        #
        # Cong cu khong biet cau hoi thuoc loai nao — model thi biet, vi no doc ca
        # doan hoi thoai. Nen o day noi ca hai duong kem LY DO, khong chi ra lenh.
        return (
            "Không tìm thấy đoạn tài liệu nội bộ nào liên quan tới câu hỏi này.\n\n"
            "- Nếu đây là câu hỏi về QUY ĐỊNH / QUY TRÌNH / CHÍNH SÁCH của tổ chức: "
            "nói thẳng là tài liệu hiện có không đề cập và gợi ý hỏi bộ phận phụ trách. "
            "ĐỪNG tra web — web không biết quy định riêng của tổ chức này, và một câu "
            "trả lời chung chung sẽ bị hiểu nhầm thành quy định thật.\n"
            "- Nếu đây là câu hỏi KIẾN THỨC CHUNG (món ăn, cách nấu, thông tin đời "
            "sống, sự kiện bên ngoài): gọi web_search ngay trong lượt này, và khi trả "
            "lời phải nói rõ thông tin lấy từ web chứ không phải từ tài liệu nội bộ.\n\n"
            "Cả hai trường hợp: đừng lấy trí nhớ của bạn ra thay thế."
        )

    return "\n\n".join(
        f"[{i}] Nguồn: {c.doc_title}"
        + (f" — mục: {c.section}" if c.section else "")
        + (f" — trang {c.page}" if c.page else "")
        + f"\n{c.content}"
        for i, c in enumerate(chunks, start=1)
    )
