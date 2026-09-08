"""Chay KHO mot tai lieu va bao cao chat luong, khong ghi mot dong nao vao CSDL.

Tra loi truc tiep nam trong sau cau hoi cua buoc "kiem tra chat luong index":

    Co doc du tai lieu khong?        -> so trang, trang rong, ky tu/trang
    Chunk co bi mat noi dung khong?  -> do phu, phan bo do dai
    Metadata co dung khong?          -> ti le co section / co page
    Co chunk bi trung khong?         -> bam noi dung da chuan hoa
    Embedding co tao thanh cong?     -> khong o day: xem ghi chu ben duoi
    Tim kiem co tra ve doan lien quan? -> khong o day: can `evals/runner.py`

Cau thu nam va sau CO Y khong nam trong lenh nay. Ca hai deu can goi API that va can
tai lieu DA NAP, con lenh nay ton tai de chay TRUOC khi nap — luc con sua duoc mien
phi. Ghep chung vao se lam mot lenh re thanh mot lenh dat, va nguoi ta se thoi chay no.

Rieng "embedding co tao thanh cong" thi da co cau tra loi tot hon o cho khac: ca tai
lieu nap trong MOT transaction, nen khong co trang thai "nua so chunk co vector".
"""

import hashlib
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from .chunk import TARGET_CHARS, Chunk, chunk_document
from .extract import extract_document

#: Chunk ngan hon nguong nay thuong la manh vun sinh ra tu mot ranh gioi cat sai —
#: no van chiem mot dong trong ket qua tim kiem ma gan nhu khong mang thong tin.
_QUA_NGAN = 200


@dataclass
class BaoCao:
    duong_dan: str
    so_trang: int = 0
    trang_rong: int = 0
    ky_tu: int = 0
    so_chunk: int = 0
    co_section: int = 0
    co_page: int = 0
    trung: list[tuple[int, int]] = field(default_factory=list)
    qua_ngan: int = 0
    vuot_tran: int = 0
    do_dai: list[int] = field(default_factory=list)
    #: Ti le ky tu cua van ban goc xuat hien trong chunk. Thieu = mat noi dung.
    do_phu: float = 0.0

    @property
    def dat(self) -> bool:
        """Dieu kien TOI THIEU de nap. Co y hep — chi bat cai chac chan la hong.

        `section` va `page` KHONG nam trong day: tai lieu .md hop le van co the
        khong co trang, va tai lieu khong co tieu de van nap duoc.
        """
        return (
            self.so_chunk > 0
            and self.do_phu >= 0.98
            and not self.trung
            and self.trang_rong < self.so_trang
        )


def _bam(noi_dung: str) -> str:
    return hashlib.sha256(" ".join(noi_dung.split()).lower().encode("utf-8")).hexdigest()


def kiem_tra(path: Path) -> tuple[BaoCao, list[Chunk]]:
    tai_lieu = extract_document(path)
    text = tai_lieu.text
    chunks = chunk_document(text, tai_lieu.ban_do_trang)

    bc = BaoCao(duong_dan=str(path), ky_tu=len(text), so_chunk=len(chunks))
    bc.so_trang = len(tai_lieu.ban_do_trang)
    bc.co_section = sum(1 for c in chunks if c.section)
    bc.co_page = sum(1 for c in chunks if c.page is not None)
    bc.do_dai = [len(c.content) for c in chunks]
    bc.qua_ngan = sum(1 for n in bc.do_dai if n < _QUA_NGAN)
    bc.vuot_tran = sum(1 for n in bc.do_dai if n > TARGET_CHARS)

    # Do phu: "bao nhieu phan van ban goc duoc mot chunk nao do phu", cong tren TAP
    # VI TRI chu khong cong do dai — chunk co chong lan nen tong do dai luon lon hon
    # van ban goc.
    #
    # Dung `bat_dau`/`dai_goc` chu KHONG di tim lai chuoi: sau khi ap chong lan,
    # `content` khong con la lat cat lien tuc cua van ban nen `text.find()` truot.
    # Ban dau viet bang `find` va no bao 54,7% tren mot tai lieu khong mat mot ky tu
    # nao — thuoc do sai con nguy hiem hon khong co thuoc do, vi no lam nguoi ta di
    # sua mot loi khong ton tai.
    phu = bytearray(len(text))
    for c in chunks:
        phu[c.bat_dau : c.bat_dau + c.dai_goc] = b"\x01" * c.dai_goc
    # Khoang trang bi `strip()` an di o ranh gioi muc — do la cat gon, khong phai mat
    # noi dung, nen khong tinh la thieu.
    thieu = sum(1 for i, ch in enumerate(text) if not phu[i] and not ch.isspace())
    bc.do_phu = 1.0 - (thieu / len(text)) if text else 0.0

    thay: dict[str, int] = {}
    for c in chunks:
        h = _bam(c.content)
        if h in thay:
            bc.trung.append((thay[h], c.ord))
        else:
            thay[h] = c.ord

    return bc, chunks


def in_bao_cao(bc: BaoCao) -> None:
    def dong(nhan: str, gia_tri: object, canh_bao: bool = False) -> None:
        print(f"  {'!' if canh_bao else ' '} {nhan:<34} {gia_tri}")

    print(f"\nKIEM TRA: {bc.duong_dan}\n")

    print("Doc du tai lieu?")
    dong("so trang", bc.so_trang)
    dong("trang rong", bc.trang_rong, bc.trang_rong > 0)
    dong("ky tu doc duoc", f"{bc.ky_tu:,}")
    if bc.so_trang:
        dong("trung binh ky tu/trang", f"{bc.ky_tu // bc.so_trang:,}")

    print("\nChunk co mat noi dung?")
    dong("so chunk", bc.so_chunk)
    dong("do phu van ban goc", f"{bc.do_phu:.1%}", bc.do_phu < 0.98)
    if bc.do_dai:
        dong("do dai min / trung vi / max",
             f"{min(bc.do_dai)} / {int(statistics.median(bc.do_dai))} / {max(bc.do_dai)}")
        dong(f"chunk ngan hon {_QUA_NGAN} ky tu", bc.qua_ngan, bc.qua_ngan > 0)
        dong(f"chunk vuot tran {TARGET_CHARS}", bc.vuot_tran)

    print("\nMetadata co dung?")
    pct = lambda n: f"{n}/{bc.so_chunk}" + (f" ({100 * n // bc.so_chunk}%)" if bc.so_chunk else "")
    dong("chunk co section", pct(bc.co_section), bc.co_section == 0)
    dong("chunk co page", pct(bc.co_page), bc.co_page == 0)

    print("\nCo chunk trung?")
    dong("cap chunk trung noi dung", len(bc.trung), bool(bc.trung))
    for a, b in bc.trung[:5]:
        dong("  ord", f"{a} == {b}", True)

    print()
    print("  => DAT, nap duoc." if bc.dat else "  => CHUA DAT, xem cac dong co dau '!'.")
    print()
