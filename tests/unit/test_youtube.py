"""Công cụ `youtube_stats`.

Bộ test này chốt hai thứ, và cái thứ hai mới là cái quan trọng:

  1. Đọc được ID từ mọi dạng link YouTube.
  2. **Nói đúng về thứ không có.** Người đăng ẩn lượt thích thì API không trả trường
     đó — khác hẳn "bằng 0". Và số lượt không thích thì YouTube đã gỡ khỏi API từ
     12/2021. Gộp hai trường hợp đó thành một con số là dạy model bịa, mà một con số
     bịa thì trông y hệt một con số thật.

Không chạm mạng: bơm phản hồi giả đúng hình dạng API trả về.
"""

from typing import Any

import pytest

from tools.youtube import (
    YOUTUBE_STATS_DEFINITION,
    run_youtube_stats,
    tach_id,
)

ID = "dQw4w9WgXcQ"


class TestDocLink:
    @pytest.mark.parametrize(
        "link",
        [
            f"https://www.youtube.com/watch?v={ID}",
            f"https://youtu.be/{ID}",
            f"https://www.youtube.com/shorts/{ID}",
            f"https://www.youtube.com/embed/{ID}",
            f"https://www.youtube.com/live/{ID}",
            f"https://m.youtube.com/watch?v={ID}&t=42s",
            f"https://www.youtube.com/watch?list=PL123&v={ID}",
            ID,
        ],
    )
    async def test_moi_dang_link_deu_ra_dung_id(self, link: str) -> None:
        assert tach_id(link) == ID

    async def test_id_tran_van_nhan(self) -> None:
        """Người dùng hay dán mỗi cái ID. Bắt họ dán URL đầy đủ là bắt họ làm việc cho máy."""
        assert tach_id(f"  {ID}  ") == ID

    @pytest.mark.parametrize(
        "khong_phai", ["https://vimeo.com/12345", "khong phai link", "", "https://youtube.com/"]
    )
    async def test_khong_nhan_ra_thi_tra_None_chu_KHONG_doan(self, khong_phai: str) -> None:
        """Đoán bừa một ID sẽ nhận về danh sách rỗng, và "không tìm thấy video" là một
        câu trả lời SAI cho một cái link viết đúng.
        """
        assert tach_id(khong_phai) is None


def phan_hoi(monkeypatch: pytest.MonkeyPatch, body: dict[str, Any], status: int = 200) -> None:
    import httpx

    from tools import youtube

    class Client:
        async def get(self, url: str, params: Any = None, timeout: float = 0) -> httpx.Response:
            return httpx.Response(status, json=body)

    monkeypatch.setattr(youtube, "get_http", lambda: Client())


def video(**thong_ke: str) -> dict[str, Any]:
    return {
        "id": ID,
        "snippet": {
            "title": "Bai hat thu nghiem",
            "channelTitle": "Kenh Thu",
            "publishedAt": "2009-10-25T06:57:33Z",
        },
        "statistics": thong_ke,
    }


class TestSoLieu:
    async def test_tra_ve_du_bon_con_so(self, monkeypatch: pytest.MonkeyPatch) -> None:
        phan_hoi(
            monkeypatch,
            {
                "items": [
                    video(
                        viewCount="1500000000",
                        likeCount="17000000",
                        commentCount="2300000",
                    )
                ]
            },
        )

        ra = await run_youtube_stats({"video": f"https://youtu.be/{ID}"}, "tr")

        assert "Bai hat thu nghiem" in ra
        assert "Kenh Thu" in ra
        assert "2009-10-25" in ra
        assert "1.500.000.000" in ra  # dấu chấm phân cách, đọc được trong khung chat
        assert "17.000.000" in ra
        assert "2.300.000" in ra

    async def test_luot_thich_BI_AN_khac_han_bang_khong(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ca quan trong nhat cua ca cong cu.

        Nguoi dang co quyen an luot thich. Khi do API khong tra truong `likeCount` —
        neu doc thanh 0 thi bot se noi "video nay co 0 luot thich", mot cau SAI voi
        day du ve tu tin.
        """
        phan_hoi(monkeypatch, {"items": [video(viewCount="1000", commentCount="5")]})

        ra = await run_youtube_stats({"video": ID}, "tr")

        assert "DA AN" in ra
        assert "dung doan" in ra
        assert "Luot thich: 0" not in ra

    async def test_binh_luan_bi_tat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        phan_hoi(monkeypatch, {"items": [video(viewCount="1000", likeCount="10")]})

        ra = await run_youtube_stats({"video": ID}, "tr")

        assert "da tat hoac bi an" in ra

    async def test_luon_nhac_day_la_anh_chup_va_khong_co_dislike(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hai câu này đi kèm MỌI kết quả, vì model sẽ tự lấp chỗ trống nếu không có.

        Số dislike trên mạng đều là ước lượng của bên thứ ba; đưa nó ra như số thật là
        đúng cái mà luật "không bịa" cấm.
        """
        phan_hoi(monkeypatch, {"items": [video(viewCount="1", likeCount="1")]})

        ra = await run_youtube_stats({"video": ID}, "tr")

        assert "THOI DIEM TRA CUU" in ra
        assert "12/2021" in ra


class TestNhanhHong:
    async def test_link_sai_thi_noi_KHONG_DOC_DUOC_LINK(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Khác hẳn "không tìm thấy video" — hai câu dẫn người dùng đi hai hướng."""
        ra = await run_youtube_stats({"video": "https://vimeo.com/12345"}, "tr")

        assert "Khong doc duoc ID" in ra
        assert "dung doan noi dung video" in ra

    async def test_video_rieng_tu_hoac_da_xoa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        phan_hoi(monkeypatch, {"items": []})

        ra = await run_youtube_stats({"video": ID}, "tr")

        assert "Khong tim thay video" in ra
        assert "dung suy doan" in ra

    async def test_mot_trong_nhieu_id_khong_quay_ve_thi_phai_NOI_RA(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Im lặng bỏ qua sẽ làm người dùng tưởng bot đã tra cứu đủ."""
        phan_hoi(monkeypatch, {"items": [video(viewCount="10", likeCount="1")]})

        ra = await run_youtube_stats({"video": f"{ID},aaaaaaaaaaa"}, "tr")

        assert "aaaaaaaaaaa" in ra
        assert "rieng tu hoac da xoa" in ra

    async def test_API_loi_thi_NEM(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Hết hạn mức phải nổ ra ngoài để registry ghi log và model nói không tra được."""
        phan_hoi(monkeypatch, {"error": {"message": "quota"}}, status=403)

        with pytest.raises(RuntimeError):
            await run_youtube_stats({"video": ID}, "tr")

    async def test_thieu_tham_so(self) -> None:
        with pytest.raises(ValueError):
            await run_youtube_stats({}, "tr")

    async def test_tham_so_rong(self) -> None:
        with pytest.raises(ValueError):
            await run_youtube_stats({"video": "   "}, "tr")


class TestKhaiBao:
    async def test_mo_ta_noi_ro_KHONG_tim_duoc_theo_TU_KHOA(self) -> None:
        """Model đọc dòng này để chọn công cụ. Không nói rõ thì nó sẽ gọi youtube_stats
        cho câu "tìm video về nấu ăn" và nhận về một lỗi.
        """
        assert "KHÔNG tìm được video theo từ khoá" in YOUTUBE_STATS_DEFINITION.description

    async def test_mo_ta_BAT_model_doi_chieu_sau_khi_web_search(self) -> None:
        """Bản mô tả đầu tiên viết là "dùng khi người dùng đưa link hoặc ID", và chạy
        thật cho thấy model hiểu đúng theo nghĩa đen: hỏi "top video nhiều like nhất"
        thì nó gọi web_search, lấy số từ blog xếp hạng, rồi DỪNG — dù có sẵn công cụ
        đọc số thật.

        Model đọc mô tả để quyết định, nên mô tả viết hẹp là tự tay tắt mất một luồng.
        """
        mo_ta = YOUTUBE_STATS_DEFINITION.description
        assert "web_search" in mo_ta
        assert "CŨ" in mo_ta  # nói rõ vì sao phải đối chiếu

    async def test_mo_ta_bao_truoc_ve_dislike(self) -> None:
        """Rẻ hơn là để model tự phát hiện sau khi đã hứa với người dùng."""
        assert "12/2021" in YOUTUBE_STATS_DEFINITION.description

    async def test_schema_chan_tham_so_la(self) -> None:
        assert YOUTUBE_STATS_DEFINITION.parameters["additionalProperties"] is False

    async def test_khai_ro_can_khoa_nao(self) -> None:
        assert YOUTUBE_STATS_DEFINITION.requirements.api_key == "YOUTUBE_API_KEY"
