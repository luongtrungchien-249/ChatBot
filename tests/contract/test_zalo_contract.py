"""Hop dong voi Zalo Bot API — chay tren PAYLOAD THAT da ghi lai.

Khac unit test o cho quan trong: unit test chay tren payload TOI TU NGHI RA, nen no
chi chung minh code khop voi hieu biet cua toi. Neu hieu biet do sai — va no da sai
mot lan, ve truong mention — thi unit test van xanh. Fixture o day chep tu he thong
that, nen khi Zalo doi payload thi CHO NAY do.

Khong cham mang, khong cham DB: doc file JSON roi day qua ham chuan hoa.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from adapters.zalo_bot.api import EMPTY_POLL_CODE, MAX_MESSAGE_CHARS, ZaloApiError, _unwrap
from adapters.zalo_bot.normalize import normalize_update
from agents.policy.mention import resolve_mention

FIXTURES = Path(__file__).parent / "fixtures" / "zalo_bot"

#: Doc tu .env.example de test do khi ai do doi ten bot ma quen mot trong hai cho.
ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def payload(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def bot_names() -> str:
    import re

    match = re.search(r"^BOT_MENTION_NAME=(.+)$", ENV_EXAMPLE.read_text(encoding="utf-8"), re.M)
    assert match is not None
    return match.group(1).strip()


class TestTinNhanRieng:
    def test_chuan_hoa_duoc(self) -> None:
        msg = normalize_update(payload("private_text"))

        assert msg is not None
        assert msg.platform == "zalo_bot"
        assert msg.is_group is False
        assert msg.text == "Xin chào"
        # `date` da la mili-giay. Nhan them 1000 thi moi phep tinh "tin nay cu bao
        # lau" deu sai, va khong co gi bao loi.
        assert msg.timestamp == 1750316131602

    def test_nhan_rieng_khong_doi_mention(self) -> None:
        msg = normalize_update(payload("private_text"))
        assert msg is not None and msg.mentioned_bot is True


class TestTinNhanNhom:
    def test_payload_nhom_KHONG_CO_truong_mention_nao(self) -> None:
        """Dieu quan trong nhat hoc duoc tu tin nhom that.

        Lop phat hien mention thu nhat (doc truong mention trong payload) duoc viet
        phong xa — hoa ra Zalo khong co truong do. Neu mot ngay Zalo THEM vao thi
        test nay do, va do la luc nen bat lop 1 len.
        """
        message = payload("group_text")["message"]

        assert sorted(message.keys()) == ["chat", "date", "from", "message_id", "text"]
        assert not any(k in message for k in ("mentions", "entities", "mentioned"))

    def test_mentioned_bot_False_vi_payload_khong_noi_gi(self) -> None:
        msg = normalize_update(payload("group_text"))
        assert msg is not None
        assert msg.is_group is True
        assert msg.mentioned_bot is False

    def test_regex_van_nhan_ra_bot_tu_TEN_HIEN_THI_ma_Zalo_chen(self) -> None:
        """Ca duong day: payload that -> chuan hoa -> chinh sach mention.

        Zalo chen nguyen ten hien thi ("Bot CP Assistant") vao text. Ten do khac ca
        hai ten bot tu quang ba, nen phai co mat trong BOT_MENTION_NAME — thieu la
        bot IM LANG trong nhom truoc dung cach goi tu nhien nhat.
        """
        msg = normalize_update(payload("group_text"))
        assert msg is not None

        verdict = resolve_mention(msg, bot_names())

        assert verdict.reply is True
        assert verdict.text == "xin chào"  # type: ignore[union-attr]


class TestPhanHoiCuaAPI:
    def test_get_me(self) -> None:
        result = _unwrap(payload("get_me"))
        assert result["display_name"].startswith("Bot")  # Zalo bat buoc tien to nay
        assert result["can_join_groups"] is True

    def test_poll_rong_la_ok_false_408(self) -> None:
        """Trang thai binh thuong nhat cua mot con bot: khong ai nhan tin.

        Coi 408 la loi thi vong poll backoff nham va bot tre hang phut, dong thoi
        log day canh bao gia.
        """
        body = payload("get_updates_empty")
        assert body["ok"] is False
        assert body["error_code"] == EMPTY_POLL_CODE

    def test_send_message_tra_ve_message_id(self) -> None:
        result = _unwrap(payload("send_message_ok"))
        assert isinstance(result["message_id"], str)

    def test_ok_false_thi_nem_loi(self) -> None:
        # Zalo tra HTTP 200 KEM ok:false cho ca loi that. Chi doc status code thi
        # moi loi deu trong nhu thanh cong.
        with pytest.raises(ZaloApiError):
            _unwrap({"ok": False, "description": "Unauthorized", "error_code": 401})


class TestGioiHanNenTang:
    def test_2000_ky_tu(self) -> None:
        assert MAX_MESSAGE_CHARS == 2_000
