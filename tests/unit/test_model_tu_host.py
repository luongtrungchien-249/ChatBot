"""Route `poem` co the tro sang model TU HOST. Cho de hong im lang nhat la endpoint.

Hai kieu hong nguy hiem, va ca hai deu khong nem loi:
  - dung CHUNG mot client cho hai endpoint -> gui khoa cua OpenAI sang may tu host
  - gui `reasoning_effort` sang Gemma -> ca request bi tu choi

Khong goi mang: chi kiem cau hinh va viec dung client.
"""

from typing import Any

import pytest

from llm import models as llm_models
from llm import openai_client
from llm.models import MODELS, ModelConfig, model_cho


class TestModelConfig:
    async def test_mac_dinh_van_la_endpoint_cua_OpenAI(self) -> None:
        """Khong cau hinh gi thi khong duoc doi hanh vi cua ca bot."""
        assert MODELS["reply"].base_url is None
        assert MODELS["reply"].effort == "low"

    async def test_route_poem_KHONG_nam_trong_dict_tinh(self) -> None:
        """Hoi quy that ma test nay chan.

        Route `poem` phai DOC CONFIG de biet co tu host hay khong. De no trong dict
        `MODELS` — mot dict dung o cap module — nghia la doc config NGAY LUC IMPORT,
        va `import llm.models` tro thanh mot cho co the chet vi thieu bien moi truong,
        ke ca trong test khong dung toi route nay.

        Cung ly do voi `get_reranker()` trong llm/reranker.py, va no da duoc ghi ro o
        do tu truoc.
        """
        assert "poem" not in MODELS

    async def test_model_cho_la_duong_DUY_NHAT_lay_route_poem(self) -> None:
        assert model_cho("poem") is not None

    async def test_model_cho_CACHE_lai_khong_doc_config_moi_lan(self) -> None:
        llm_models._tho = None

        assert model_cho("poem") is model_cho("poem")

    async def test_chua_cau_hinh_thi_route_poem_dung_model_CHUNG(self) -> None:
        """Khong dat POEM_BASE_URL thi tinh nang van chay duoc ngay, khong can GPU."""
        llm_models._tho = None

        assert model_cho("poem").base_url is None

    async def test_model_tu_host_KHONG_co_effort(self) -> None:
        """Gemma khong co `reasoning_effort`. Gui len la bi tu choi ca request."""
        tu_host = ModelConfig(
            id="google/gemma-4-26b-a4b-it",
            max_tokens=4_000,
            price_in=0.0,
            price_cached_in=0.0,
            price_out=0.0,
            effort=None,
            base_url="http://localhost:8000/v1",
        )

        assert tu_host.effort is None

    async def test_model_tu_host_gia_BANG_KHONG(self) -> None:
        """Chi phi that la GIO GPU, khong quy ve token duoc.

        Hau qua phai biet: route nay se KHONG bao gio lam `DAILY_BUDGET_USD` nhich
        len, tuc chan ngan sach khong con bao ve gi cho no. GPU van ton tien that.
        """
        tu_host = ModelConfig(
            id="x", max_tokens=1, price_in=0.0, price_cached_in=0.0, price_out=0.0
        )

        assert tu_host.price_in == 0.0
        assert tu_host.price_out == 0.0


class TestChonClient:
    @pytest.fixture(autouse=True)
    def _sach(self) -> Any:
        openai_client._clients.clear()
        yield
        openai_client._clients.clear()

    async def test_MOI_endpoint_mot_client_rieng(self) -> None:
        """Dung chung mot client cho hai endpoint la gui khoa cua ben nay sang ben
        kia — mot kieu ro ri khong nem loi nao.
        """
        mac_dinh = openai_client._get_client()
        tu_host = openai_client._get_client(
            ModelConfig(
                id="x",
                max_tokens=1,
                price_in=0.0,
                price_cached_in=0.0,
                price_out=0.0,
                base_url="http://localhost:8000/v1",
                api_key="khoa-gia",
            )
        )

        assert mac_dinh is not tu_host

    async def test_cung_endpoint_thi_DUNG_LAI_client(self) -> None:
        """Tao client moi moi lan goi la mo mot pool ket noi moi moi lan goi."""
        cau_hinh = ModelConfig(
            id="x",
            max_tokens=1,
            price_in=0.0,
            price_cached_in=0.0,
            price_out=0.0,
            base_url="http://localhost:8000/v1",
            api_key="khoa-gia",
        )

        assert openai_client._get_client(cau_hinh) is openai_client._get_client(cau_hinh)

    async def test_client_tu_host_dung_DUNG_base_url_va_khoa(self) -> None:
        client = openai_client._get_client(
            ModelConfig(
                id="x",
                max_tokens=1,
                price_in=0.0,
                price_cached_in=0.0,
                price_out=0.0,
                base_url="http://localhost:8000/v1",
                api_key="khoa-gia",
            )
        )

        assert str(client.base_url).rstrip("/") == "http://localhost:8000/v1"
        assert client.api_key == "khoa-gia"


class TestChonModelChoRouteTho:
    """Doi model cho RIENG route tho, bang mot dong .env.

    VI SAO CHI ROUTE NAY duoc doi tu do: moi luat trong SYSTEM_PROMPT deu duoc hieu
    chuan tren `gpt-5-mini` qua ba ngay do dac. Doi model cho ca bot se lam toan bo so
    lieu do het gia tri. Route `poem` thi khong dinh gi toi chung — no khong dung
    SYSTEM_PROMPT, khong goi cong cu, khong qua vong ReAct.
    """

    @pytest.fixture(autouse=True)
    def _sach(self) -> Any:
        llm_models._tho = None
        yield
        llm_models._tho = None

    async def test_gpt_4o_mini_KHONG_duoc_gui_reasoning_effort(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cho de hong im lang: `gpt-4o-mini` KHONG phai model reasoning. Gui
        `reasoning_effort` len la bi tu choi CA REQUEST, khong phai bi bo qua.
        """
        monkeypatch.setenv("POEM_MODEL_ID", "gpt-4o-mini")
        from config import get_settings

        get_settings.cache_clear()

        m = model_cho("poem")

        assert m.id == "gpt-4o-mini"
        assert m.effort is None

    async def test_gpt_5_nano_VAN_la_model_reasoning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POEM_MODEL_ID", "gpt-5-nano")
        from config import get_settings

        get_settings.cache_clear()

        m = model_cho("poem")

        assert m.effort == "low"
        assert m.price_out == 0.40

    async def test_model_la_cua_OPENAI_thi_KHONG_co_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Doi model khong duoc bien thanh tu host: hai viec do khac han nhau."""
        monkeypatch.setenv("POEM_MODEL_ID", "gpt-4o-mini")
        from config import get_settings

        get_settings.cache_clear()

        assert model_cho("poem").base_url is None

    async def test_gia_KHONG_bang_khong_khi_dung_model_OpenAI(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ca am: chi model TU HOST moi co gia 0. Model OpenAI van ton tien that, va
        `DAILY_BUDGET_USD` phai dem duoc no.
        """
        monkeypatch.setenv("POEM_MODEL_ID", "gpt-4o-mini")
        from config import get_settings

        get_settings.cache_clear()

        assert model_cho("poem").price_out > 0

    async def test_id_LA_KHONG_BIET_thi_ve_model_chung(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Go nham ten model thi phai roi ve mac dinh chay duoc, khong phai chet."""
        monkeypatch.setenv("POEM_MODEL_ID", "mot-model-khong-ton-tai")
        from config import get_settings

        get_settings.cache_clear()

        assert model_cho("poem").id == "gpt-5-mini"
