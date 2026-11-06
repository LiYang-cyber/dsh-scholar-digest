"""CNKI Space search and record lookup. Metadata only."""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from .client import (
    SearchField,
    SearchKind,
    SearchSort,
    fetch_detail,
    fetch_detail_lenient,
    fetch_listresult,
)
from .kns import dbcode_from_query, is_kns_url
from .models import Record, RecordDetail, SearchResponse
from .parse import (
    is_challenge_html,
    is_cnki_url,
    is_not_found_html,
    parse_detail_html,
    parse_list_html,
)

KIND_LABELS = {
    "journal": {"期刊"},
    "phd": {"博士论文"},
    "master": {"硕士论文"},
    "thesis": {"博士论文", "硕士论文"},
}

#: CNKI's "no such record" page, served with HTTP 200.
_NOT_FOUND_PATH = "/404"

#: Record types whose anonymous page URL carries the granting-institution code
#: (``CDMD-<institution>-<filename>.htm``). That code exists only in the 知网空间
#: path, so a kns.cnki.net ``dbcode``/``filename`` pair cannot rebuild it:
#: ``CDMD-<filename>.htm`` and ``CDMD-<filename>.nh.htm`` both 302 to /404.htm.
#: Refusing to invent one is the point -- a guessed URL is a wrong URL.
_INSTITUTION_SCOPED_DBCODES = frozenset({"CDMD", "CDFD", "CMFD"})


def _filter_kind(records: list[Record], kind: SearchKind) -> list[Record]:
    labels = KIND_LABELS.get(kind)
    if not labels:
        return records
    return [item for item in records if item.kind in labels]


def search_cnki(
    query: str,
    *,
    field: SearchField = "theme",
    page: int = 1,
    author: str | None = None,
    advisor: str | None = None,
    year: str | None = None,
    kind: SearchKind = "all",
    sort: SearchSort = "relevance",
) -> SearchResponse:
    query = " ".join(query.split())
    author = " ".join(author.split()) if author else None
    advisor = " ".join(advisor.split()) if advisor else None
    year = year.strip() if year else None
    if not query and not author and not advisor:
        return SearchResponse(status="error", query="", error="empty_query")
    page = min(max(int(page), 1), 50)
    started = time.perf_counter()
    try:
        http = fetch_listresult(
            query,
            field=field,
            page=page,
            author=author,
            advisor=advisor,
            year=year,
            kind=kind,
            sort=sort,
        )
    except ValueError as exc:
        return SearchResponse(status="error", query=query, page=page, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface transport to the MCP caller
        return SearchResponse(
            status="error",
            query=query,
            field=field,
            page=page,
            error=f"{type(exc).__name__}: {exc}",
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )

    elapsed = round((time.perf_counter() - started) * 1000)
    if http.status_code == 403 or is_challenge_html(http.text):
        return SearchResponse(
            status="blocked",
            query=query,
            field=field,
            page=page,
            elapsed_ms=elapsed,
            error="cnki_space_challenge",
        )
    if http.status_code >= 400:
        return SearchResponse(
            status="error",
            query=query,
            field=field,
            page=page,
            elapsed_ms=elapsed,
            error=f"http_{http.status_code}",
        )

    records = _filter_kind(parse_list_html(http.text), kind)
    warnings: list[str] = []
    unmapped = [item.title for item in records if not is_kns_url(item.url)]
    if unmapped:
        warnings.append(
            "cnki_link_unresolved: "
            + str(len(unmapped))
            + " record(s) returned the CNKI Space link because dbcode/filename "
            "could not be read; do not present these as CNKI main site links: "
            + "; ".join(unmapped[:3])
        )
    return SearchResponse(
        status="ok",
        query=query,
        field=field,
        page=page,
        returned_count=len(records),
        records=records,
        warnings=warnings,
        elapsed_ms=elapsed,
    )


def _space_fetch_target(url: str) -> tuple[str, str | None, str | None]:
    """Choose the page to fetch for ``get_record``.

    A ``kns.cnki.net`` link is tried directly, because on an institutional IP it
    serves the full record page. Callers may also pass a 知网空间 link, which is
    the only variant that works without any access rights.
    """
    if not is_kns_url(url):
        return url, None, None
    return url, dbcode_from_query(url), _query_value(url, "filename")


def _query_value(url: str, key: str) -> str | None:
    values = parse_qs(urlparse(url).query).get(key)
    return values[0] if values else None


def _space_redirect_target(url: str, dbcode: str | None, filename: str | None) -> str | None:
    """Fallback link on a host that serves anonymous metadata (mall / www).

    Returns None when no such link can be *derived*; the caller then reports the
    login wall instead of fetching a page that does not exist.
    """
    name = (filename or "").strip()
    code = (dbcode or "").upper()
    if not name or not code:
        return None
    if code in _INSTITUTION_SCOPED_DBCODES:
        return None
    # Newspapers are hosted on the magazine mall, not under /Article/<CODE>TOTAL-.
    if code == "CCND":
        return f"https://mall.cnki.net/magazine/article/CCND/{name.split('.')[0]}.htm"
    return f"https://www.cnki.com.cn/Article/{code}TOTAL-{name.split('.')[0]}.htm"


def _is_not_found_url(url: str) -> bool:
    """CNKI redirects unknown articles to its 404 page with HTTP 200."""
    return _NOT_FOUND_PATH in urlparse(url or "").path


def _not_found_warnings(url: str) -> list[str]:
    """Explain a miss that may really be throttling.

    ``mall.cnki.net`` answers with the very same 1 KB ``<title>404</title>`` page
    both for an article it does not have and while it is throttling, so a miss
    from that host is worth one retry instead of being read as "no such record".
    """
    host = (urlparse(url or "").hostname or "").lower()
    if host == "mall.cnki.net":
        return [
            "soft_404_on_mall_host: mall.cnki.net serves this same page while "
            "throttling, so the record may exist; retry before concluding it "
            "does not"
        ]
    return []


def _is_login_redirect(url: str) -> bool:
    return "login.cnki.net" in (url or "").lower()


def get_record(url: str) -> RecordDetail:
    url = url.strip()
    if not url:
        return RecordDetail(status="error", url="", error="empty_url")
    if not is_cnki_url(url):
        return RecordDetail(
            status="error",
            url=url,
            error="url_must_be_cnki",
        )
    started = time.perf_counter()
    fetch_url, dbcode, filename = _space_fetch_target(url)
    try:
        http, insecure = fetch_detail_lenient(fetch_url)
    except Exception as exc:  # noqa: BLE001
        return RecordDetail(
            status="error",
            url=url,
            error=f"{type(exc).__name__}: {exc}",
        )

    # A kns.cnki.net link redirects to the login page when the caller has no
    # institutional access. Retry on the anonymous host before giving up.
    logged_in_redirect = _is_login_redirect(http.url)
    if dbcode and logged_in_redirect:
        fallback = _space_redirect_target(fetch_url, dbcode, filename)
        if fallback:
            try:
                http, insecure = fetch_detail_lenient(fallback)
            except Exception:  # noqa: BLE001 - keep the login-page response
                pass

    if _is_login_redirect(http.url):
        # Still on the login wall: say so instead of blaming a captcha. The
        # login page happens to contain 验证码 wording, which would otherwise
        # read as a 知网空间 challenge.
        return RecordDetail(
            status="blocked",
            url=http.url,
            space_url=url,
            error="login_required_for_record",
        )

    if http.status_code == 403 or is_challenge_html(http.text):
        return RecordDetail(status="blocked", url=http.url, error="cnki_space_challenge")
    if http.status_code >= 400:
        return RecordDetail(status="error", url=http.url, error=f"http_{http.status_code}")
    # A nonexistent article answers 200; report it as a miss, never as a record.
    if _is_not_found_url(http.url) or is_not_found_html(http.text):
        return RecordDetail(
            status="error",
            url=http.url,
            space_url=url,
            warnings=_not_found_warnings(http.url),
            error="record_not_found",
        )

    detail = parse_detail_html(http.text, http.url)
    if insecure:
        detail.warnings.append(
            "metadata_read_over_unverified_tls: the cnki.com.cn mirror serves a "
            "certificate whose subject does not match the host name"
        )
    return detail
