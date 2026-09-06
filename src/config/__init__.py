"""Doc config MOT LAN luc import, roi dong bang.

Moi cho khac trong codebase import `settings` tu day chu khong tu doc os.environ.
"""

from functools import lru_cache

from .schema import Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Doc va kiem tra env. Thieu bien -> nem ngay luc khoi dong.

    lru_cache de doc dung mot lan; cung la cho de test ghi de bang
    get_settings.cache_clear() khi can.
    """
    return Settings()  # type: ignore[call-arg]  # gia tri den tu env, khong tu tham so
