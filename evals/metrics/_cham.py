"""Phan CHUNG cho cac chi so dung LLM lam nguoi cham: goi model va doc phan phan quyet.

Chi so nao cung tu dinh nghia LUAT CHAM cua no (prompt) va CACH GOP diem cua no.
Cho nay chi lo phan van chuyen — goi `llm.cheap` roi doc ket qua ra thanh list[bool].
Tach nhu vay vi loi canh bao trong metrics/__init__.py ("doi cach do mot chi so khong
duoc lam thay doi so lieu cua hai chi so kia") nham vao DINH NGHIA PHEP DO, khong nham
vao viec ba file cung goi mot ham HTTP.

Dinh dang phan quyet, dung cho ca ba chi so kieu "dem y":

    1|CO
    2|KHONG
    3|CO

Vi sao bat danh so lai tu dau dong: model rat hay tra ve thua hoac thieu mot dong so
voi so y no vua liet ke. Co so thu tu thi phat hien duoc ngay, con doc theo thu tu
xuat hien thi mot dong lac cho lam lech het cac dong sau ma khong ai biet.
"""

import re

from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext
from llm.models import MODELS
from llm.openai_client import llm

#: `1|CO` / `2|KHONG`. Chap nhan khoang trang thua va chu thuong.
_PHAN_QUYET = re.compile(r"^\s*(\d+)\s*\|\s*(CO|KHONG)\s*$", re.IGNORECASE | re.MULTILINE)

#: Cau tra loi kieu "khong tim thay", "minh khong biet". Voi bot nay do la HANH VI
#: DUNG khi kho khong co thong tin, nen cac chi so phai xu ly rieng chu khong cham 0
#: mot cach may moc nhu RAGAS goc. Xem answer_relevance.py.
_THOAI_THAC = re.compile(
    r"không tìm thấy|không có (?:thông tin|trong tài liệu)|chưa tìm được|mình không biết"
    r"|not (?:found|covered|available)|no information|does not (?:appear|contain)",
    re.IGNORECASE,
)


def la_thoai_thac(text: str) -> bool:
    """Cau tra loi co phai la mot loi tu choi trung thuc khong."""
    return _THOAI_THAC.search(text) is not None


async def goi_cham(*, system: str, input: str, trace_id: str) -> str:
    """Mot lan goi nguoi cham. Dung route `summarize` y het faithfulness.py."""
    return await llm.cheap(
        system=system,
        input=input,
        max_tokens=MODELS["summarize"].max_tokens,
        route="summarize",
        ctx=CallContext(
            scope=ThreadScope(platform="cli", thread_id="eval"),
            sender_id="eval",
            trace_id=trace_id,
        ),
    )


def doc_phan_quyet(raw: str, so_y: int) -> list[bool] | None:
    """Doc `n|CO` thanh list[bool] dai dung `so_y`. Doc khong duoc -> None.

    Tra ve None chu khong tra ve list rong: hai truong hop do khac nhau han. List rong
    la "khong y nao duoc chung minh" (diem 0), con None la "khong cham duoc" — va gop
    hai cai lam mot se bien mot su co ha tang thanh mot van de chat luong gia.
    """
    if so_y <= 0:
        return None
    thay: dict[int, bool] = {}
    for khop in _PHAN_QUYET.finditer(raw):
        so = int(khop.group(1))
        if 1 <= so <= so_y:
            thay[so] = khop.group(2).upper() == "CO"
    # Doi DU. Thieu mot dong nghia la nguoi cham bo qua mot y, va doan lay phan con
    # lai se cho ra mot con so trong nhu that.
    if len(thay) != so_y:
        return None
    return [thay[i] for i in range(1, so_y + 1)]
