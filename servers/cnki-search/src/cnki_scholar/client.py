"""HTTP client for the public 知网空间 search surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from curl_cffi import requests

SEARCH_PAGE_URL = "https://search.cnki.com.cn/Search/Result"
LISTRESULT_URL = "https://search.cnki.com.cn/search/listresult"

SearchField = Literal["theme", "title", "keyword", "content", "summary"]
SearchKind = Literal["all", "journal", "thesis", "phd", "master"]
SearchSort = Literal["relevance", "date", "downloads", "cites"]

FIELD_TO_PARAM = {
    "theme": "Theme",
    "title": "Title",
    "keyword": "KeyWd",
    "content": "Content",
    "summary": "Summary",
}
SORT_TO_ORDER = {
    "relevance": 1,
    "date": 2,
    "downloads": 3,
    "cites": 4,
}


def build_listresult_payload(
    query: str,
    *,
    field: SearchField = "theme",
    page: int = 1,
    author: str | None = None,
    advisor: str | None = None,
    year: str | None = None,
    kind: SearchKind = "all",
    sort: SearchSort = "relevance",
) -> dict[str, str | int]:
    if field not in FIELD_TO_PARAM:
        raise ValueError(f"unsupported_field:{field}")
    if sort not in SORT_TO_ORDER:
        raise ValueError(f"unsupported_sort:{sort}")
    payload: dict[str, str | int] = {
        "searchType": "MulityTermsSearch",
        "Page": page,
        "Order": SORT_TO_ORDER[sort],
    }
    if query:
        payload[FIELD_TO_PARAM[field]] = query
    if author:
        payload["Author"] = author
    if advisor:
        payload["Boss"] = advisor
    if year:
        payload["Year"] = year
    # Type=1 is journals on 知网空间. Other type codes are unreliable; thesis
    # filtering is applied after parse.
    if kind == "journal":
        payload["Type"] = 1
        payload["ArticleType"] = 1
    return payload


@dataclass(slots=True)
class HttpResult:
    status_code: int
    url: str
    text: str
    content_type: str


def _session() -> requests.Session:
    session = requests.Session(impersonate="chrome")
    session.headers.update(
        {
            "Accept": "text/html, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Origin": "https://search.cnki.com.cn",
            "Referer": "https://search.cnki.com.cn/",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return session


def fetch_listresult(
    query: str,
    *,
    field: SearchField = "theme",
    page: int = 1,
    author: str | None = None,
    advisor: str | None = None,
    year: str | None = None,
    kind: SearchKind = "all",
    sort: SearchSort = "relevance",
    timeout: float = 25,
) -> HttpResult:
    session = _session()
    warmup = query or author or advisor or "知网"
    session.get(SEARCH_PAGE_URL, params={"content": warmup}, timeout=timeout)
    payload = build_listresult_payload(
        query,
        field=field,
        page=page,
        author=author,
        advisor=advisor,
        year=year,
        kind=kind,
        sort=sort,
    )
    response = session.post(LISTRESULT_URL, data=payload, timeout=timeout)
    return HttpResult(
        status_code=int(response.status_code),
        url=str(response.url),
        text=response.text,
        content_type=response.headers.get("content-type", ""),
    )


def fetch_detail(url: str, *, timeout: float = 25) -> HttpResult:
    session = _session()
    response = session.get(url, timeout=timeout, allow_redirects=True)
    return HttpResult(
        status_code=int(response.status_code),
        url=str(response.url),
        text=response.text,
        content_type=response.headers.get("content-type", ""),
    )


def fetch_detail_lenient(url: str, *, timeout: float = 25) -> tuple[HttpResult, bool]:
    """``fetch_detail`` that survives the certificate mismatch on cnki.com.cn.

    ``www.cnki.com.cn`` currently serves a certificate whose subject does not
    match the host name, so a browser-less client cannot verify it. That host is
    an anonymous metadata mirror: the content carries no credentials, no cookies
    and no downloads, so one unverified retry is the pragmatic way to keep
    abstract lookup working. The verified attempt always runs first.

    Returns ``(result, used_unverified_retry)``.
    """
    try:
        return fetch_detail(url, timeout=timeout), False
    except Exception as exc:  # noqa: BLE001 - only cert failures fall through
        if "certificate" not in f"{type(exc).__name__} {exc}".lower():
            raise
    session = _session()
    response = session.get(url, timeout=timeout, allow_redirects=True, verify=False)
    return (
        HttpResult(
            status_code=int(response.status_code),
            url=str(response.url),
            text=response.text,
            content_type=response.headers.get("content-type", ""),
        ),
        True,
    )
