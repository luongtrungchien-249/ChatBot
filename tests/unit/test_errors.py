"""Bang hanh vi loi o ARCHITECTURE.md section 9.

Case quan trong nhat: 401. Gop no vao "loi upstream, cu retry di" vua ton ba lan goi
vo ich, vua lam nguoi dung nhan cau "thu lai sau" cho mot thu khong bao gio tu khoi —
trieu chung nhin y het "bot khong hieu tieng Viet".
"""

import pytest

from agents.domain.errors import (
    BadPayload,
    BudgetExceeded,
    NotAllowed,
    RateLimited,
    UpstreamError,
    UpstreamTimeout,
    is_config_error,
    is_retryable,
    is_silent,
)


class TestIsRetryable:
    @pytest.mark.parametrize("status", [401, 403])
    def test_khong_retry_loi_cau_hinh(self, status: int) -> None:
        assert is_retryable(UpstreamError(service="llm", status=status)) is False

    @pytest.mark.parametrize("status", [400, 404, 422])
    def test_khong_retry_4xx_khac(self, status: int) -> None:
        # Gui lai y het thi hong y het.
        assert is_retryable(UpstreamError(service="llm", status=status)) is False

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 529])
    def test_co_retry_429_va_5xx(self, status: int) -> None:
        # Day moi that su la tam thoi.
        assert is_retryable(UpstreamError(service="llm", status=status)) is True

    def test_khong_ro_status_thi_van_retry(self) -> None:
        # Loi mang thuong khong co status — cho huong loi cua su nghi ngo.
        assert is_retryable(UpstreamError(service="llm")) is True

    def test_timeout_KHONG_retry(self) -> None:
        # Nguoi dung da nhan cau fallback roi.
        assert is_retryable(UpstreamTimeout(service="llm")) is False

    @pytest.mark.parametrize(
        "error",
        [BudgetExceeded(), NotAllowed(), RateLimited(retry_after_ms=1000), BadPayload(detail="x")],
    )
    def test_cac_loai_khac_khong_bao_gio_retry(self, error: object) -> None:
        assert is_retryable(error) is False  # type: ignore[arg-type]


class TestIsConfigError:
    @pytest.mark.parametrize("status", [401, 403])
    def test_401_va_403_la_loi_cau_hinh(self, status: int) -> None:
        assert is_config_error(UpstreamError(service="llm", status=status)) is True

    def test_5xx_khong_phai_loi_cau_hinh(self) -> None:
        assert is_config_error(UpstreamError(service="llm", status=500)) is False

    def test_timeout_khong_phai_loi_cau_hinh(self) -> None:
        assert is_config_error(UpstreamTimeout(service="llm")) is False


class TestIsSilent:
    def test_khong_duoc_phep_va_payload_hong_thi_im_lang(self) -> None:
        assert is_silent(NotAllowed()) is True
        assert is_silent(BadPayload(detail="x")) is True

    def test_het_ngan_sach_thi_KHONG_im_lang(self) -> None:
        # Nguoi dung phai biet vi sao bot khong tra loi.
        assert is_silent(BudgetExceeded()) is False
