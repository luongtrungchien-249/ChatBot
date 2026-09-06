import pytest

from agents.domain.message import InboundMessage
from agents.policy.mention import mention_regex, primary_name, resolve_mention


def msg(text: str, *, is_group: bool = True, mentioned_bot: bool = False) -> InboundMessage:
    return InboundMessage(
        platform="zalo_bot",
        thread_id="t1",
        sender_id="u1",
        sender_name="Nam",
        text=text,
        is_group=is_group,
        mentioned_bot=mentioned_bot,
        message_id="m1",
        timestamp=0,
        trace_id="tr1",
    )


NAMES = "CP_Assistant,CP"


class TestMention:
    def test_trong_nhom_khong_mention_thi_khong_tra_loi(self) -> None:
        assert resolve_mention(msg("chao ca nha"), NAMES).reply is False

    def test_trong_dm_thi_luon_tra_loi(self) -> None:
        verdict = resolve_mention(msg("hello", is_group=False), NAMES)
        assert (verdict.reply, verdict.text, verdict.empty) == (True, "hello", False)  # type: ignore[union-attr]

    def test_boc_mention_xong_rong_thi_danh_dau_empty(self) -> None:
        verdict = resolve_mention(msg("@CP_Assistant", mentioned_bot=True), NAMES)
        assert verdict.reply is True
        assert verdict.empty is True  # type: ignore[union-attr]

    def test_khong_an_nham_ten_khac(self) -> None:
        pattern = mention_regex(NAMES)
        # '@CP_Assistant2' la mot nguoi dung KHAC, khong phai bot.
        assert pattern.search("@CP_Assistant2") is None
        assert pattern.search("@CPU hong roi") is None
        assert pattern.search("@CP_Assistant") is not None

    @pytest.mark.parametrize(
        "text",
        [
            "@CP_Assistant giúp mình",
            "@CP Assistant giúp mình",
            "@CP giúp mình",
            "@cp assistant deadline?",
        ],
    )
    def test_bat_duoc_ca_ten_day_du_lan_ten_ngan(self, text: str) -> None:
        # Bot tu gioi thieu la "CP Assistant" nen trong nhom nguoi ta se go "@CP".
        assert resolve_mention(msg(text), NAMES).reply is True

    def test_bat_duoc_mention_go_co_dau(self) -> None:
        # BOT_MENTION_NAME khong dau, nhung nguoi Viet GO CO DAU.
        verdict = resolve_mention(msg("@Chiến Assistant giá vé bao nhiêu"), "Chien_Assistant")
        assert verdict.reply is True
        assert verdict.text == "giá vé bao nhiêu"  # type: ignore[union-attr]

    def test_ten_dai_khop_truoc_khong_de_ten_ngan_an_mat_phan_duoi(self) -> None:
        verdict = resolve_mention(msg("@CP_Assistant deadline hôm nào"), NAMES)
        assert verdict.text == "deadline hôm nào"  # type: ignore[union-attr]

    def test_bo_qua_khoang_trang_thua_trong_danh_sach_ten(self) -> None:
        assert resolve_mention(msg("@CP xin chào"), " CP_Assistant , , CP ").reply is True

    def test_danh_sach_ten_rong_thi_nem_loi(self) -> None:
        with pytest.raises(ValueError):
            mention_regex("  ,  ")


class TestPrimaryName:
    def test_lay_ten_dau_tien(self) -> None:
        assert primary_name(NAMES) == "CP_Assistant"
        assert primary_name("  CP  ") == "CP"


class TestDangMentionThatCuaZalo:
    """Do bang tin nhom that ngay 06/09/2026, khong phai suy doan.

    Payload nhom cua Zalo KHONG co truong mention nao — chi
    ['chat', 'date', 'from', 'message_id', 'text']. Zalo chen thang TEN HIEN THI
    cua bot vao text. Ten hien thi bat buoc bat dau bang "Bot" (quy dinh cua Zalo
    Bot Platform), nen no khac ca hai ten bot tu quang ba.

    Hau qua neu thieu: bot IM LANG trong nhom truoc dung cach goi tu nhien nhat —
    bam vao ten bot trong danh sach thanh vien. Va im lang thi khong co thong bao
    loi nao de lan ra.
    """

    #: Nguyen van tu log, khong go lai.
    ZALO_GROUP_TEXT = "@Bot CP Assistant xin chào"

    def _env_names(self) -> str:
        import re
        from pathlib import Path

        env = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
        match = re.search(r"^BOT_MENTION_NAME=(.+)$", env, re.M)
        assert match is not None
        return match.group(1).strip()

    def test_khop_ten_hien_thi_ma_ZALO_tu_chen(self) -> None:
        verdict = resolve_mention(msg(self.ZALO_GROUP_TEXT), self._env_names())
        assert verdict.reply is True
        assert verdict.text == "xin chào"  # type: ignore[union-attr]

    def test_van_khop_ca_hai_ten_bot_tu_quang_ba(self) -> None:
        names = self._env_names()
        for text in ("@CP Assistant xin chào", "@CP xin chào"):
            assert resolve_mention(msg(text), names).reply is True

    def test_them_alias_dai_KHONG_lam_hong_alias_ngan(self) -> None:
        # Ten dai duoc sap truoc trong regex; sai thu tu thi '@CP' bi '@Bot CP
        # Assistant' an mat, hoac nguoc lai '@Bot CP Assistant' chi khop duoc '@CP'
        # va phan 'Assistant' con lai chui vao cau hoi.
        names = self._env_names()
        assert resolve_mention(msg("@CPU giá bao nhiêu"), names).reply is False
