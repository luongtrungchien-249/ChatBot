"""Cong cu `search_knowledge_base` — phan model doc va phan model nhan lai.

Khong I/O: cai gia cho KnowledgePort la du, va do la ly do ton tai cua ports.
"""

from typing import Any

import pytest

from agents.domain.knowledge import RetrievedChunk
from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext
from tools import knowledge_search
from tools.knowledge_search import (
    KNOWLEDGE_SEARCH_DEFINITION,
    is_knowledge_search_available,
    run_knowledge_search,
)

#: Moi lan `knowledge.search` duoc goi: (truy_van, k). Xem fixture `kho`.
da_goi: list[tuple[str, int]] = []

#: Pham vi di cung moi lan goi cong cu, y het hop dong cua memory_fact.
CTX = CallContext(
    scope=ThreadScope(platform="cli", thread_id="t1"), sender_id="u1", trace_id="tr"
)


def chunk(
    content: str,
    section: str | None = "Chinh sach hoan tien",
    distance: float | None = 0.2,
    chunk_id: str = "1",
) -> RetrievedChunk:
    """Mac dinh distance=0,2 — tuc CHAC. Test nao muon nhanh hoi lai thi tu dat cao."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_title="So tay nhan vien 2026",
        section=section,
        page=None,
        content=content,
        score=0.9,
        distance=distance,
    )


@pytest.fixture
def kho(monkeypatch: pytest.MonkeyPatch) -> list[RetrievedChunk]:
    """Thay KnowledgePort that bang mot cai gia, tra ve danh sach do test dat vao."""
    ket_qua: list[RetrievedChunk] = []
    da_goi.clear()

    class KhoGia:
        async def search(
            self, scope: ThreadScope, query: str, k: int
        ) -> list[RetrievedChunk]:
            # Ghi lai de test kiem duoc lan tra SAU co doi truy van va noi rong k khong.
            da_goi.append((query, k))
            return ket_qua

    import knowledge.retrieve.service as service

    monkeypatch.setattr(service, "knowledge", KhoGia())
    return ket_qua


class TestKhaiBao:
    async def test_mo_ta_noi_ro_khi_nao_KHONG_dung(self) -> None:
        """Model doc dong nay de chon cong cu. Chi noi "tim tai lieu" thi no se goi
        ca khi nguoi dung hoi gia bitcoin.
        """
        assert "web_search" in KNOWLEDGE_SEARCH_DEFINITION.description

    async def test_khong_khai_khi_chua_co_tai_lieu(self) -> None:
        """Cho model thay mot cong cu roi de no tra ve rong lien tuc la day no bia."""
        knowledge_search._has_documents = False
        assert is_knowledge_search_available() is False

    async def test_khai_khi_da_co_tai_lieu(self) -> None:
        knowledge_search._has_documents = True
        assert is_knowledge_search_available() is True

    async def test_schema_chan_tham_so_la(self) -> None:
        assert KNOWLEDGE_SEARCH_DEFINITION.parameters["additionalProperties"] is False


class TestMoTaNoiDungKho:
    """Mo ta cong cu la CODE, khong phai chu thich — model doc no de quyet dinh.

    Ban dau mo ta viet kho la "tai lieu noi bo cua to chuc: quy dinh, quy trinh,
    chinh sach" va bao dung "TRUOC khi tra loi cau hoi ve cach to chuc nay lam viec".
    Do duoc tren bot that: hoi "Ga ham bi do can nguyen lieu gi" — mot mon CO trong
    kho — model KHONG goi cong cu nay lan nao, vi cau hoi khong giong "cach to chuc
    lam viec". No tra loi tu tri nho, khong nguon.

    Sau khi mo ta noi ro kho co the chua BAT KY loai tai lieu nao va model khong biet
    trong do co gi cho toi khi tra: 6/6 nhom do deu dat.
    """

    async def test_khong_bo_hep_kho_vao_moi_tai_lieu_quan_tri(self) -> None:
        mo_ta = KNOWLEDGE_SEARCH_DEFINITION.description
        assert "BẤT KỲ" in mo_ta

    async def test_noi_ro_model_KHONG_BIET_trong_kho_co_gi(self) -> None:
        assert "KHÔNG BIẾT TRONG KHO CÓ GÌ" in KNOWLEDGE_SEARCH_DEFINITION.description

    async def test_bat_tra_TRUOC_khi_tra_loi_tu_tri_nho(self) -> None:
        mo_ta = KNOWLEDGE_SEARCH_DEFINITION.description
        assert "TRƯỚC" in mo_ta
        assert "trí nhớ" in mo_ta


class TestBatGoiCongCu:
    """Mo ta phai lam model GOI cong cu — do dau-cuoi 10/09/2026: 1/4 -> 4/4.

    Truoc do menh lenh "goi cong cu TRUOC khi tra loi" nam o GIUA doan mo ta, va dieu
    kien buoc theo SU TU TIN cua model ("ke ca cau ban nghi minh da biet dap an").
    Ca hai deu hong voi cung mot lop cau hoi:

        cau TRA CUU      ("Ga ham bi do can nguyen lieu gi")   4/4 co goi cong cu
        cau GIAO TAP HOP ("Mon nao co pho mai va mi ong")      1/4 co goi cong cu

    Model tra loi thang tu tri nho, khong nguon, va tung cai ten no ke deu la mon co
    that tren doi — chi khong phai mon trong kho cua nguoi dung. Dieu kien theo su tu
    tin tu vo hieu dung luc can nhat, vi voi loai cau nay model LUON tu tin.

    Ba thay doi, do rieng: menh lenh len cau dau, goi ten cam bay "hoi tu dac diem ra
    ten", va mot vi du cu the. Chi them luat ma van de menh lenh o giua: 2/4. Dua len
    dau: 4/4, va ca bon deu lay dung chunk dap an.

    LUU Y cho nguoi sua sau: vi du trong mo ta CO Y dung mot cap nguyen lieu khong
    nam trong bo cau do. Doi no thanh dung cau dang do la day vet, va con so sau do
    khong con do duoc gi.
    """

    @property
    def mo_ta(self) -> str:
        return KNOWLEDGE_SEARCH_DEFINITION.description

    async def test_menh_lenh_nam_o_CAU_DAU_chu_khong_giua_doan(self) -> None:
        """Thu tu cau la mot nua tac dung, khong phai gia vi: cung luat do dat o giua
        chi duoc 2/4, dua len dau duoc 4/4.
        """
        assert "GỌI CÔNG CỤ NÀY TRƯỚC KHI TRẢ LỜI" in self.mo_ta
        # Trong 200 ky tu dau, tuc truoc phan mo ta kho co nhung gi.
        assert self.mo_ta.index("GỌI CÔNG CỤ NÀY TRƯỚC KHI TRẢ LỜI") < 200

    async def test_KHONG_buoc_dieu_kien_theo_su_tu_tin_cua_model(self) -> None:
        """"ke ca cau ban nghi minh da biet dap an" tu vo hieu dung luc can nhat."""
        assert "Không có ngoại lệ" in self.mo_ta
        assert "giống kiến thức phổ thông" in self.mo_ta

    async def test_goi_ten_cam_bay_CAU_HOI_NGUOC(self) -> None:
        assert "NGƯỢC" in self.mo_ta
        assert "từ đặc điểm ra tên" in self.mo_ta

    async def test_co_VI_DU_cu_the_va_KHONG_lay_cau_dang_do(self) -> None:
        """Vi du day manh hon luat — nhung vi du trung cau dang do thi la day vet."""
        assert "đậu phụ" in self.mo_ta and "cà chua" in self.mo_ta
        for cap in ("phô mai", "mì ống", "cá ngừ", "sô cô la", "bơ đậu phộng"):
            assert cap not in self.mo_ta, cap


class TestNgonNguTruyVan:
    """Truy van phai viet bang TIENG ANH. Do that 10/09/2026: 2/6 -> 5/6.

    Mo ta tham so cu bao model "viet bang tieng Viet nhu nguoi dung da hoi". Model
    lam dung nhu duoc bao, va nua kho tai lieu tro nen VO HINH:

        Dap an nam o sach song ngu Viet-Anh   4/4 dung
        Dap an nam o sach thuan tieng Anh     0/4 dung

    Hoi DUNG CAU DO bang tieng Anh thi tim ra ngay. Nhin tang vector TRUOC rerank
    voi cau hoi tieng Viet "Mon nao dung pho mai va mi ong": khong MOT mon tieng Anh
    nao lot vao top 10, va duong lexical rong. Tuc rerank chua bao gio duoc NHIN THAY
    dap an dung — loi o tang TRUY HOI, khong phai tang xep hang. Nguyen nhan: embedding
    bi chi phoi boi NGON NGU chu khong phai noi dung, mot cau tieng Viet nam gan MOI
    van ban tieng Viet hon la gan van ban tieng Anh dung nghia.

    Do ba bien the truy van tren cung 6 cau giao tap hop:

        tieng Viet (cu)          2/6
        tieng Anh                5/6
        tron Viet + Anh mot chuoi 4/6   <- vector chuoi lai nam lung chung hai cum

    Nen co ca hai luat: viet tieng Anh, VA dung tron hai thu tieng trong mot chuoi.

    Cac test duoi day ton tai de chan viec ai do "sua lai cho nhat quan" ve tieng
    Viet. Dong mo ta do khong phai tuy hung.

    Luat nay PHU THUOC CORPUS va se dao nguoc khi kho thanh chu yeu tieng Viet —
    dieu kien het han ghi ngay trong knowledge_search.py, canh chinh tham so.

    DO LAI DAU-CUOI 10/09/2026 — VA NEN 2/6 CUA PLAN KHONG TAI LAP DUOC
    --------------------------------------------------------------------------
    Chay 6 cau tren qua handle_message() that (kho that: 179 chunk, 2 tai lieu),
    dap an chuan dung lai tu CSDL bang ranh gioi tu. Doi RIENG dong mo ta nay:

        mo ta CU (tieng Viet)  0/6
        mo ta MOI (tieng Anh)  0/6

    Ca hai 0/6 vi mot ly do CHUNG nam TREN thay doi nay: model phan lon khong goi
    search_knowledge_base lan nao cho cau hoi dang "mon nao co X va Y" — xem
    TestBatGoiCongCu. Nen con so 2/6 trong plan gia dinh cong cu LUON duoc goi, va
    gia dinh do khong dung. Phai sua ca hai thi con so moi nhuc nhich.

    Sau khi sua CA HAI (mo ta cong cu + mo ta tham so), do lai tren cung bo cau:

        dung dap an chuan   5/6      (nguong muc 7 cua plan: >= 5/6)
        co goi cong cu      6/6
        nhom tra cuu        4/4      hang chong hoi quy, khong tut

    Truy van model sinh ra, chep tu log that — tieng Anh, ten rieng nguyen ven:

        "Andrew's Macaroni with Bacon & Green Onion ingredients"
        "recipe 'oc om chuoi dau' braised snails with banana and tofu recipe"
        "Which dishes use bacon and scallions (green onions)?"

    Cau con truot la "pho mai + mi ong": model viet `pasta` thay cho `macaroni`, rong
    hon mot bac, va chunk `Andrew's Macaroni` rot khoi top 5. DA THU sua bang mot cau
    luat "giu dung muc cu the" va DA HOAN LAI — no keo 4/6 xuong 2/6 vi model chuyen
    sang chen tieng Viet vao truy van. Chi tiet ghi trong knowledge_search.py.
    """

    @property
    def mo_ta(self) -> str:
        thuoc_tinh: Any = KNOWLEDGE_SEARCH_DEFINITION.parameters["properties"]
        return str(thuoc_tinh["query"]["description"])

    async def test_bat_viet_truy_van_bang_TIENG_ANH(self) -> None:
        assert "VIẾT BẰNG TIẾNG ANH" in self.mo_ta

    async def test_KHONG_con_bao_viet_bang_tieng_Viet(self) -> None:
        """Hoi quy that ma test nay chan: mot dong mo ta bao model viet tieng Viet
        lam nua kho tai lieu vo hinh, va khong loi nao bao ra.
        """
        assert "viết bằng tiếng Việt" not in self.mo_ta

    async def test_neu_LY_DO_chu_khong_chi_ra_lenh(self) -> None:
        """Model tuan mot lenh CO LY DO tot hon lenh tran — cung luat da dung cho
        thong diep "khong tim thay" va cho mo ta cong cu.
        """
        assert "Lý do:" in self.mo_ta
        assert "phần lớn là tiếng Anh" in self.mo_ta

    async def test_giu_nguyen_ma_so_va_ten_rieng(self) -> None:
        """Dich "QD-145/2026" hay ten rieng la lam hong dung thu giup tim ra tai
        lieu — do la tin hieu manh nhat cua duong BM25.
        """
        assert "KHÔNG DỊCH" in self.mo_ta
        assert "QD-145/2026" in self.mo_ta
        assert "tên riêng" in self.mo_ta

    async def test_bat_truy_van_NGAN_va_khong_nhet_menh_lenh(self) -> None:
        """Do trong mot phien hai luot: cung cau hoi, chi khac do dai truy van.

            "Which dishes contain cheese and pasta?"                    d=0,5619
            "... ? Provide common dish names ..., list up to 10."       d=0,6223
            "... ? List common dishes that combine cheese and pasta."   d=0,6336

        Con so cuoi vuot ca RAG_MAX_DISTANCE, tuc tra ve RONG — bot quay sang web va
        tra loi bang kien thuc chung, trong khi dap an van nam trong CSDL.
        """
        assert "NGẮN" in self.mo_ta
        assert "Đừng thêm chỉ dẫn cho công cụ" in self.mo_ta

    async def test_cam_tron_hai_thu_tieng_trong_mot_chuoi(self) -> None:
        """4/6 — kem hon tieng Anh thuan. Khong phai luat thua: "giu nguyen ten
        rieng" rat de bi hieu thanh "viet ca cau bang ca hai thu tieng".
        """
        assert "đừng viết CẢ CÂU bằng hai thứ tiếng" in self.mo_ta

    async def test_ghi_dieu_kien_HET_HAN_ngay_trong_code(self) -> None:
        """Nguoi sua code doc CODE truoc, khong doc docs/. Luat nay dao nguoc khi
        corpus thanh chu yeu tieng Viet, nen dieu kien do phai nam canh chinh no.
        """
        from pathlib import Path

        nguon = Path(knowledge_search.__file__).read_text(encoding="utf-8")
        assert "PHU THUOC CORPUS" in nguon
        assert "DAO NGUOC" in nguon


class TestNguoiTrongVongLap:
    """Tim CHUNG CHUNG thi khong doan bua — dua ung vien co that ra cho nguoi dung chon.

    Vi sao can: cau "Mon nao dung pho mai va mi ong" duoc model dich thanh "dishes
    that use cheese and pasta". Truy hoi tra ve mot mo mon co dinh dang pasta, khong
    mon nao la dap an, va bot van tra loi nhu that. Truot IM LANG — nguoi dung khong
    co cach nao biet ket qua chi la "gan gan".

    Tin hieu la KHOANG CACH cosine, khong phai diem rerank: o che do du phong diem la
    ti le tu trung nen khong so duoc voi nguong co dinh. Do 10/09/2026 tren kho that,
    khoang cach cua ung vien gan nhat:

        hoi thang mot muc co ten     0,2468  0,2613  0,2810  0,3499
        hoi chung chung / mo ho      0,3504  0,4658  0,5061  0,5629  0,5625  0,5960

    Nguong 0,50 (RAG_HOI_LAI_TU) nam trong khoang trong 0,466-0,506 cua mau nay.
    """

    async def test_CHAC_thi_tra_ve_noi_dung_chu_KHONG_hoi(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """Duong thuong phai khong doi. Hoi lai khi da chac la mot luot lang phi."""
        kho.append(chunk("Don hoan tien xu ly trong 7 ngay.", distance=0.21))
        kho.append(chunk("Muc khac.", section="Doi tra", distance=0.30, chunk_id="2"))

        out = await run_knowledge_search({"query": "hoan tien"}, CTX)

        assert "7 ngay" in out
        assert "KẾT QUẢ KHÔNG CHẮC" not in out

    async def test_CHUNG_CHUNG_thi_dua_danh_sach_de_nguoi_dung_chon(
        self, kho: list[RetrievedChunk]
    ) -> None:
        kho.append(chunk("A", section="Pasta trong lo vi song", distance=0.56))
        kho.append(chunk("B", section="Goulash cua Kristin", distance=0.58, chunk_id="2"))

        out = await run_knowledge_search({"query": "cheese and pasta"}, CTX)

        assert "KẾT QUẢ KHÔNG CHẮC" in out
        assert "1. Pasta trong lo vi song" in out
        assert "2. Goulash cua Kristin" in out


class TestHaiNhanhCuaDanhSachHoiLai:
    """Danh sach hoi lai co KEM TRICH DOAN, va model chon mot trong hai nhanh.

    Ban dau danh sach chi co TEN, kem mot cau cam thang: "ĐỪNG trả lời bằng nội dung
    các mục này". Ly do luc do hop ly — dua ca noi dung ra thi model se tu chon lay
    mot muc roi tra loi, tuc vong hoi lai thanh vo nghia.

    Nhung do dau-cuoi 11/09/2026 cho thay cai cam do lam hong ca mot lop cau hoi:

        "Lam sao cho chuoi xanh bot chat?"
        -> bot tra ve danh sach 8 MON AN va hoi nguoi dung chon mot mon

    Nguoi dung hoi mot KY THUAT. Ca 8 muc deu tra loi giong nhau — ngam chanh va giam
    — nen bat ho chon mot mon la hoi sai thu. Va model KHONG THE nhan ra dieu do, vi
    no chi nhin thay TEN.

    Nen bay gio danh sach kem trich doan (`_TRICH_DOAN` ky tu moi muc), va ket qua
    cong cu neu ro hai nhanh:

        CO    cac muc cung noi mot dieu  -> TRA LOI LUON, neu nguon, dung hoi
        KHONG moi muc mot dap an rieng   -> dua danh sach ra hoi, KHONG kem trich doan

    Do sau khi sua, cau tren: bot tra loi dung dap an chuan kem hai ten muc lam nguon,
    thay vi mot danh sach mon an. Cau "Mon nao dung pho mai va mi ong" van ra danh
    sach nhu cu — hai nhanh khong dam nhau.

    CANH BAO cho nguoi sua sau: viec chon nhanh la do MODEL quyet, khong tat dinh. Do
    lai hai luot tren cung cau: mot luot tra loi thang, mot luot hoi lai mot cau khac.
    Dung mong doi mot nhanh co dinh cho mot cau hoi co dinh.
    """

    async def test_kem_TRICH_DOAN_de_model_thay_cac_muc_co_giong_nhau_khong(
        self, kho: list[RetrievedChunk]
    ) -> None:
        kho.append(chunk("Ngam voi chanh va giam.", section="Muc mot", distance=0.56))
        kho.append(chunk("Cung ngam chanh giam.", section="Muc hai", distance=0.58, chunk_id="2"))

        out = await run_knowledge_search({"query": "bot chat"}, CTX)

        assert "Ngam voi chanh va giam." in out
        assert "Cung ngam chanh giam." in out

    async def test_neu_ro_CA_HAI_nhanh(self, kho: list[RetrievedChunk]) -> None:
        """Chi neu nhanh hoi lai thi ta quay ve dung cai bay cu."""
        kho.append(chunk("A", section="Muc mot", distance=0.56))
        kho.append(chunk("B", section="Muc hai", distance=0.58, chunk_id="2"))

        out = await run_knowledge_search({"query": "x"}, CTX)

        assert "TRẢ LỜI LUÔN" in out
        assert "ĐỪNG hỏi lại" in out
        assert "DỪNG lượt này" in out

    async def test_nhanh_hoi_lai_van_cam_kem_trich_doan_khi_TRA_LOI_nguoi_dung(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """Trich doan la de MODEL doc, khong phai de do het len man hinh nguoi dung."""
        kho.append(chunk("A", section="Muc mot", distance=0.56))
        kho.append(chunk("B", section="Muc hai", distance=0.58, chunk_id="2"))

        out = await run_knowledge_search({"query": "x"}, CTX)

        assert "KHÔNG kèm trích đoạn" in out

    async def test_ca_hai_nhanh_deu_cam_tra_loi_tu_tri_nho(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """Nhanh CO mo duong cho model tra loi — khong duoc de no thanh duong tat ve
        lai viec tra loi tu tri nho.
        """
        kho.append(chunk("A", section="Muc mot", distance=0.56))
        kho.append(chunk("B", section="Muc hai", distance=0.58, chunk_id="2"))

        out = await run_knowledge_search({"query": "x"}, CTX)

        assert "KHÔNG được trả lời từ trí nhớ" in out

    async def test_luon_co_dong_KHAC_o_cuoi_danh_sach(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """Danh sach khong co duong ra la mot cai bay: nguoi dung buoc phai chon mot
        muc sai roi nhan ve mot cau tra loi sai mot cach tu tin hon truoc.
        """
        kho.append(chunk("A", section="Muc mot", distance=0.56))
        kho.append(chunk("B", section="Muc hai", distance=0.58, chunk_id="2"))

        out = await run_knowledge_search({"query": "x"}, CTX)

        assert "3. Khác — không phải mục nào ở trên" in out

    async def test_danh_sach_KHONG_lap_ten_muc(self, kho: list[RetrievedChunk]) -> None:
        """Mot muc bi cat thanh nhieu chunk la chuyen binh thuong. Hien ba dong cung
        ten thi nguoi dung tuong do la ba thu khac nhau.
        """
        kho.append(chunk("A", section="Muc mot", distance=0.56))
        kho.append(chunk("A2", section="Muc mot", distance=0.57, chunk_id="2"))
        kho.append(chunk("B", section="Muc hai", distance=0.58, chunk_id="3"))

        out = await run_knowledge_search({"query": "x"}, CTX)

        assert out.count("Muc mot") == 1
        assert "3. Khác" in out

    async def test_MOT_ung_vien_VAN_hoi(self, kho: list[RetrievedChunk]) -> None:
        """Hoi quy that. Ban dau co luat "duoi hai ung vien thi khong hoi", va no sai
        theo mot kieu tu che giau: truy van cang mo ho thi cang IT doan qua duoc
        RAG_MAX_DISTANCE, nen dung luc can hoi nhat lai la luc chi con mot ung vien.

        Do that: truy van dai dong model sinh ra cho d=0,6223 va DUNG MOT doan song
        sot — va luat cu lam ca tinh nang im lang khong chay.
        """
        kho.append(chunk("A", section="Muc duy nhat", distance=0.9))

        out = await run_knowledge_search({"query": "x"}, CTX)

        assert "KẾT QUẢ KHÔNG CHẮC" in out
        assert "1. Muc duy nhat" in out
        assert "2. Khác — không phải mục nào ở trên" in out

    async def test_gom_ung_vien_RONG_hon_khi_phai_hoi(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """Top-5 cua mot truy van mo ho thuong bo sot dung thu nguoi dung dinh hoi.
        Do that: "dishes that use cheese and pasta" o k=5 cho 5 muc khong co dap an
        nao, o k=12 keo duoc CA HAI dap an dung vao danh sach.
        """
        kho.append(chunk("A", section="Muc mot", distance=0.56))
        kho.append(chunk("B", section="Muc hai", distance=0.58, chunk_id="2"))

        await run_knowledge_search({"query": "x"}, CTX)

        # Lan dau k=5 de do do chac, lan hai k rong hon de dung danh sach.
        assert [k for _, k in da_goi] == [5, 12]

    async def test_KHONG_biet_khoang_cach_thi_KHONG_hoi(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """"Khong biet" khong duoc bien thanh "khong chac"."""
        kho.append(chunk("A", section="Muc mot", distance=None))
        kho.append(chunk("B", section="Muc hai", distance=None, chunk_id="2"))

        assert "KẾT QUẢ KHÔNG CHẮC" not in await run_knowledge_search({"query": "x"}, CTX)

    async def test_da_chon_thi_TRA_SAU_va_KHONG_hoi_lai(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """Hoi hai luot lien tiep la dung cai vong lap ma luat 07/09 dung len de chan.

        Nen o duong `chon`, du khoang cach co xa den may cung KHONG duoc hoi nua.
        """
        kho.append(chunk("Noi dung that", section="Muc mot", distance=0.95))
        kho.append(chunk("Noi dung hai", section="Muc hai", distance=0.96, chunk_id="2"))

        out = await run_knowledge_search({"query": "x", "chon": "Muc mot"}, CTX)

        assert "KẾT QUẢ KHÔNG CHẮC" not in out
        assert "Noi dung that" in out

    async def test_chon_thi_lai_ten_muc_vao_truy_van_va_noi_rong_k(
        self, kho: list[RetrievedChunk]
    ) -> None:
        kho.append(chunk("Noi dung", distance=0.2))

        await run_knowledge_search({"query": "cheese and pasta", "chon": "Muc mot"}, CTX)

        truy_van, k = da_goi[-1]
        assert "Muc mot" in truy_van and "cheese and pasta" in truy_van
        assert k > 5

    async def test_chon_KHAC_thi_KHONG_nhet_chu_khac_vao_truy_van(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """"Khac" la mot loi PHU DINH, khong phai mot tu khoa. Nhet no vao truy van la
        di tim tai lieu noi ve chu "khac".
        """
        kho.append(chunk("Noi dung", distance=0.2))

        await run_knowledge_search({"query": "cheese and pasta", "chon": "Khác"}, CTX)

        truy_van, k = da_goi[-1]
        assert truy_van == "cheese and pasta"
        assert k > 5

    async def test_nhan_ra_KHAC_du_go_kieu_nao(self, kho: list[RetrievedChunk]) -> None:
        kho.append(chunk("Noi dung", distance=0.2))

        for cach_go in ("khác", "Khac", "OTHER", "không phải", "none"):
            await run_knowledge_search({"query": "q", "chon": cach_go}, CTX)
            assert da_goi[-1][0] == "q", cach_go

    async def test_chon_rong_thi_coi_nhu_khong_chon(
        self, kho: list[RetrievedChunk]
    ) -> None:
        """Model tra ve chuoi rong la chuyen co that. Coi do la "da chon" thi lan tim
        chung chung se khong bao gio hoi nua, va tinh nang tu tat mot cach im lang.
        """
        kho.append(chunk("A", section="Muc mot", distance=0.56))
        kho.append(chunk("B", section="Muc hai", distance=0.58, chunk_id="2"))

        out = await run_knowledge_search({"query": "x", "chon": "   "}, CTX)

        assert "KẾT QUẢ KHÔNG CHẮC" in out


class TestKhaiBaoThamSoChon:
    async def test_khai_bao_tham_so_chon(self) -> None:
        thuoc_tinh: Any = KNOWLEDGE_SEARCH_DEFINITION.parameters["properties"]
        assert "chon" in thuoc_tinh

    async def test_chon_KHONG_bat_buoc(self) -> None:
        """Bat buoc thi model phai bia mot gia tri ngay lan tim dau tien."""
        assert KNOWLEDGE_SEARCH_DEFINITION.parameters["required"] == ["query"]

    async def test_mo_ta_chon_cam_tu_bia_gia_tri(self) -> None:
        thuoc_tinh: Any = KNOWLEDGE_SEARCH_DEFINITION.parameters["properties"]
        mo_ta = str(thuoc_tinh["chon"]["description"])
        assert "CHỈ dùng khi" in mo_ta
        assert "Không bao giờ tự bịa" in mo_ta


class TestKetQua:
    async def test_kem_nguon_va_muc_de_trich_dan(self, kho: list[RetrievedChunk]) -> None:
        kho.append(chunk("Don hoan tien xu ly trong 7 ngay lam viec."))

        out = await run_knowledge_search({"query": "hoan tien"}, CTX)

        assert "So tay nhan vien 2026" in out
        assert "Chinh sach hoan tien" in out
        assert "7 ngay lam viec" in out

    async def test_khong_co_muc_thi_van_chay(self, kho: list[RetrievedChunk]) -> None:
        kho.append(chunk("Noi dung.", section=None))
        assert "So tay nhan vien 2026" in await run_knowledge_search({"query": "x"}, CTX)

    async def test_khong_tim_thay_thi_NOI_THANG(self, kho: list[RetrievedChunk]) -> None:
        """Cau nay di thang vao prompt, va no la don bay manh nhat cua ca luong: no
        den DUNG khoanh khac model vua thay ket qua rong.
        """
        out = await run_knowledge_search({"query": "gia bitcoin"}, CTX)

        assert "Không tìm thấy" in out
        # Tri nho cua model van bi cam — do la luat cu, KHONG doi.
        assert "đừng lấy trí nhớ của bạn ra thay thế" in out.lower() or (
            "trí nhớ" in out and "thay thế" in out
        )

    async def test_CHAN_tra_web_cho_cau_hoi_noi_bo(self, kho: list[RetrievedChunk]) -> None:
        """Nhanh nguy hiem hon trong hai nhanh.

        Web tra ve luat lao dong chung cho cau "chinh sach nghi phep nam" — hop ly,
        co nguon, va SAI voi to chuc nay. Thong diep phai noi ro VI SAO cam, khong
        chi ra lenh: model tuan lenh co ly do tot hon lenh tran.
        """
        out = await run_knowledge_search({"query": "chinh sach nghi phep"}, CTX)

        assert "ĐỪNG tra web" in out
        assert "quy định riêng" in out

    async def test_CHO_PHEP_tra_web_cho_kien_thuc_chung(
        self, kho: list[RetrievedChunk]
    ) -> None:
        out = await run_knowledge_search({"query": "cach lam bun cha"}, CTX)

        assert "web_search" in out
        assert "lấy từ web" in out

    async def test_thieu_query_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        with pytest.raises(ValueError):
            await run_knowledge_search({}, CTX)

    async def test_query_rong_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        with pytest.raises(ValueError):
            await run_knowledge_search({"query": "   "}, CTX)

    async def test_query_khong_phai_chuoi_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        payload: dict[str, Any] = {"query": 42}
        with pytest.raises(ValueError):
            await run_knowledge_search(payload, CTX)


class TestCamBayConSoVaCachLam:
    """Hinh dang cam bay THU HAI: hoi mot CON SO hoac mot CACH LAM.

    Do dau-cuoi 11/09/2026 qua `evals.runner --qua-cong-cu` (che do chay qua
    handle_message, tuc model tu viet truy van nhu production):

        12/50 cau model KHONG goi cong cu lan nao

    Mo ta cong cu luc do da goi ten cam bay "cau hoi NGUOC — hoi tu dac diem ra ten",
    va cam bay do da duoc chan. Nhung nhung cau nay khong phai cau hoi nguoc:

        "Luoc khoai so trong bao lau?"
        "Lam sao cho chuoi xanh bot chat?"
        "How long do I microwave the pasta?"

    Chung trong y het kien thuc pho thong, nen model thay minh biet thua. Ma con so
    trong tai lieu CUA HO moi la con so dung, va no thuong khac con so chung.

    Do lai tren 16 cau (12 cau hong + 4 cau chong hoi quy): 4/16 -> 15/16 co goi
    cong cu. Sua o CA HAI cho — luat cung trong SYSTEM_PROMPT va hinh dang nay trong
    mo ta cong cu; xem tests/unit/test_system_prompt.py.
    """

    @property
    def mo_ta(self) -> str:
        return KNOWLEDGE_SEARCH_DEFINITION.description

    async def test_goi_ten_cam_bay_CON_SO_va_CACH_LAM(self) -> None:
        assert "MỘT CON SỐ" in self.mo_ta
        assert "MỘT CÁCH LÀM" in self.mo_ta

    async def test_neu_LY_DO_chu_khong_chi_ra_lenh(self) -> None:
        """Con so trong tai lieu cua ho thuong KHAC con so chung — do la ly do, va
        model tuan mot lenh co ly do tot hon lenh tran.
        """
        assert "thường khác con số chung" in self.mo_ta

    async def test_co_vi_du_va_KHONG_lay_cau_dang_do(self) -> None:
        """Vi du CO Y chon mot cau khong nam trong golden.jsonl. Lay dung cau dang do
        lam vi du la day vet, va con so sau do khong con do duoc gi.
        """
        assert "Ướp thịt bao lâu cho ngấm?" in self.mo_ta
        for dang_do in ("luộc bí", "bớt chát", "bớt ngứa", "microwave"):
            assert dang_do not in self.mo_ta, dang_do
