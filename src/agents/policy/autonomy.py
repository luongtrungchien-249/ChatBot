"""BA MỨC TỰ CHỦ — ai quyết, và quyết vào lúc nào.

Ba mức, theo thứ tự người can thiệp ngày càng sớm:

    on-the-loop     Agent làm → người xem lại SAU.  Rủi ro thấp, đảo ngược được.
    in-the-loop     Agent đề xuất → người duyệt TRƯỚC.  Rủi ro trung bình.
    tiebreaker      Người quyết, agent chỉ hỗ trợ.  Rủi ro cao.

MỘT ĐIỀU PHẢI NÓI THẲNG: bot này gần như không có hành động rủi ro cao. Nó đọc và trả
lời; ba công cụ đều chỉ-đọc; thứ duy nhất nó ghi được là `memory_fact`. Nên bảng dưới
đây cố ý NGẮN, và cột "hiện trạng" nói rõ cái gì đã có sẵn từ trước.

Dựng một bộ máy phê duyệt ba tầng cho những việc không tồn tại là nghi lễ: nó tạo cảm
giác đã kiểm soát, trong khi thứ thật sự cần canh — ghi fact tự động về người có tên —
lại là thứ duy nhất chưa có luồng nào.

Bảng này là TÀI LIỆU CƯỠNG CHẾ ĐƯỢC, không phải chú thích: `test_autonomy.py` đối chiếu
nó với hành vi thật của đường ống. Thêm một hành động mới mà quên xếp mức thì test đỏ.
"""

from dataclasses import dataclass
from typing import Literal

Muc = Literal["on-the-loop", "in-the-loop", "tiebreaker"]


@dataclass(frozen=True, slots=True)
class HanhDong:
    ten: str
    muc: Muc
    #: Vì sao mức đó, chứ không phải mức cao hơn hay thấp hơn.
    ly_do: str
    #: Đảo ngược bằng cách nào. Rỗng = không đảo ngược được, và khi đó mức phải >= in-the-loop.
    dao_nguoc: str


HANH_DONG: tuple[HanhDong, ...] = (
    # ---------------------------------------------------------- on-the-loop
    HanhDong(
        ten="tra-loi",
        muc="on-the-loop",
        ly_do=(
            "Một câu trả lời sai được sửa bằng câu tiếp theo. Bắt duyệt trước mỗi câu "
            "thì bot không còn là bot."
        ),
        dao_nguoc="Nhắn lại đính chính; lịch sử hội thoại lưu trong Postgres.",
    ),
    HanhDong(
        ten="tra-cuu",
        muc="on-the-loop",
        ly_do="Ba công cụ đều CHỈ ĐỌC. Không công cụ nào đổi được trạng thái bên ngoài.",
        dao_nguoc="Không cần — không có gì bị thay đổi.",
    ),
    HanhDong(
        ten="ghi-fact-tu-dong",
        muc="on-the-loop",
        ly_do=(
            "Đây là hành động cần canh nhất trong cả hệ thống: bot ghi thông tin về "
            "NGƯỜI CÓ TÊN mà không ai bấm nút đồng ý. Vẫn xếp on-the-loop chứ không "
            "cao hơn vì ba lớp chặn đã thu hẹp nó rất nhiều (loại câu của bot, tên "
            "phải có trong lô, confidence >= 0.8), và vì bắt duyệt trước thì không ai "
            "duyệt và tính năng chết. Điều kiện đủ là phải NHÌN THẤY được: `cli review`."
        ),
        dao_nguoc="`cli review bo <số>` — soft delete, fact biến khỏi mọi prompt sau đó.",
    ),
    # ---------------------------------------------------------- in-the-loop
    HanhDong(
        ten="xoa-fact",
        muc="in-the-loop",
        ly_do=(
            "Soft delete KHÔNG có lệnh khôi phục, nên một lần gõ nhầm là mất thật. "
            "Ngưỡng tìm ứng viên lại cố ý rộng (0,30) để không bỏ sót cách người dùng "
            "nói — nên danh sách thường có cả thứ họ không định xoá."
        ),
        dao_nguoc="Không. Đó chính là lý do phải duyệt trước.",
    ),
    # ---------------------------------------------------------- tiebreaker
    HanhDong(
        ten="nap-tai-lieu",
        muc="tiebreaker",
        ly_do=(
            "Tài liệu nạp vào sẽ được kéo vào prompt ở mọi câu hỏi liên quan, cho cả "
            "nhóm, mãi mãi. Một tệp sai hoặc có câu ra lệnh nhúng là một lỗi lặp lại."
        ),
        dao_nguoc="Xoá `kb_document` (chunk theo CASCADE). Nhưng câu trả lời đã đưa ra thì không.",
    ),
    HanhDong(
        ten="mo-nhom",
        muc="tiebreaker",
        ly_do="Quyết định ai được dùng bot. Không phải quyết định kỹ thuật.",
        dao_nguoc="`cli deny` — ghi dòng 'disabled', không xoá dấu vết ai đã mở.",
    ),
)

#: Tra cứu nhanh theo tên.
MUC_CUA: dict[str, Muc] = {h.ten: h.muc for h in HANH_DONG}


def can_duyet_truoc(ten: str) -> bool:
    """Hành động này có phải chờ người đồng ý trước khi thực hiện không."""
    return MUC_CUA[ten] in ("in-the-loop", "tiebreaker")


def agent_tu_lam_duoc(ten: str) -> bool:
    """Agent có được tự khởi xướng hành động này không.

    `tiebreaker` = không, kể cả khi được nhờ: đường duy nhất là CLI trên máy chủ, nên
    agent không có cách nào chạm tới. Đó là cưỡng chế bằng cấu trúc, không bằng luật
    trong prompt — và cấu trúc thì model không thuyết phục được.
    """
    return MUC_CUA[ten] != "tiebreaker"
