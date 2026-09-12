"""Stage 9b: lam tho — di DUONG RIENG, khong qua vong ReAct.

VI SAO TACH RA: lam tho la bai toan NGUOC voi phan con lai cua bot. Luat he thong
hien tai la "KHONG tra loi tu tri nho, moi cau hoi co du kien deu phai tra tai lieu
TRUOC", va chan 7 trong `generate.py` cuong che luat do. Mot yeu cau lam tho khong co
tai lieu nao de tra, va tra cung vo nghia — nen neu de no di qua vong ReAct thi:

  - no kich hoat chan 7, ton MOT LUOT GOI MODEL thua cho moi bai tho;
  - va co nguy co model di tra that roi tra ve "khong tim thay tai lieu ve mua thu".

Dat SAU chan ngan sach (stage 5) chu khong truoc: lam tho van goi model, van ton tien,
nen no phai chiu cung mot cai chan nhu moi luot khac. Dat TRUOC recall (stage 10): mot
bai tho khong can L1/L2/L3, va doc chung chi cong them do tre.

Luat tho duoc cuong che bang CODE trong `tho/luat.py`, khong bang cau chu trong prompt
— xem docstring cua goi `tho` de biet vi sao.
"""

from tho.prompt import system_prompt
from tho.sinh import KetQua, sinh_tho, tra_loi
from tho.y_dinh import YeuCauTho

from ...ports.llm import CallContext, LlmPort, UserMessage
from ...ports.logger import LoggerPort


async def lam_tho(
    yeu_cau: YeuCauTho,
    llm: LlmPort,
    *,
    max_tokens: int,
    ctx: CallContext,
    logger: LoggerPort,
) -> str:
    """Sinh bai tho, tra ve van ban da san sang gui cho nguoi dung."""

    async def goi_model(sys_prompt: str, luot: list[str]) -> str:
        # `effort` KHONG truyen o day. Lam tho la viec sinh, khong phai viec suy luan
        # nhieu buoc, va `llm/models.py` da ghi lai phep do 07/09: effort cao hon lam
        # moi lan goi lau hon ma khong tot hon. Muc tieu cua ca tinh nang nay la GIAM
        # do tre.
        ket_qua = await llm.reply(
            system=sys_prompt,
            messages=tuple(UserMessage(content=x) for x in luot),
            max_tokens=max_tokens,
            effort="low",
            ctx=ctx,
            # Route RIENG: day la cho duy nhat co the tro sang model tu host ma khong
            # keo theo ca bot. Chua cau hinh POEM_BASE_URL thi no dung model chung.
            route="poem",
        )
        return ket_qua.text

    async def cham_model(sys_prompt: str, luot: list[str]) -> str:
        # NGUOI CHAM di duong `cheap` route `summarize` — model KHAC model lam tho.
        #
        # Do 11/09/2026: dung chung `gpt-4o-mini` lam nguoi cham thi no khong phan
        # biet duoc bai nao hon bai nao (hai thiet ke prompt, mot cai cho 81% deu tay,
        # mot cai cho diem giong het nhau). Nguoi cham cua evals/ thi phan biet duoc,
        # va khac biet nam o dung cho nay. Xem `CHON_BANG_NGUOI_CHAM` trong tho/sinh.py.
        return await llm.cheap(
            system=sys_prompt,
            input=luot[-1],
            max_tokens=max_tokens,
            route="summarize",
            ctx=ctx,
        )

    ket_qua: KetQua = await sinh_tho(
        yeu_cau.the_tho, yeu_cau.chu_de, goi_model, cham_model=cham_model
    )

    # Ghi SO LAN GOI va SO LOI CON LAI: hai con so nay la thu duy nhat noi duoc tinh
    # nang nay dang ton bao nhieu do tre, va prompt co dang lam viec khong. Khong co
    # chung thi moi thay doi prompt tho deu la doan mo.
    logger.info(
        "lam tho xong",
        the_tho=yeu_cau.the_tho,
        so_lan_goi=ket_qua.so_lan_goi,
        so_loi_con_lai=len(ket_qua.con_loi),
        # Bang-trac khong chan (xem tho/sinh.py EP_BANG_TRAC) nhung VAN duoc dem:
        # day la con so duy nhat noi duoc khi nao bat lai duoc tang luat do.
        so_loi_bang_trac=len(ket_qua.loi_bang_trac),
        co_chu_de=bool(yeu_cau.chu_de),
    )
    return tra_loi(ket_qua)


__all__ = ["lam_tho", "system_prompt"]
