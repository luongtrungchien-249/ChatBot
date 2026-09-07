"""MOT pool ket noi HTTP dung chung cho ca process.

BUG DA DO DUOC (07/09/2026). Sau cho trong codebase mo `httpx.AsyncClient(...)` ngay
trong ham goi, tuc la moi lan goi lai dung mot pool moi va bat tay TLS lai tu dau.

Do that tren duong embedding (30 lan goi lien tiep, cung mot API):

    client moi moi lan   p50 282ms   p90 1062ms   max 20016ms   tong 33,5s
    client dung chung    p50 188ms   p90  360ms   max   578ms   tong  6,8s

`max 20016ms` chinh la trần timeout 20s: mot lan bat tay treo den het gio roi duoc
retry. Trong `usage_log`, 96 tren 1493 lan embed (6,4%) vuot 19s va cham nhat la 41s
CHO MOT INPUT 8 TOKEN — khong phai API cham, ma la ta tu tao lai ket noi.

Vi sao dieu do quan trong o day chu khong o mot script: `web_search`, `paper_search`,
rerank va embedding deu nam TRONG duong phan hoi, va Zalo `sendMessage` cung vay.

Timeout truyen theo TUNG lan goi, khong dat o client: mot vong long-poll cho 25 giay
va mot lan gui tin cho 10 giay khong dung chung duoc mot con so.
"""

import httpx

#: Chan so ket noi giu mo. Du rong cho fan-out bon nguon cua paper_search chay song
#: song, du hep de mot su co ben kia khong bien thanh vai tram ket noi treo ben nay.
_LIMITS = httpx.Limits(max_connections=32, max_keepalive_connections=16)

_client: httpx.AsyncClient | None = None


def get_http() -> httpx.AsyncClient:
    """Client dung chung. Truyen `timeout=` o TUNG lan goi.

    Tao luoi luc goi dau tien chu khong luc import: httpx gan client vao event loop
    dang chay, va o thoi diem import thi chua co loop nao.
    """
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            limits=_LIMITS,
            # arXiv va Crossref deu tra 301 sang https/duong dan khac. Mac dinh cua
            # httpx la KHONG di theo, nen thieu dong nay la mat lang mot nguon.
            follow_redirects=True,
        )
    return _client


async def close_http() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
