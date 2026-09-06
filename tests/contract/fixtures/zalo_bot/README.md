# Payload that cua Zalo Bot API

Ghi lai MOT LAN tu he thong that (06/09/2026), dung mai. Zalo doi payload thi test
o `tests/contract/` do — chu khong phai production do.

**Da an danh gia tri, GIU NGUYEN hinh dang.** id va noi dung tin nhan la du lieu
that cua mot nhom that; cai co gia tri kiem chung la CAU TRUC (ten truong, kieu,
truong nao vang mat), khong phai gia tri. Do dai va tien to cua id duoc giu dung de
neu co cho nao ngam gia dinh ve dinh dang id thi test van bat duoc.

## Dieu quan trong nhat da hoc duoc

`group_text.json` KHONG co truong mention nao. Zalo chen thang TEN HIEN THI cua bot
vao `text`. Do la ly do `adapters/zalo_bot/normalize.py` de `mentioned_bot=False`
cho tin nhom va giao viec nhan dien cho regex trong `agents/policy/mention.py`.
