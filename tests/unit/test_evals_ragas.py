"""Phan THUAN cua khung RAGAS: gop diem, doc phan quyet, dem neo.

Khong goi model, khong cham CSDL. Nhung ham goi model thi khong test o day — cai
dang test la LUAT GOP DIEM, va do la cho de sai lang le nhat: mot chi so gop sai van
in ra mot con so dep va khong ai biet.

Bo eval la mot dung cu do. Dung cu do ma khong ai do lai no thi ta dang tin mot thu
chua duoc kiem chung — dung loi da mac ba lan trong hai ngay 10-11/09/2026 (id chet,
cau hoi mang ten muc vo, cau hoi ky vong 35 chunk).
"""

from agents.ports.llm import ToolCall
from agents.ports.tool import ToolResult
from evals.metrics._cham import doc_phan_quyet, la_thoai_thac
from evals.metrics.answer_relevance import cosine
from evals.metrics.context_precision import average_precision
from evals.runner import (
    _CongCuGhiLai,
    _KenhGom,
    la_cau_fallback,
    neo_trong_ngu_canh,
    trung_binh,
)


class TestAveragePrecision:
    """AP@k phat viec XEP SAI THU TU, khong chi dem."""

    async def test_dung_het_va_xep_dau_thi_tuyet_doi(self) -> None:
        assert average_precision([True, True, True]) == 1.0

    async def test_cung_hai_chunk_dung_nhung_xep_CUOI_thi_diem_thap_hon(self) -> None:
        """Day la ly do dung Average Precision chu khong dung ti le don gian: prompt
        co ngan sach, chunk rac xep tren day chunk dung ra khoi phan bot doc ky.
        """
        tren = average_precision([True, True, False, False, False])
        duoi = average_precision([False, False, False, True, True])

        assert tren == 1.0
        assert duoi < 0.5
        assert tren > duoi

    async def test_khong_co_chunk_nao_lien_quan_thi_0(self) -> None:
        """Mot lan truy hoi hong that, khong phai mot phep chia cho khong."""
        assert average_precision([False, False]) == 0.0

    async def test_danh_sach_rong_thi_0(self) -> None:
        assert average_precision([]) == 0.0


class TestDocPhanQuyet:
    """Doc `1|CO` thanh list[bool]. Doc khong duoc phai tra None, KHONG phai list rong."""

    async def test_doc_duoc_day_du(self) -> None:
        assert doc_phan_quyet("1|CO\n2|KHONG\n3|CO", 3) == [True, False, True]

    async def test_THIEU_mot_dong_thi_tra_None(self) -> None:
        """Doan lay phan con lai se cho ra mot con so trong nhu that. Nguoi cham bo
        qua mot y la mot su co, va no phai duoc dem o cho khac voi diem chat luong.
        """
        assert doc_phan_quyet("1|CO\n3|CO", 3) is None

    async def test_None_khac_han_list_rong(self) -> None:
        """`None` = khong cham duoc. `[]` = khong y nao duoc chung minh (diem 0).
        Gop hai cai lam mot se bien mot su co ha tang thanh mot van de chat luong gia.
        """
        assert doc_phan_quyet("khong doc duoc gi", 2) is None
        assert doc_phan_quyet("", 0) is None

    async def test_dung_SO_THU_TU_chu_khong_dung_thu_tu_xuat_hien(self) -> None:
        """Model hay tra ve cac dong khong dung thu tu. Doc theo thu tu xuat hien thi
        mot dong lac cho lam lech het cac dong sau ma khong ai biet.
        """
        assert doc_phan_quyet("2|KHONG\n1|CO", 2) == [True, False]

    async def test_bo_qua_so_nam_ngoai_pham_vi(self) -> None:
        assert doc_phan_quyet("1|CO\n2|CO\n9|KHONG", 2) == [True, True]

    async def test_chap_nhan_chu_thuong_va_khoang_trang_thua(self) -> None:
        assert doc_phan_quyet("  1 | co  \n2|khong", 2) == [True, False]


class TestThoaiThac:
    """Cau "khong tim thay" la HANH VI DUNG cua bot nay khi kho khong co thong tin.

    RAGAS goc cham 0 cho cau thoai thac. Ap nguyen luat do vao day thi bo eval se
    THUONG cho viec bia ra mot cau tra loi lac de va PHAT cau tra loi trung thuc.
    """

    async def test_nhan_ra_loi_tu_choi_tieng_Viet(self) -> None:
        assert la_thoai_thac("Mình không tìm thấy thông tin này trong tài liệu.") is True
        assert la_thoai_thac("Tài liệu không có thông tin về việc đó.") is True

    async def test_nhan_ra_loi_tu_choi_tieng_Anh(self) -> None:
        assert la_thoai_thac("This is not covered by the documents.") is True

    async def test_KHONG_bat_nham_cau_tra_loi_that(self) -> None:
        """Ca am: mot cau tra loi that bi coi la thoai thac se bi bo ra khoi trung
        binh, va chi so se dep len vi mot loi doc chu khong vi he thong tot hon.
        """
        assert la_thoai_thac("Sữa bí đỏ cần bí đỏ 500g, lá nếp 2 lá và sữa đặc 20ml.") is False
        assert la_thoai_thac("Bake it at 350°F for 30 to 45 minutes.") is False


class TestCosine:
    async def test_hai_vector_trung_nhau(self) -> None:
        assert cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0

    async def test_hai_vector_vuong_goc(self) -> None:
        assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0

    async def test_vector_khong_thi_0_chu_khong_no(self) -> None:
        assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


class TestNeoTrongNguCanh:
    """Phep dem chu, mien phi, khong dung `chunk_id` — luoi an toan cho Context Recall.

    `expected_chunk_ids` CHET moi lan nap lai kho: trong hai ngay 10-11/09/2026 da
    phai anh xa lai hai lan. Cum tu dac trung thi song qua moi lan nap.
    """

    async def test_dem_dung_ti_le(self) -> None:
        assert neo_trong_ngu_canh(["bí đỏ", "lá nếp"], "Bí đỏ 500g, không có gì khác") == 0.5

    async def test_bo_qua_chu_hoa_va_khoang_trang_thua(self) -> None:
        assert neo_trong_ngu_canh(["Bí đỏ: 500g"], "... bí   đỏ:\n500g ...") == 1.0

    async def test_khong_co_neo_thi_None_chu_khong_phai_1(self) -> None:
        """1,0 se noi doi rang cau nay da duoc kiem, trong khi no chua he duoc kiem."""
        assert neo_trong_ngu_canh([], "bat ky noi dung nao") is None


class TestTrungBinh:
    """Trung binh phai NOI RA no da bo qua bao nhieu cau."""

    async def test_bo_qua_None_va_dem_lai(self) -> None:
        assert trung_binh([1.0, 0.0, None]) == (0.5, 1)

    async def test_khong_cau_nao_cham_duoc(self) -> None:
        assert trung_binh([None, None]) == (None, 2)

    async def test_0_van_duoc_tinh_vao_trung_binh(self) -> None:
        """0.0 la "cham va truot", khac han None la "khong cham duoc"."""
        assert trung_binh([0.0, 0.0]) == (0.0, 0)


class TestCongCuGhiLai:
    """Boc `ToolPort` de ghi lai model goi cong cu gi — che do --qua-cong-cu.

    BOC chu khong va de: `Deps.tools` la mot `ToolPort`, tuc mot cho noi da duoc thiet
    ke san. Va de len noi tam cua `tools/registry.py` thi bo eval se gan chat vao chi
    tiet ben trong cua no va vo im lang khi ai do doi chi tiet do.
    """

    @staticmethod
    def _gia(ket_qua: tuple[ToolResult, ...]) -> object:
        class Gia:
            def specs(self) -> tuple[str, ...]:
                return ("spec_gia",)

            async def call_many(self, calls: object, ctx: object) -> tuple[ToolResult, ...]:
                return ket_qua

        return Gia()

    @staticmethod
    def _kq(content: str, ok: bool = True) -> ToolResult:
        return ToolResult(
            tool_call_id="1", name="search_knowledge_base", content=content, ok=ok, latency_ms=1
        )

    async def test_ghi_lai_truy_van_MODEL_TU_VIET(self) -> None:
        """Day la thu che do mac dinh khong nhin thay duoc: model dich cau hoi tieng
        Viet sang tieng Anh TRUOC khi tra. Ban sua 10/09 nam dung o buoc nay.
        """
        ghi = _CongCuGhiLai(self._gia((self._kq("noi dung"),)))  # type: ignore[arg-type]
        goi = (ToolCall(id="1", name="search_knowledge_base", input={"query": "cheese pasta"}),)

        await ghi.call_many(goi, None)  # type: ignore[arg-type]

        assert ghi.goi == [("search_knowledge_base", "cheese pasta")]

    async def test_gom_noi_dung_cong_cu_tra_ve(self) -> None:
        """Day moi la "ngu canh" o che do nay: dung thu model nhin thay, khong phai
        mot ban ghep lai tu chunk.
        """
        ghi = _CongCuGhiLai(self._gia((self._kq("doan mot"), self._kq("doan hai"))))  # type: ignore[arg-type]

        await ghi.call_many((), None)  # type: ignore[arg-type]

        assert ghi.ket_qua == ["doan mot", "doan hai"]

    async def test_KHONG_gom_ket_qua_that_bai(self) -> None:
        """Cong cu loi thi `content` la thong bao loi. Dua no vao ngu canh roi bat
        nguoi cham doi chieu cau tra loi voi mot thong bao loi la vo nghia.
        """
        ghi = _CongCuGhiLai(self._gia((self._kq("loi roi", ok=False),)))  # type: ignore[arg-type]

        await ghi.call_many((), None)  # type: ignore[arg-type]

        assert ghi.ket_qua == []

    async def test_chuyen_tiep_specs_nguyen_ven(self) -> None:
        """Doi danh sach cong cu la doi hanh vi model — bo boc phai trong suot."""
        ghi = _CongCuGhiLai(self._gia(()))  # type: ignore[arg-type]

        assert ghi.specs() == ("spec_gia",)


class TestKenhGom:
    async def test_gom_nhieu_lan_gui_thanh_mot_cau_tra_loi(self) -> None:
        kenh = _KenhGom()

        await kenh.send(None, "phan mot. ")  # type: ignore[arg-type]
        await kenh.send(None, "phan hai.")  # type: ignore[arg-type]

        assert kenh.text == "phan mot. phan hai."

    async def test_KHONG_cat_tin_theo_gioi_han_nen_tang(self) -> None:
        """Cat theo gioi han cua Zalo se lam nguoi cham thay mot cau cut duoi, va
        cham no la thieu can cu.
        """
        assert _KenhGom.max_message_chars > 100_000


class TestNhanRaCauFallback:
    """Luot KHONG CHAY duoc phai bi dem rieng, khong duoc cham nhu cau tra loi te.

    Da xay ra that 11/09/2026: `DAILY_BUDGET_USD=2` can giua lan chay 52 cau, va 27
    cau LIEN TIEP tu g026 den het deu nhan cau xin loi mac dinh. Bao cao in ra:

        Context Recall      0,438
        giao_tap_hop        0,000
        xuyen_ngon_ngu      0,000

    Trong y het mot hoi quy tham khoc. Khong co gi hong ca — chi la het tien. Mot bo
    eval bao dong gia theo kieu do con nguy hiem hon khong co bo eval: no se lam nguoi
    ta di "sua" mot thu dang chay dung.
    """

    async def test_nhan_ra_cau_xin_loi_mac_dinh(self) -> None:
        from agents.pipeline.stages.generate import FALLBACK_TEXT

        assert la_cau_fallback(FALLBACK_TEXT) is True

    async def test_nhan_ra_ca_khi_co_duoi_CHUA_DAY_DU(self) -> None:
        """`_finish()` noi INCOMPLETE_SUFFIX vao duoi khi dung giua chung, nen so sanh
        ca chuoi se truot.
        """
        from agents.pipeline.stages.generate import FALLBACK_TEXT, INCOMPLETE_SUFFIX

        assert la_cau_fallback(FALLBACK_TEXT + INCOMPLETE_SUFFIX) is True

    async def test_nhan_ra_cau_loi_cau_hinh(self) -> None:
        from agents.pipeline.stages.generate import CONFIG_ERROR_TEXT

        assert la_cau_fallback(CONFIG_ERROR_TEXT) is True

    async def test_KHONG_bat_nham_cau_tra_loi_that(self) -> None:
        """Ca am: mot cau tra loi that bi coi la fallback se bien mat khoi moi chi so,
        va diem se DEP LEN vi mot loi doc chu khong vi he thong tot hon.
        """
        assert la_cau_fallback("Sữa bí đỏ cần bí đỏ 500g và lá nếp 2 lá.") is False
        assert la_cau_fallback("Xin lỗi, tài liệu không nói rõ chỗ này.") is False
