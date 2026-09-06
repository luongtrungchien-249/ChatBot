from agents.prompt.budget import (
    CHARS_PER_TOKEN,
    TOKEN_BUDGET,
    exceeds_budget,
    trim_to_budget,
)

#: Tieng Viet co dau — dung loai van ban that, khong dung 'aaa...'.
CAU = "Deadline nộp báo cáo quý 3 là ngày 30 tháng 11, họp tổng kết lúc 14 giờ. "


class TestTrimToBudget:
    def test_duoi_tran_thi_giu_nguyen(self) -> None:
        result = trim_to_budget("ngắn gọn", "facts")
        assert result.text == "ngắn gọn"
        assert result.trimmed_tokens == 0

    def test_van_ban_co_kich_thuoc_that_KHONG_bi_cat(self) -> None:
        # Muc tieu cua tran moi: trong van hanh binh thuong khong bao gio cham toi.
        hoi_thoai = CAU * 15  # 15 tin nhan nhom
        assert trim_to_budget(hoi_thoai, "recent").trimmed_tokens == 0

        tai_lieu = CAU * (5 * 12)  # 5 chunk sau rerank
        assert trim_to_budget(tai_lieu, "knowledge").trimmed_tokens == 0

    def test_cau_dao_van_nay_khi_vuot_tran(self) -> None:
        qua = CAU * 2_000
        result = trim_to_budget(qua, "facts")

        assert len(result.text) <= TOKEN_BUDGET["facts"] * CHARS_PER_TOKEN
        assert result.trimmed_tokens > 0
        assert qua.startswith(result.text)

    def test_cat_o_ranh_gioi_khong_cat_giua_tu(self) -> None:
        result = trim_to_budget(CAU * 2_000, "facts")
        assert result.text[-1] in " \n"

    def test_moi_tang_co_tran_rieng(self) -> None:
        qua = CAU * 3_000
        assert len(trim_to_budget(qua, "facts").text) < len(
            trim_to_budget(qua, "knowledge").text
        )


class TestExceedsBudget:
    def test_bao_dung_khi_vuot(self) -> None:
        assert exceeds_budget(CAU * 2_000, "facts") is True

    def test_bao_dung_khi_chua_vuot(self) -> None:
        assert exceeds_budget("ngắn", "facts") is False

    def test_tang_tool_rong_hon_tang_facts(self) -> None:
        # Ket qua cong cu dai hon fact nhieu; tran phai phan anh dieu do.
        assert TOKEN_BUDGET["tool"] > TOKEN_BUDGET["facts"]
