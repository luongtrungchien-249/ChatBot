"""Stage 13: gui cau tra loi — va la CHOT CHAN CUOI CUNG truoc khi no roi he thong.

KHONG chunk o day. Hop dong cua ChannelPort.send() la "tu chunk theo
max_message_chars" — moi nen tang mot gioi han (Zalo 2000 ky tu), va agents/ khong
duoc hardcode con so cua tung nen tang.

Truoc 08/09/2026 ham nay di THANG tu model ra kenh chat. Moi lop phong thu cua du an
deu nam o dau vao hoac trong prompt — tuc la deu dua vao viec model chiu nghe loi.
Model khong phai lop bao mat. Gio moi cau tra loi deu qua `kiem_dau_ra`; xem
agents/policy/output_guard.py.

Vi sao dat o day chu khong o stage 12: cau BAO LOI va cau TU CHOI cung phai qua. Mot
cau fallback khong the chua bi mat, nhung mot cau tu lenh `memory` thi hoan toan co
the — no doc lai fact ma nguoi khac da ghi.
"""

from ...domain.thread import ThreadScope
from ...policy.output_guard import kiem_dau_ra
from ...ports.channel import ChannelPort
from ...ports.logger import LoggerPort


async def respond(
    channel: ChannelPort,
    scope: ThreadScope,
    text: str,
    reply_to: str | None = None,
    *,
    logger: LoggerPort | None = None,
    van_ban_nguoi_dung: str = "",
    co_tai_lieu: bool = False,
) -> None:
    verdict = kiem_dau_ra(
        text, van_ban_nguoi_dung=van_ban_nguoi_dung, co_tai_lieu=co_tai_lieu
    )

    if logger is not None and verdict.da_can_thiep:
        # Ghi LOAI, khong ghi chinh chuoi bi che — log cung la mot cho ro ri.
        #
        # `bi-mat` la muc ERROR chu khong phai WARNING: no nghia la mot khoa that da
        # di qua model va suyt ra toi nhom chat. Thu do phai duoc thu hoi, khong phai
        # duoc ghi nhan roi bo qua.
        muc = logger.error if "bi-mat" in verdict.da_can_thiep else logger.warning
        muc(
            "output guard da can thiep vao cau tra loi",
            luat=list(verdict.da_can_thiep),
            loai_bi_mat=list(verdict.loai_bi_mat),
            loai_ca_nhan=list(verdict.loai_ca_nhan),
        )

    if logger is not None and verdict.thieu_trich_dan:
        # KHONG chan: mot cau tra loi dung nhung quen trich dan van huu ich hon mot
        # cau bi nuot. O day de DO ti le, roi moi quyet dinh siet bang cach nao.
        logger.warning("tra loi co tai lieu nhung khong neu nguon nao")

    await channel.send(scope, verdict.text, reply_to)
