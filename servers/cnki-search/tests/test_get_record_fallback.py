"""get_record must survive the login wall and the cnki.com.cn certificate mismatch."""

from __future__ import annotations

import pytest

from cnki_scholar import service
from cnki_scholar.client import HttpResult
from cnki_scholar.service import _is_login_redirect, _space_redirect_target

KCMS = "https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=CJFD&filename=ZXKC202625006"
LOGIN = (
    "https://login.cnki.net/login/?returnUrl=http%3A%2F%2Fkns.cnki.net%3A80%2Fkcms"
    "%2Fdetail%2Fdetail.aspx%3Ffilename%3DZXKC202625006%26dbcode%3DCJFD"
)
ARTICLE_HTML = """
<html><head><title>深度学习--《中学课程辅导》2026年25期</title></head><body>
<a href="//pay.cnki.net/x" data-fn="ZXKC202625006" data-dbcode="CJFD">下载</a>
</body></html>
"""


def _result(url: str, text: str = "", status: int = 200) -> HttpResult:
    return HttpResult(status_code=status, url=url, text=text, content_type="text/html")


def test_login_redirect_is_recognised() -> None:
    assert _is_login_redirect(LOGIN)
    assert _is_login_redirect("https://login.cnki.net/login/")
    assert not _is_login_redirect(KCMS)


def test_fallback_hosts_match_record_type() -> None:
    assert _space_redirect_target(KCMS, "CJFD", "ZXKC202625006") == (
        "https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm"
    )
    assert _space_redirect_target(KCMS, "CCND", "GJDW202505190013") == (
        "https://mall.cnki.net/magazine/article/CCND/GJDW202505190013.htm"
    )
    # No derivable anonymous page exists for a thesis: the institution code is
    # only in the 知网空间 path.
    assert _space_redirect_target(KCMS, "CDMD", "1025564694.nh") is None
    assert _space_redirect_target(KCMS, None, "abc") is None
    assert _space_redirect_target(KCMS, "CJFD", None) is None


def test_thesis_login_wall_is_reported_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A kns thesis link cannot fall back anywhere, so say so."""
    thesis = "https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=CDMD&filename=1025564694.nh"
    calls: list[str] = []

    def fake(url: str, *, timeout: float = 25):
        calls.append(url)
        return _result(LOGIN, "<html>验证码</html>"), False

    monkeypatch.setattr(service, "fetch_detail_lenient", fake)
    detail = service.get_record(thesis)

    assert calls == [thesis], "no fallback request may be attempted"
    assert detail.status == "blocked"
    assert detail.error == "login_required_for_record"


def test_nonexistent_article_is_not_reported_as_a_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CNKI answers a missing article with HTTP 200 on its /404.htm shell."""
    missing = "https://www.cnki.com.cn/Article/CJFDTOTAL-ZZZZ99999999.htm"

    def fake(url: str, *, timeout: float = 25):
        return _result("https://www.cnki.com.cn/404.htm", "<html><head><title></title></head></html>"), False

    monkeypatch.setattr(service, "fetch_detail_lenient", fake)
    detail = service.get_record(missing)

    assert detail.status == "error"
    assert detail.error == "record_not_found"
    assert detail.title is None


def test_mall_soft_404_is_not_reported_as_a_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mall.cnki.net throttles to a 1 KB page whose title is literally 404."""
    target = "https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm"

    def fake(url: str, *, timeout: float = 25):
        return _result(url, "<html><head><title>404</title></head></html>"), False

    monkeypatch.setattr(service, "fetch_detail_lenient", fake)
    detail = service.get_record(target)

    assert detail.status == "error"
    assert detail.error == "record_not_found"
    # Not the mall host: a plain miss, with nothing to retry.
    assert detail.warnings == []


def test_mall_miss_says_it_may_be_throttling(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same page means both "absent" and "throttled" on mall.cnki.net."""
    mall = "https://mall.cnki.net/magazine/article/CCND/GJDW202505190013.htm"

    def fake(url: str, *, timeout: float = 25):
        return _result(url, "<html><head><title>404</title></head></html>"), False

    monkeypatch.setattr(service, "fetch_detail_lenient", fake)
    detail = service.get_record(mall)

    assert detail.status == "error"
    assert detail.error == "record_not_found"
    assert any("soft_404_on_mall_host" in w for w in detail.warnings)


def test_get_record_falls_back_past_the_login_wall(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake(url: str, *, timeout: float = 25):
        calls.append(url)
        if "kns.cnki.net" in url:
            return _result(LOGIN, "<html>验证码</html>"), False
        return _result("https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm", ARTICLE_HTML), True

    monkeypatch.setattr(service, "fetch_detail_lenient", fake)
    detail = service.get_record(KCMS)

    assert calls[0] == KCMS, "the main-site link must be tried first"
    assert calls[1].endswith("CJFDTOTAL-ZXKC202625006.htm")
    assert detail.status == "ok"
    assert detail.url == KCMS, "the main-site link must be reported, not the mirror"
    assert detail.space_url.endswith("CJFDTOTAL-ZXKC202625006.htm")
    assert any("unverified_tls" in w for w in detail.warnings)


def test_get_record_reports_login_required_not_a_captcha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Both attempts land on the login wall (fallback host unreachable).
    def fake(url: str, *, timeout: float = 25):
        return _result(LOGIN, "<html>验证码</html>"), False

    monkeypatch.setattr(service, "fetch_detail_lenient", fake)
    detail = service.get_record(KCMS)

    assert detail.status == "blocked"
    # The login page contains 验证码 wording; that must not be reported as a
    # 知网空间 challenge.
    assert detail.error == "login_required_for_record"


def test_space_link_still_reads_without_login(monkeypatch: pytest.MonkeyPatch) -> None:
    space = "https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm"
    calls: list[str] = []

    def fake(url: str, *, timeout: float = 25):
        calls.append(url)
        return _result(space, ARTICLE_HTML), False

    monkeypatch.setattr(service, "fetch_detail_lenient", fake)
    detail = service.get_record(space)

    assert calls == [space], "no fallback needed when already on the anonymous host"
    assert detail.status == "ok"
    assert detail.url == KCMS


def test_lenient_fetch_only_retries_on_certificate_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cnki_scholar import client

    def boom(url: str, *, timeout: float = 25):
        raise ConnectionError("connection reset by peer")

    monkeypatch.setattr(client, "fetch_detail", boom)
    with pytest.raises(ConnectionError):
        client.fetch_detail_lenient("https://www.cnki.com.cn/x.htm")


def test_lenient_fetch_retries_certificate_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from cnki_scholar import client

    def cert_fail(url: str, *, timeout: float = 25):
        raise RuntimeError("SSL: no alternative certificate subject name matches target hostname")

    seen: dict = {}

    class FakeResponse:
        status_code = 200
        url = "https://www.cnki.com.cn/x.htm"
        text = "<html>ok</html>"
        headers = {"content-type": "text/html"}

    class FakeSession:
        def get(self, url, **kwargs):
            seen.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(client, "fetch_detail", cert_fail)
    monkeypatch.setattr(client, "_session", lambda: FakeSession())

    result, insecure = client.fetch_detail_lenient("https://www.cnki.com.cn/x.htm")
    assert insecure is True
    assert result.status_code == 200
    assert seen.get("verify") is False
