-- Cau tra loi cua bot cung phai luu.
--
-- StoredMessage trong agents/ports/memory.port.ts da khai truong fromBot tu dau,
-- nhung bang inbound_message khong co cot nao tuong ung va khong noi nao luu cau
-- tra loi. Hau qua neu de nguyen: lich su hoi thoai chi con mot nua, va job tom
-- tat L2 o tuan sau se nen mot doan doc thoai chu khong phai mot cuoc hoi thoai.
--
-- Ten bang gio hoi sai nghia (khong con chi chua tin "inbound"). Doi ten la mot
-- migration rieng, khong dang lam bay gio.

ALTER TABLE inbound_message ADD COLUMN from_bot BOOLEAN NOT NULL DEFAULT FALSE;

-- L1 doc 15 tin gan nhat theo ca hai chieu, nen index cu (platform, thread_id,
-- created_at DESC) van phuc vu duoc. Khong them index moi de tranh ghi cham.
