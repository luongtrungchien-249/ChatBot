"""Stage 5: chot chan CUNG theo ngan sach ngay. Khong phai alert.

"Mot nhom 50 nguoi nghich bot co the dot sach ngan sach thang trong mot buoi chieu"
— day la cho bien cau canh bao do thanh mot cau lenh if.

Dat TRUOC moi lan goi model. Vong ReAct o stage generate phai goi lai ham nay truoc
MOI vong lap, vi mot cau hoi co the ton nhieu lan goi model.
"""

from ...ports.ratelimit import RateLimitPort

BUDGET_EXCEEDED_TEXT = (
    "Hôm nay mình đã dùng hết ngân sách được cấp rồi, nên tạm thời chưa trả lời được. "
    "Mai bạn hỏi lại giúp mình nhé."
)


async def check_budget(rate_limit: RateLimitPort) -> bool:
    return await rate_limit.within_daily_budget()
