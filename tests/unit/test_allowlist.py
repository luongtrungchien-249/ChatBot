"""Allowlist quyet dinh bot co noi hay khong. Sai o day = bot cam trong moi nhom."""

from agents.domain.thread import ThreadScope, scope_key
from agents.policy.access import AccessRules, is_allowed
from infra.allowlist import row_key


def test_khop_scope_key() -> None:
    """row_key (doc tu Postgres) phai cho ra dung chuoi ma is_allowed di so sanh.

    Hai ham dung hai kieu du lieu khac nhau (str vs Literal) nen khong goi chung
    duoc. Lech mot ky tu thi allowlist khong khop gi ca, va trieu chung la "bot
    im lang" — khong co thong bao loi nao.
    """
    scope = ThreadScope(platform="zalo_bot", thread_id="group-abc")
    assert row_key("zalo_bot", "group-abc") == scope_key(scope)


class TestIsAllowedVoiAllowlistThat:
    def _rules(self, *keys: str) -> AccessRules:
        return AccessRules(
            group_policy="allowlist", dm_policy="allowlist", allowed_threads=frozenset(keys)
        )

    def test_nhom_trong_allowlist_thi_duoc(self) -> None:
        scope = ThreadScope(platform="zalo_bot", thread_id="g1")
        assert is_allowed(scope, True, self._rules(row_key("zalo_bot", "g1"))) is True

    def test_nhom_ngoai_allowlist_thi_khong(self) -> None:
        scope = ThreadScope(platform="zalo_bot", thread_id="g2")
        assert is_allowed(scope, True, self._rules(row_key("zalo_bot", "g1"))) is False

    def test_cung_thread_id_khac_nen_tang_KHONG_dung_chung_quyen(self) -> None:
        # Khoa la (platform, thread_id). Mo mot nhom Zalo khong duoc mo luon mot
        # thread web trung id.
        allowed = self._rules(row_key("zalo_bot", "x"))
        assert is_allowed(ThreadScope(platform="web", thread_id="x"), True, allowed) is False

    def test_dm_policy_open_thi_khong_can_allowlist(self) -> None:
        rules = AccessRules(
            group_policy="allowlist", dm_policy="open", allowed_threads=frozenset()
        )
        scope = ThreadScope(platform="zalo_bot", thread_id="u1")
        assert is_allowed(scope, False, rules) is True
        # ...nhung nhom thi van phai xin phep.
        assert is_allowed(scope, True, rules) is False
