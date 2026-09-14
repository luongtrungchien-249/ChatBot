"""Bo chu de huan luyen RLVR. Buoc 5 cua docs/plan-rlvr-tho.md.

RANG BUOC QUAN TRONG NHAT: train va test KHONG GIAO NHAU.

§6.3 doi nghiem thu tren chu de CHUA TUNG THAY khi train. Hai tap giao nhau thi con so
nghiem thu do "model da thuoc bai" chu khong do "model da hoc luat" — va sai lech do IM
LANG, khong co gi bao. Nen no phai co test rieng, khong de cho luc chay moi phat hien.
"""

import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(GOC / "ops"))

from sinh_chu_de import CHU_THE, GOC_NHIN, HAT_GIONG, TI_LE_TEST, sinh  # noqa: E402


class TestTrainTestKhongGiaoNhau:
    def test_khong_mot_chu_de_nao_nam_o_ca_hai_tap(self) -> None:
        train, test = sinh()

        assert not ({x["chu_de"] for x in train} & {x["chu_de"] for x in test})

    def test_tach_theo_CHU_THE_chu_khong_ngau_nhien_tren_danh_sach_cuoi(self) -> None:
        """Chia ngau nhien thi "mẹ" vao train con "nỗi nhớ về mẹ" vao test — hai cai
        gan nhau qua, va model se co ve nhu tong quat hoa duoc trong khi khong.
        """
        train, test = sinh()
        ct_train = {ct for ct in CHU_THE if any(ct in x["chu_de"] for x in train)}
        ct_test = {ct for ct in CHU_THE if any(ct in x["chu_de"] for x in test)}

        # Mot chu the chi duoc nam o DUNG mot ben. ("cha" la chuoi con cua "người cha"
        # nen dung `==` tren tap chu the goc, khong dung chuoi con.)
        for ct in CHU_THE:
            o_train = any(x["chu_de"] == ct for x in train)
            o_test = any(x["chu_de"] == ct for x in test)
            assert not (o_train and o_test), f"{ct} nằm ở cả hai tập"
        assert ct_train and ct_test

    def test_moi_chu_the_deu_duoc_dung(self) -> None:
        train, test = sinh()

        assert len(train) + len(test) == len(CHU_THE) * len(GOC_NHIN)


class TestLapLaiDuoc:
    def test_hai_lan_goi_cho_KET_QUA_GIONG_HET(self) -> None:
        """Hat giong co dinh. Doi hat giong la doi ca phep do — phai co chu y."""
        a1, b1 = sinh()
        a2, b2 = sinh()

        assert a1 == a2
        assert b1 == b2

    def test_hat_giong_duoc_ghim(self) -> None:
        assert HAT_GIONG == 20260914


class TestHinhDangDuLieu:
    def test_moi_dong_co_du_chu_de_va_the_tho(self) -> None:
        train, test = sinh()

        for x in train + test:
            assert set(x) == {"chu_de", "the_tho"}
            assert x["chu_de"].strip()

    def test_doi_duoc_the_tho(self) -> None:
        train, _ = sinh("that_ngon_bat_cu")

        assert all(x["the_tho"] == "that_ngon_bat_cu" for x in train)

    def test_ti_le_test_hop_ly(self) -> None:
        train, test = sinh()
        ti_le = len(test) / (len(train) + len(test))

        assert abs(ti_le - TI_LE_TEST) < 0.1
