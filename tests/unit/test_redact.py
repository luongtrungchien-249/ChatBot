import pytest

from shared.redact import redact, redact_deep


class TestRedact:
    @pytest.mark.parametrize(
        "key",
        [
            "sk-proj-AbCdEf123456_xyz-QQrstu",
            "sk-svcacct-AbCdEf123456xyzQQ",
            "sk-ant-api03-AbCdEf123456_xyz-QQ",
            "sk-AbCdEf123456xyzQQrstu",
        ],
    )
    def test_che_api_key_ho_sk_cua_moi_nha_cung_cap(self, key: str) -> None:
        assert redact(f"key la {key} nhe") == "key la sk-*** nhe"

    def test_che_key_tavily(self) -> None:
        assert redact("TAVILY_API_KEY=tvly-AbCdEf123456xyz") == "TAVILY_API_KEY=tvly-***"

    def test_che_token_zalo_dang_numeric_id_secret(self) -> None:
        out = redact("ZALO_BOT_TOKEN=1234567890:AbCdEfGhIjKlMnOpQr")
        assert "AbCdEfGhIjKlMnOpQr" not in out
        assert "***:***" in out

    def test_che_page_token_cua_meta(self) -> None:
        out = redact("token EAAGm0PX4ZCpsBAxxxxxxxxxxxxxxxxxxxxx het")
        assert "EAAGm0PX4ZCpsBAxxxx" not in out
        assert "EAA***" in out

    def test_che_mat_khau_trong_chuoi_ket_noi(self) -> None:
        out = redact("postgres://bot:sieubimat@localhost:5432/chatbot")
        assert out == "postgres://***:***@localhost:5432/chatbot"

    @pytest.mark.parametrize(
        ("text", "expected"),
        [("goi 0912345678 di", "goi *** di"), ("hoac +84912345678", "hoac ***")],
    )
    def test_che_so_dien_thoai_viet_nam(self, text: str, expected: str) -> None:
        assert redact(text) == expected

    def test_che_email_nhung_giu_ten_mien(self) -> None:
        assert redact("lien he nam.tran@congty.vn nhe") == "lien he ***@congty.vn nhe"

    def test_che_header_uy_quyen(self) -> None:
        assert redact("Authorization: Bearer abc123def456ghi") == "Authorization: Bearer ***"

    def test_khong_dung_toi_van_ban_thuong(self) -> None:
        text = "Deadline la 30/11, hop luc 14h tai phong 302."
        assert redact(text) == text

    def test_khong_an_nham_ma_don_hang(self) -> None:
        # 8 chu so, khong phai 10 -> khong phai so dien thoai VN.
        assert redact("ma don hang 01234567") == "ma don hang 01234567"


class TestRedactDeep:
    def test_di_vao_dict_long_nhau_va_giu_nguyen_hinh_dang(self) -> None:
        result = redact_deep(
            {
                "trace_id": "tr1",
                "user": {"phone": "0912345678", "email": "a@b.vn"},
                "tags": ["sk-ant-api03-SECRETSECRET", "binh thuong"],
                "count": 3,
                "ok": True,
                "nothing": None,
            }
        )
        assert result == {
            "trace_id": "tr1",
            "user": {"phone": "***", "email": "***@b.vn"},
            "tags": ["sk-***", "binh thuong"],
            "count": 3,
            "ok": True,
            "nothing": None,
        }
