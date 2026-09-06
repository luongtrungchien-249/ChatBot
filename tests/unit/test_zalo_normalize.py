"""Payload that cua Zalo, chep tu tai lieu Webhook (docs.zaloplatforms.com).

Khong bia payload: mot bo test dua tren hinh dang tu nghi ra se xanh mai mai va
khong chung minh duoc gi ve nen tang that.
"""

from typing import Any

from adapters.zalo_bot.normalize import normalize_update

#: Chep nguyen van tu tai lieu Webhook.
PRIVATE_UPDATE: dict[str, Any] = {
    "message": {
        "from": {"id": "6ede9afa66b88fe6d6a9", "display_name": "Ted", "is_bot": False},
        "chat": {"id": "6ede9afa66b88fe6d6a9", "chat_type": "PRIVATE"},
        "text": "Xin chào",
        "message_id": "2d758cb5e222177a4e35",
        "date": 1750316131602,
    },
    "event_name": "message.text.received",
}


def group_update(text: str = "@CP deadline la ngay nao", **over: Any) -> dict[str, Any]:
    message = {
        **PRIVATE_UPDATE["message"],
        "chat": {"id": "group-abc", "chat_type": "GROUP"},
        "text": text,
        **over,
    }
    return {"message": message, "event_name": "message.text.received"}


class TestTinNhanRieng:
    def test_chuyen_dung_moi_truong(self) -> None:
        msg = normalize_update(PRIVATE_UPDATE)
        assert msg is not None

        assert msg.platform == "zalo_bot"
        assert msg.thread_id == "6ede9afa66b88fe6d6a9"
        assert msg.sender_id == "6ede9afa66b88fe6d6a9"
        assert msg.sender_name == "Ted"
        assert msg.text == "Xin chào"
        assert msg.message_id == "2d758cb5e222177a4e35"

    def test_date_da_la_mili_giay_KHONG_nhan_them_1000(self) -> None:
        # 1750316131602 ms = nam 2025. Nhan them 1000 thi thanh nam 57000, va moi
        # phep tinh "tin nay cu bao lau" deu sai.
        msg = normalize_update(PRIVATE_UPDATE)
        assert msg is not None
        assert msg.timestamp == 1750316131602

    def test_nhan_rieng_khong_can_mention(self) -> None:
        msg = normalize_update(PRIVATE_UPDATE)
        assert msg is not None
        assert msg.is_group is False
        assert msg.mentioned_bot is True

    def test_moi_tin_mot_trace_id_rieng(self) -> None:
        a = normalize_update(PRIVATE_UPDATE)
        b = normalize_update(PRIVATE_UPDATE)
        assert a is not None and b is not None
        assert a.trace_id != b.trace_id


class TestTinNhanNhom:
    def test_chat_type_GROUP_thi_is_group_True(self) -> None:
        msg = normalize_update(group_update())
        assert msg is not None
        assert msg.is_group is True
        assert msg.thread_id == "group-abc"

    def test_trong_nhom_KHONG_tu_dat_mentioned_bot_True(self) -> None:
        # Dat bua True o day la bot tra loi MOI tin trong nhom — cach nhanh nhat de
        # bi kick. Quyet dinh mention thuoc ve policy/mention.py tren van ban.
        msg = normalize_update(group_update())
        assert msg is not None
        assert msg.mentioned_bot is False

    def test_payload_co_mention_dung_id_bot_thi_nhan_ra(self) -> None:
        update = group_update(mentions=[{"id": "bot-1"}])
        msg = normalize_update(update, bot_id="bot-1")
        assert msg is not None
        assert msg.mentioned_bot is True

    def test_mention_nguoi_khac_khong_tinh_la_mention_bot(self) -> None:
        update = group_update(mentions=[{"id": "nguoi-khac"}])
        msg = normalize_update(update, bot_id="bot-1")
        assert msg is not None
        assert msg.mentioned_bot is False


class TestBoQua:
    def test_su_kien_khong_phai_text_thi_bo_qua(self) -> None:
        update = {**PRIVATE_UPDATE, "event_name": "message.image.received"}
        assert normalize_update(update) is None

    def test_tin_do_BOT_khac_gui_thi_bo_qua(self) -> None:
        # Hai bot trong mot nhom lap lai nhau la vong lap khong day, va no tieu
        # tien that o moi luot.
        update = {
            "event_name": "message.text.received",
            "message": {**PRIVATE_UPDATE["message"], "from": {"id": "b", "is_bot": True}},
        }
        assert normalize_update(update) is None

    def test_thieu_truong_bat_buoc_thi_bo_qua_chu_khong_no(self) -> None:
        for missing in ("text", "chat", "message_id"):
            message = {k: v for k, v in PRIVATE_UPDATE["message"].items() if k != missing}
            update = {"event_name": "message.text.received", "message": message}
            assert normalize_update(update) is None

    def test_payload_rong_khong_lam_no_adapter(self) -> None:
        assert normalize_update({}) is None
        assert normalize_update({"event_name": "message.text.received"}) is None

    def test_thieu_display_name_van_chay(self) -> None:
        message = {**PRIVATE_UPDATE["message"], "from": {"id": "x", "is_bot": False}}
        msg = normalize_update({"event_name": "message.text.received", "message": message})
        assert msg is not None
        assert msg.sender_name == "Ẩn danh"
