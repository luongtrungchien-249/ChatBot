import pytest

from shared.chunk_text import chunk_text, truncate_at_boundary

DOAN = "Cau mot rat dai o day. Cau hai cung dai khong kem.\n\nDoan sau bat dau tu day."


class TestChunkText:
    @pytest.mark.parametrize("max_chars", [5, 10, 17, 30, 100])
    def test_bat_bien_ghep_lai_bang_ban_goc(self, max_chars: int) -> None:
        assert "".join(chunk_text(DOAN, max_chars)) == DOAN

    @pytest.mark.parametrize("max_chars", [5, 10, 17, 30])
    def test_khong_chunk_nao_vuot_max_chars(self, max_chars: int) -> None:
        for chunk in chunk_text(DOAN, max_chars):
            assert len(chunk) <= max_chars

    def test_van_ban_ngan_hon_cap_tra_ve_nguyen_mot_manh(self) -> None:
        assert chunk_text("ngan", 100) == ["ngan"]

    def test_van_ban_rong_tra_ve_mang_rong(self) -> None:
        assert chunk_text("", 100) == []

    def test_uu_tien_cat_o_ranh_gioi_doan_van(self) -> None:
        assert chunk_text(DOAN, 60)[0] == "Cau mot rat dai o day. Cau hai cung dai khong kem.\n\n"

    def test_khong_co_doan_van_thi_cat_o_ranh_gioi_cau(self) -> None:
        text = "Cau mot o day. Cau hai o day. Cau ba o day."
        assert chunk_text(text, 20)[0] == "Cau mot o day. "

    @pytest.mark.parametrize("max_chars", [11, 13, 16])
    def test_khong_vo_tu_khi_con_cho_cat(self, max_chars: int) -> None:
        chunks = chunk_text("alpha beta gamma delta", max_chars)
        # Moi manh TRU MANH CUOI phai ket thuc bang khoang trang.
        for chunk in chunks[:-1]:
            assert chunk.endswith((" ", "\n"))

    def test_mot_tu_dai_hon_cap_thi_cat_cung(self) -> None:
        text = "a" * 20
        assert chunk_text(text, 6) == ["aaaaaa", "aaaaaa", "aaaaaa", "aa"]
        assert "".join(chunk_text(text, 6)) == text

    def test_max_chars_khong_duong_thi_nem_loi(self) -> None:
        with pytest.raises(ValueError):
            chunk_text("abc", 0)


class TestTruncateAtBoundary:
    def test_ngan_hon_cap_thi_giu_nguyen(self) -> None:
        assert truncate_at_boundary("ngan", 100) == "ngan"

    def test_cat_o_ranh_gioi_va_luon_la_tien_to(self) -> None:
        kept = truncate_at_boundary(DOAN, 30)
        assert len(kept) <= 30
        assert DOAN.startswith(kept)
