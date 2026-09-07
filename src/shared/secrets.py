"""Phan biet BI MAT voi THONG TIN CA NHAN — hai thu doi hai cach xu ly khac nhau.

`shared/redact.py` gop ca hai vao mot danh sach vi no phuc vu LOG, noi tha che nham
con hon de lot: mot dong log xau khong lam ai kho chiu.

Duong RA thi khac. Che tat ca moi thu se cho ra nhung cau nhu "Minh nho so dien thoai
cua ban la ***" — bot tro nen vo dung, va nguoi dung se thoi dung no. Nen o day tach
lam hai nhom, va moi nhom mot chinh sach:

  BI MAT    khoa API, token, chuoi ket noi. KHONG co truong hop hop le nao de bot
            doc chung ra trong mot khung chat. Chan cung, khong dieu kien.

  CA NHAN   so dien thoai, email. Co truong hop hop le: nguoi dung vua tu go ra va
            nho bot nhac lai. Chinh sach o output_guard.py: chi che khi no KHONG co
            trong luot cua chinh nguoi dung — tuc la bot lay no tu tai lieu, tu web,
            hoac tu bo nho cua nguoi khac.

Hai danh sach nay co y KHONG import lai tu redact.py: gop lai thi mot lan sua cho log
se lang le doi hanh vi cua duong ra, va nguoc lai.
"""

import re

#: Nhung thu khong bao gio duoc phep xuat hien trong cau tra loi.
#:
#: Bot doc tai lieu noi bo va ket qua web. Mot trang huong dan cai dat co the chua
#: `sk-proj-...` that; mot tep cau hinh bi nap nham vao RAG cung vay. Khong chan thi
#: bot se doc no ra giua nhom chat, va do la mot khoa phai thu hoi.
_BI_MAT: list[tuple[str, re.Pattern[str], str]] = [
    (
        "chuoi-ket-noi",
        re.compile(r"\b(postgres|postgresql|redis|rediss|amqp|mongodb)://[^:@\s/]+:[^@\s]+@", re.I),
        r"\1://[da an]:[da an]@",
    ),
    # Ho 'sk-': OpenAI (sk-proj-, sk-svcacct-), Anthropic (sk-ant-). Bat ca ho thay vi
    # liet ke tung tien to — doi nha cung cap thi khong phai nho quay lai sua cho nay.
    ("khoa-sk", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"), "[khoa da an]"),
    ("khoa-tavily", re.compile(r"\btvly-[A-Za-z0-9_-]{8,}"), "[khoa da an]"),
    ("token-meta", re.compile(r"\bEAA[A-Za-z0-9]{20,}"), "[token da an]"),
    # Zalo Bot Platform: numeric_id:secret
    ("token-zalo", re.compile(r"(?<!\d)\d{6,}:[A-Za-z0-9_-]{16,}"), "[token da an]"),
    (
        "header-uy-quyen",
        re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
        r"\1 [da an]",
    ),
    # AWS. Khong co trong redact.py vi log cua du an nay khong cham toi AWS, nhung
    # mot tai lieu duoc nap vao thi hoan toan co the.
    ("khoa-aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[khoa da an]"),
    # GitHub token: ghp_, gho_, ghs_, ghu_, ghr_
    ("token-github", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[token da an]"),
    # Khoa rieng dang PEM.
    (
        "khoa-rieng",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "[khoa rieng da an]",
    ),
]

#: Thong tin ca nhan. Che CO DIEU KIEN — xem output_guard.py.
#:
#: Email di TRUOC so dien thoai: '0912345678@vd.com' se bi mau so dien thoai an mat
#: phan truoc @ neu dao thu tu.
_CA_NHAN: list[tuple[str, re.Pattern[str], str]] = [
    # KHONG dung backreference o nhom nay: `che_ca_nhan` thay the bang HAM, va khi
    # do Python tra ve chuoi NGUYEN VAN — dau tham chieu se di thang vao cau tra
    # loi. Da troi that: nguoi dung nhan duoc "hoac @\1 nhe".
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email da an]"),
    ("dien-thoai", re.compile(r"(?<!\d)(?:\+84|0)\d{9}(?!\d)"), "[so da an]"),
    # Can cuoc cong dan Viet Nam: 12 chu so. Nguong hep de khong nuot moi day so dai.
    ("can-cuoc", re.compile(r"(?<!\d)\d{12}(?!\d)"), "[so da an]"),
]


def tim_bi_mat(text: str) -> tuple[str, ...]:
    """Ten cac loai bi mat xuat hien trong `text`. Rong = sach."""
    return tuple(ten for ten, mau, _ in _BI_MAT if mau.search(text))


def che_bi_mat(text: str) -> str:
    for _ten, mau, thay in _BI_MAT:
        text = mau.sub(thay, text)
    return text


def tim_ca_nhan(text: str) -> tuple[str, ...]:
    return tuple(ten for ten, mau, _ in _CA_NHAN if mau.search(text))


def trich_ca_nhan(text: str) -> set[str]:
    """Cac chuoi ca nhan CU THE co trong `text`.

    Dung de so sanh: mot so dien thoai nguoi dung vua go ra thi bot duoc phep nhac
    lai, con mot so bot lay tu tai lieu thi khong.
    """
    ra: set[str] = set()
    for _ten, mau, _thay in _CA_NHAN:
        ra.update(m.group(0) for m in mau.finditer(text))
    return ra


def che_ca_nhan(text: str, cho_phep: set[str]) -> str:
    """Che moi chuoi ca nhan TRU nhung cai trong `cho_phep`.

    `cho_phep` la nhung chuoi da co san trong luot cua nguoi dung — che chung lai la
    tra loi "so dien thoai cua ban la ***" cho chinh nguoi vua go no ra.
    """
    for _ten, mau, thay in _CA_NHAN:
        # `thay=thay` de gan gia tri NGAY vong lap nay. Khong co no thi lambda doc
        # `thay` luc CHAY, va neu mot ngay ai do doi `sub` thanh goi tre thi moi mau
        # se dung ky tu thay the cua vong cuoi — mot loi im lang.
        text = mau.sub(
            lambda m, thay=thay: m.group(0) if m.group(0) in cho_phep else thay,  # type: ignore[misc]
            text,
        )
    return text
