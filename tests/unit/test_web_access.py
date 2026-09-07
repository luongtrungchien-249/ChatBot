"""Hai chinh sach truy cap cua giao dien web, va ranh gioi giua chung.

Bo test nay ton tai vi mot lo hong that: `/api/metrics` dung `require_localhost`, ma
Prometheus lai chay trong mot container khac — nen no bi 403 va toan bo dashboard
Grafana trong rong. Trieu chung khong he chi ve nguyen nhan: khong co dong log nao o
phia Grafana, va goi tay tu chinh may thi lai ra 200.

Khong I/O: ca hai ham chi doc dia chi cua request.
"""

from typing import Any

import pytest
from fastapi import HTTPException

from adapters.web.routes import require_localhost, require_operator


class Request:
    """Du phan Request ma hai ham nay cham toi. Khong dung TestClient: dung no la keo
    theo ca ung dung, ma ung dung thi can Postgres va Redis luc khoi dong.
    """

    def __init__(self, host: str | None) -> None:
        self.client: Any = None if host is None else type("C", (), {"host": host})()

    # Hai ham duoi chi doc `.client.host`, nhung chu ky cua chung doi
    # starlette.Request. Ep kieu o mot cho thay vi rai `type: ignore` khap file.
    def as_request(self) -> Any:
        return self


LOOPBACK = ["127.0.0.1", "::1", "::ffff:127.0.0.1"]
MANG_RIENG = ["172.18.0.5", "10.0.0.7", "192.168.1.75", "fd00::1"]
#: Dia chi CONG KHAI that. KHONG dung 203.0.113.x hay 2001:db8:: — do la dai danh
#: cho tai lieu, va Python xep chung vao nhom "khong dinh tuyen duoc".
CONG_KHAI = ["8.8.8.8", "2606:4700:4700::1111"]


class TestChiLocalhost:
    """Cac route doc va XOA duoc hoi thoai. Chung khong duoc noi long."""

    @pytest.mark.parametrize("host", LOOPBACK)
    async def test_loopback_duoc_qua(self, host: str) -> None:
        require_localhost(Request(host).as_request())

    @pytest.mark.parametrize("host", MANG_RIENG + CONG_KHAI)
    async def test_moi_dia_chi_khac_deu_bi_CHAN(self, host: str) -> None:
        """Ke ca mang rieng. Mot may khac trong cung mang LAN khong duoc doc hoi thoai."""
        with pytest.raises(HTTPException) as loi:
            require_localhost(Request(host).as_request())
        assert loi.value.status_code == 403

    async def test_khong_biet_dia_chi_thi_CHAN(self) -> None:
        with pytest.raises(HTTPException):
            require_localhost(Request(None).as_request())


class TestMetrics:
    """`/api/metrics` phai nhan them mang rieng — va CHI mang rieng."""

    @pytest.mark.parametrize("host", LOOPBACK)
    async def test_loopback_duoc_qua(self, host: str) -> None:
        require_operator(Request(host).as_request())

    @pytest.mark.parametrize("host", MANG_RIENG)
    async def test_mang_rieng_duoc_qua(self, host: str) -> None:
        """Day chinh la ca da hong: Prometheus goi tu 172.x trong mang cua compose."""
        require_operator(Request(host).as_request())

    @pytest.mark.parametrize("host", CONG_KHAI)
    async def test_dia_chi_CONG_KHAI_van_bi_chan(self, host: str) -> None:
        with pytest.raises(HTTPException) as loi:
            require_operator(Request(host).as_request())
        assert loi.value.status_code == 403

    async def test_khong_biet_dia_chi_thi_CHAN(self) -> None:
        with pytest.raises(HTTPException):
            require_operator(Request(None).as_request())

    async def test_dia_chi_khong_doc_duoc_thi_CHAN(self) -> None:
        """Chuoi rac phai roi vao nhanh tu choi, khong phai nhanh nem ValueError."""
        with pytest.raises(HTTPException):
            require_operator(Request("khong-phai-mot-dia-chi").as_request())
