"""Bang chu CO THAT, tra theo van. TEP NAY DUOC SINH RA — dung sua tay.

    uv run python ops/dung_bang_van.py

VI SAO TON TAI: model be chu (`ngọt ngào` -> `ngọt ngao`) khong phai vi no sai
chinh ta, ma vi no BI TU VAN — viet toi vi tri van thi khong co san chu that nao
vua hop van vua hop nghia. Bang nay dua san chu that cho no chon.

LA GOI Y, KHONG PHAI RANG BUOC. «Chon van truoc» — ep dung nhung chu do o dung
nhung vi tri do — da lam diem sap tu 69,7 xuong 57,1/100. Khac biet nam o cho:
bang nay MO RONG lua chon, khong thu hep no.

Nguon: vi tri van cua 3.254 cau Truyen Kieu (het han bao ho) + tho/tu_vung.py.
Chi thanh bang, xep theo tan suat roi cat ngon.
"""

#: van -> cac TIENG that cung van, thanh bang, xep theo tan suat giam dan.
CHU_THEO_VAN: dict[str, tuple[str, ...]] = {
    "a": ("là", "ra", "nhà", "xa", "ta", "mà", "qua", "già", "sa", "gia", "ba", "bà"),
    "ai": ("ai", "hai", "bài", "mai", "dài", "tài", "vài", "phai", "tai", "đài", "sai", "ngài"),
    "an": ("tan", "đàn", "tàn", "nhan", "than", "quan", "an", "ngàn", "han", "màn", "gian", "vàn"),
    "ang": (
        "vàng", "nàng", "chàng", "sang", "trang", "ràng", "hàng", "càng", "ngang", "đàng",
        "tràng", "màng",
    ),
    "anh": (
        "xanh", "cành", "thành", "quanh", "đành", "thanh", "anh", "rành", "danh", "mành", "canh",
        "vành",
    ),
    "ao": ("vào", "nào", "sao", "cao", "đào", "bao", "xao", "nao", "dào", "dao", "trao", "đao"),
    "ay": ("này", "ngày", "tay", "nay", "hay", "ngay", "bay", "say", "mày", "may", "dày", "thay"),
    "en": (
        "phen", "ghen", "đen", "hèn", "đèn", "khen", "quen", "chen", "sen", "phèn", "nhen",
        "then",
    ),
    "i": ("gì", "thì", "đi", "chi", "tri", "khi", "nhi", "nghi", "phi", "vì", "nghì", "vi"),
    "inh": (
        "tình", "mình", "sinh", "kinh", "đình", "minh", "hình", "binh", "bình", "linh", "tinh",
        "ninh",
    ),
    "iên": (
        "tiền", "tiên", "liền", "thiên", "nhiên", "miền", "phiền", "viên", "niên", "xiên", "hiên",
        "nghiên",
    ),
    "iêu": (
        "nhiều", "điều", "kiều", "chiều", "liều", "xiêu", "nhiêu", "tiêu", "chiêu", "điêu",
        "siêu", "triều",
    ),
    "ong": (
        "lòng", "xong", "trong", "dong", "phong", "mong", "vòng", "dòng", "tòng", "phòng", "song",
        "sòng",
    ),
    "ung": (
        "chung", "hùng", "đùng", "trung", "lùng", "phùng", "thùng", "nùng", "cung", "vùng",
        "trùng", "chùng",
    ),
    "âm": ("cầm", "thầm", "tâm", "âm", "đầm", "thâm", "rầm", "lầm", "ngâm", "ầm", "trầm", "ngầm"),
    "ân": (
        "thân", "gần", "nhân", "lần", "quân", "phần", "trần", "thần", "vân", "vần", "chân", "dần",
    ),
    "âu": ("đâu", "đầu", "lâu", "sầu", "châu", "cầu", "sâu", "dầu", "dâu", "hầu", "câu", "lầu"),
    "ây": ("đây", "mây", "đầy", "tây", "cây", "chầy", "dây", "vầy", "ngây", "thầy", "gầy", "bầy"),
    "ê": ("về", "bề", "mê", "nghề", "quê", "thề", "đề", "kề", "khê", "nề", "dề", "ghê"),
    "ôi": ("thôi", "rồi", "tôi", "hồi", "đôi", "xôi", "bồi", "ngồi", "mồi", "dồi", "sôi", "vôi"),
    "ông": (
        "hồng", "không", "đồng", "công", "sông", "nồng", "chồng", "đông", "lồng", "trông",
        "thông", "bồng",
    ),
    "ăng": (
        "chăng", "rằng", "trăng", "bằng", "thằng", "hằng", "năng", "đằng", "răng", "băng", "lăng",
        "giằng",
    ),
    "ơ": ("giờ", "tơ", "thơ", "cờ", "ngơ", "tờ", "chờ", "cơ", "ngờ", "thờ", "trơ", "vơ"),
    "ơi": ("lời", "trời", "nơi", "đời", "chơi", "rời", "bời", "khơi", "vời", "dời", "rơi", "mời"),
    "ưa": ("xưa", "mưa", "thưa", "vừa", "ưa", "thừa", "đưa", "chưa", "chừa", "trưa", "dưa", "lừa"),
    "ương": (
        "đường", "hương", "thương", "thường", "tường", "trường", "sương", "gương", "phường",
        "vương", "phương", "lường",
    ),
    "oi": ("coi", "soi", "đòi", "thòi", "hoi", "ròi", "thoi", "tòi", "hòi", "nòi", "doi"),
    "uyên": (
        "duyên", "thuyền", "tuyền", "nguyền", "nguyên", "huyên", "khuyên", "huyền", "truyền",
        "suyền", "uyên",
    ),
    "au": ("sau", "nhau", "đau", "màu", "dàu", "mau", "lau", "chau", "thau", "nau"),
    "e": ("nghe", "the", "xe", "che", "e", "rè", "khe", "hè", "nhe", "ve"),
    "on": ("non", "còn", "con", "tròn", "son", "mòn", "đòn", "giòn", "hòn", "don"),
    "am": ("cam", "tham", "làm", "lam", "sàm", "giàm", "phàm", "chàm", "nam"),
    "o": ("cho", "to", "dò", "co", "hò", "lo", "bò", "no", "trò"),
    "oan": ("oan", "đoan", "hoàn", "loan", "đoàn", "hoan", "khoan", "ngoan", "toan"),
    "u": ("thù", "ru", "thu", "tu", "phu", "tù", "bù", "phù", "du"),
    "ăm": ("nằm", "đăm", "năm", "thăm", "trăm", "dằm", "tằm", "xăm", "nhằm"),
    "ưng": ("chừng", "rừng", "dưng", "từng", "bưng", "xưng", "đừng", "mừng", "dừng"),
    "ên": ("lên", "trên", "đền", "bên", "nên", "tên", "quên", "nền"),
    "ư": ("thư", "tư", "dư", "như", "sư", "hư", "lư", "từ"),
    "oa": ("hoa", "lòa", "ngoa", "tòa", "hòa", "thoa", "loa"),
    "ui": ("sùi", "mùi", "ngùi", "vùi", "vui", "lui", "bùi"),
    "êm": ("nêm", "thêm", "đêm", "êm", "thềm", "mềm"),
    "ênh": ("ghềnh", "đênh", "chênh", "tênh", "thênh", "nghênh"),
    "ô": ("hồ", "đồ", "mồ", "ngô", "bồ", "cô"),
    "ôn": ("hôn", "môn", "khôn", "chồn", "chôn", "hồn"),
    "ơn": ("hơn", "cơn", "đơn", "sơn", "hờn", "ơn"),
    "ươi": ("người", "cười", "mười", "tươi", "ngươi", "mươi"),
    "eo": ("theo", "bèo", "gieo", "veo", "chèo"),
    "uy": ("suy", "uy", "truy", "thùy", "tùy"),
    "uôn": ("buôn", "buồn", "chuồn", "khuôn", "nguồn"),
    "y": ("kỳ", "ly", "quy", "quỳ", "y"),
    "êu": ("thêu", "rêu", "trêu", "kêu", "khêu"),
    "ăn": ("khăn", "văn", "ăn", "ngăn", "năn"),
}

#: van cua tieng CUOI -> cac TU GHEP hai tieng. Nguon: tho/tu_vung.py.
TU_THEO_VAN: dict[str, tuple[str, ...]] = {
    "a": (
        "bao la", "chiều tà", "hiên nhà", "mái nhà", "mượt mà", "mặn mà", "mẹ cha", "nõn nà",
        "phôi pha", "quê nhà", "thiết tha", "thướt tha",
    ),
    "ang": (
        "ao làng", "chói chang", "dịu dàng", "khẽ khàng", "mơ màng", "mịn màng", "ngỡ ngàng",
        "nhẹ nhàng", "nắng vàng", "phũ phàng", "rộn ràng", "thênh thang",
    ),
    "ao": (
        "bờ ao", "dạt dào", "lao xao", "lao đao", "nao nao", "nghẹn ngào", "ngọt ngào", "nôn nao",
        "rì rào", "xanh xao", "xôn xao", "yếm đào",
    ),
    "ơ": (
        "bơ vơ", "bạc phơ", "chơ vơ", "hoang sơ", "lơ thơ", "mong chờ", "mịt mờ", "mộng mơ",
        "ngẩn ngơ", "phất phơ", "thẫn thờ", "tuổi thơ",
    ),
    "ông": (
        "bến sông", "con sông", "cánh đồng", "dòng sông", "mênh mông", "mùa đông", "mặn nồng",
        "ngóng trông", "ruộng đồng", "rực hồng", "đỏ hồng",
    ),
    "anh": (
        "an lành", "chòng chành", "hiền lành", "long lanh", "mong manh", "mái tranh", "mỏng manh",
        "trong lành", "trăng thanh", "vắng tanh",
    ),
    "ai": (
        "cành mai", "hoa nhài", "khoan thai", "miệt mài", "nhạt phai", "sương mai", "tàn phai",
        "áo dài",
    ),
    "inh": (
        "bình minh", "dáng hình", "lung linh", "lặng thinh", "mái đình", "thanh bình",
        "trắng tinh", "yên bình",
    ),
    "u": ("cần cù", "hoang vu", "lời ru", "mùa thu", "mịt mù", "tiếng ru", "êm ru"),
    "ênh": (
        "bập bềnh", "bồng bềnh", "chênh vênh", "dòng kênh", "dập dềnh", "gập ghềnh", "lênh đênh",
    ),
    "ơi": ("chơi vơi", "cuộc đời", "dòng đời", "ngời ngời", "rạng ngời", "rợp trời", "sáng ngời"),
    "an": ("chứa chan", "gian nan", "ngút ngàn", "nồng nàn", "râm ran", "thời gian"),
    "ung": ("bập bùng", "chập chùng", "ngượng ngùng", "nhớ nhung", "thẹn thùng", "thủy chung"),
    "ơn": ("chập chờn", "cô đơn", "dập dờn", "giận hờn", "rập rờn", "xanh rờn"),
    "ươi": ("hồng tươi", "kiếp người", "nụ cười", "phận người", "xanh tươi", "đời người"),
    "ương": ("con đường", "nhớ thương", "quê hương", "tình thương", "vấn vương", "yêu thương"),
    "ân": ("bần thần", "quây quần", "trắng ngần", "tảo tần", "ân cần"),
    "ê": ("bờ đê", "làng quê", "tràn trề", "đường quê", "đồng quê"),
    "ưa": ("lưa thưa", "ngày xưa", "năm xưa", "say sưa", "thuở xưa"),
    "o": ("líu lo", "quanh co", "thơm tho", "điệu hò"),
    "au": ("hoa cau", "trắng phau", "đỏ au"),
    "ay": ("bàn tay", "heo may", "đắng cay"),
    "iu": ("hắt hiu", "nâng niu", "quạnh hiu"),
    "on": ("chon von", "nỉ non", "sắt son"),
    "ong": ("chờ mong", "long đong", "sáng trong"),
    "ui": ("bùi ngùi", "ngậm ngùi", "ngọt bùi"),
    "ây": ("ngất ngây", "sum vầy", "đong đầy"),
    "êm": ("dịu êm", "êm đềm", "ấm êm"),
    "ăng": ("vầng trăng", "ánh trăng", "đêm trăng"),
    "ưng": ("rưng rưng", "thơm lừng", "tưng bừng"),
    "em": ("anh em", "chị em"),
    "en": ("hoa sen", "hờn ghen"),
    "eo": ("cheo leo", "trong veo"),
    "im": ("im lìm", "lặng im"),
    "iêu": ("nắng chiều", "tiêu điều"),
    "oa": ("hiền hòa", "nhạt nhòa"),
    "uya": ("canh khuya", "đêm khuya"),
    "uân": ("gió xuân", "mùa xuân"),
    "âm": ("lâm thâm", "thì thầm"),
    "ô": ("mơ hồ", "nhấp nhô"),
    "ôi": ("bồi hồi", "xa xôi"),
    "ăm": ("trăng rằm", "xa xăm"),
    "e": ("lũy tre",),
    "ia": ("đầm đìa",),
    "iên": ("đoàn viên",),
    "iêng": ("nghiêng nghiêng",),
    "oan": ("hân hoan",),
    "oe": ("vàng hoe",),
    "oeo": ("ngoằn ngoèo",),
    "oi": ("lẻ loi",),
    "ua": ("quê mùa",),
    "um": ("xanh um",),
    "uyên": ("truân chuyên",),
    "uâng": ("bâng khuâng",),
    "yêu": ("tình yêu",),
    "âng": ("lâng lâng",),
    "âu": ("áo nâu",),
    "ôn": ("hoàng hôn",),
    "ăn": ("nhọc nhằn",),
    "ư": ("hiền từ",),
    "ươm": ("vàng ươm",),
}
