"""Rate limit ba tang + chot chan ngan sach ngay.

| Tang | Nguong | Cuong che o dau |
|---|---|---|
| user | RL_USER_PER_MIN | check() — token bucket |
| thread | RL_THREAD_PER_MIN | check() — token bucket |
| global | DAILY_BUDGET_USD | within_daily_budget() — stage 5 + moi vong ReAct |

Ngan sach ngay tinh theo gio Viet Nam, khong theo UTC: "hom nay" phai trung voi
hom nay cua nguoi dung, khong lech 7 tieng.
"""

import time
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from agents.domain.thread import ThreadScope
from agents.ports.ratelimit import Allowed, Denied, LimitVerdict
from config import get_settings

from .logger import get_logger
from .redis_client import aw, get_redis

_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
_COST_DAY_TTL_SECONDS = 172_800  # 48h, xem section 6.5

#: Toi da MOT cau nhac "cham lai" cho mot thread trong 5 phut (section 9).
_WARN_COOLDOWN_SECONDS = 300

_log = get_logger()

#: Token bucket cho HAI tang trong MOT script.
#:
#: Vi sao Lua chu khong phai INCR roi EXPIRE: hai lenh la hai vong, va giua chung
#: co the mat ket noi — de lai mot khoa KHONG CO TTL, tuc la nguoi dung do bi chan
#: vinh vien. Lua chay tron ven tren server, khong co khe ho do.
#:
#: Vi sao mot script cho ca hai tang chu khong phai hai lan goi: phai PEEK ca hai
#: truoc roi moi TRU ca hai. Goi rieng thi khi tang thread het luot, luot cua nguoi
#: dung DA bi tru mat cho mot cau bot khong tra loi.
#:
#: Vi sao token bucket chu khong phai dem theo cua so co dinh: cua so co dinh cho
#: phep gap doi nguong o ranh gioi (10 tin luc 10:00:59 + 10 tin luc 10:01:00).
#:
#: `now` do CLIENT truyen vao chu khong dung TIME cua Redis: TIME lam script khong
#: xac dinh (khong replicate duoc), va truyen vao thi test bom duoc thoi gian gia.
_BUCKET_SCRIPT = """
local now = tonumber(ARGV[5])

-- So token con lai sau khi do day theo thoi gian da troi. Khong ghi gi.
local function refill(key, capacity, rate)
  local data = redis.call('HMGET', key, 'tokens', 'ts')
  local tokens, ts = tonumber(data[1]), tonumber(data[2])
  if tokens == nil or ts == nil then
    return capacity   -- lan dau thay khoa nay: gau day
  end
  local elapsed = math.max(0, now - ts) / 1000.0
  return math.min(capacity, tokens + elapsed * rate)
end

local user_cap, user_rate = tonumber(ARGV[1]), tonumber(ARGV[2])
local thread_cap, thread_rate = tonumber(ARGV[3]), tonumber(ARGV[4])

local user_tokens = refill(KEYS[1], user_cap, user_rate)
local thread_tokens = refill(KEYS[2], thread_cap, thread_rate)

if user_tokens < 1 then
  return {1, math.ceil((1 - user_tokens) / user_rate * 1000), 'user'}
end
if thread_tokens < 1 then
  return {1, math.ceil((1 - thread_tokens) / thread_rate * 1000), 'thread'}
end

local function commit(key, tokens, capacity, rate)
  redis.call('HSET', key, 'tokens', string.format('%.6f', tokens - 1), 'ts', tostring(now))
  -- TTL = thoi gian do day lai ca gau, cong mot chut. Gau da day thi giu lai cung
  -- khong noi them dieu gi, va de no het han giup Redis khong phinh theo so nguoi.
  redis.call('PEXPIRE', key, math.ceil(capacity / rate * 1000) + 1000)
end

commit(KEYS[1], user_tokens, user_cap, user_rate)
commit(KEYS[2], thread_tokens, thread_cap, thread_rate)
return {0, 0, ''}
"""


def cost_day_key(now: datetime | None = None) -> str:
    """cost:day:{YYYY-MM-DD}. Mot noi duy nhat dung khoa nay.

    llm/cost_meter.py ghi, o day doc.
    """
    moment = now or datetime.now(_TIMEZONE)
    return f"cost:day:{moment.astimezone(_TIMEZONE):%Y-%m-%d}"


async def spent_today(now: datetime | None = None) -> float:
    raw = await get_redis().get(cost_day_key(now))
    return float(raw) if raw is not None else 0.0


def bucket_args(user_per_min: int, thread_per_min: int, now_ms: int) -> list[str]:
    """ARGV cho _BUCKET_SCRIPT, DA thanh chuoi.

    Ep chuoi tuong minh chu khong pho mac cho redis-py: truyen mot float vao thi
    thu vien client tu chon cach in no, va `repr()` cua Python co the ra dang mu
    ('1e-05') ma `tonumber` cua Lua doc duoc nhung khong ai muon phu thuoc vao do.
    Dinh dang co dinh o day thi cai gi den Redis la cai ta viet ra.
    """
    return [
        str(user_per_min),
        f"{user_per_min / 60.0:.9f}",
        str(thread_per_min),
        f"{thread_per_min / 60.0:.9f}",
        str(now_ms),
    ]


class RedisRateLimit:
    """Implement RateLimitPort."""

    async def check(self, scope: ThreadScope, sender_id: str) -> LimitVerdict:
        settings = get_settings()
        try:
            raw = await aw(
                get_redis().eval(
                    _BUCKET_SCRIPT,
                    2,
                    f"rl:u:{scope.platform}:{sender_id}",
                    f"rl:t:{scope.platform}:{scope.thread_id}",
                    *bucket_args(
                        settings.RL_USER_PER_MIN,
                        settings.RL_THREAD_PER_MIN,
                        int(time.time() * 1000),
                    ),
                )
            )
        except Exception as error:
            # Redis hong thi CHO QUA, khong chan. Rate limit la lop chong lam dung,
            # khong phai lop bao mat: chan sach moi nguoi vi mot su co ha tang la
            # doi mot van de nho lay mot van de to. Chot chan tien van con nguyen —
            # within_daily_budget() doc Redis rieng va tu fail-closed.
            _log.error("rate limit khong doc duoc Redis — cho qua", err=str(error))
            return Allowed()

        # Script tra ve {co_bi_chan, retry_after_ms, tang}. Client dat
        # decode_responses=True nen phan tu thu ba la str, khong phai bytes.
        result = cast(list[Any], raw)
        if int(result[0]) == 0:
            return Allowed()
        return Denied(retry_after_ms=int(result[1]), tier=cast(Any, str(result[2])))

    async def should_warn(self, scope: ThreadScope) -> bool:
        """SET NX la ATOMIC. Tuyet doi khong GET roi SET: hai tin ve cung luc se
        cung thay "chua canh bao" va nhom nhan hai cau nhac lien tiep.
        """
        key = f"rl:warn:{scope.platform}:{scope.thread_id}"
        try:
            claimed = await aw(get_redis().set(key, "1", ex=_WARN_COOLDOWN_SECONDS, nx=True))
        except Exception as error:
            # Khong biet da canh bao chua thi IM LANG. Nham im con hon nham spam:
            # nguoi dung chi mat mot cau nhac, con lua chon kia lam bot spam nhom.
            _log.warning("khong kiem duoc co canh bao — im lang", err=str(error))
            return False
        return bool(claimed)

    async def within_daily_budget(self) -> bool:
        """CHOT CHAN CUNG, khong phai alert. Vuot ngan sach thi tu choi tra loi.

        "Mot nhom 50 nguoi nghich bot co the dot sach ngan sach thang trong mot buoi
        chieu" — day la cho bien canh bao do thanh mot cau lenh if.
        """
        try:
            spent = await spent_today()
        except ValueError:
            _log.error("cost:day khong doc duoc so — coi nhu het ngan sach", key=cost_day_key())
            return False
        except Exception as error:
            # FAIL-CLOSED, va day la cho KHAC han check() o tren.
            #
            # Rate limit hong thi cho qua: no la lop chong lam dung. Chot chan tien
            # thi nguoc lai — khong doc duoc so da tieu ma van cho goi model nghia la
            # mot su co Redis bien thanh mot hoa don khong co tran.
            #
            # Nguoi dung se thay cau "het ngan sach hom nay", khong dung han nguyen
            # nhan. Do la danh doi co y: cau dung nguyen nhan ("mat ket noi Redis")
            # la thong tin van hanh, chi thuoc ve log. Dong ERROR duoi day moi la
            # cho noi that.
            _log.error(
                "khong doc duoc cost:day — FAIL-CLOSED, tu choi tra loi",
                key=cost_day_key(),
                err=str(error),
            )
            return False

        budget = get_settings().DAILY_BUDGET_USD
        within = spent < budget
        if not within:
            _log.warning("vuot ngan sach ngay, dung tra loi", spent=spent, budget=budget)
        return within


async def add_cost(amount: float, now: datetime | None = None) -> None:
    """Cong don chi tieu trong ngay. Goi tu llm/cost_meter.py.

    MOT vong mang, khong phai hai. Cung ly do da viet o _BUCKET_SCRIPT: mat ket noi
    giua INCRBYFLOAT va EXPIRE de lai mot khoa khong co TTL. O day hau qua nhe hon
    (khoa cost:day co ten theo ngay nen khong chan ai) nhung no ro ri khoa vinh vien
    trong Redis, va khong co ly do gi de giu hai vong.
    """
    key = cost_day_key(now)
    pipe = get_redis().pipeline()
    pipe.incrbyfloat(key, amount)
    pipe.expire(key, _COST_DAY_TTL_SECONDS)
    await pipe.execute()


rate_limit = RedisRateLimit()
