"""CNKI Space -> CNKI main site (``kns.cnki.net``) link mapping.

Every CNKI record is identified by a ``dbcode`` plus a ``filename``; those two
values are enough to build the canonical main-site link::

    https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=<dbcode>&filename=<filename>

A 知网空间 record page exposes both values, and they can be read from two
independent anchors:

1. the download button carries ``data-dbcode`` and ``data-fn``;
2. the source line links to ``/<dbalias>/Detail/RedirectSpace/<filename>``.

The ``data-fn`` value is authoritative for the file name: thesis records keep
their ``.nh`` suffix there (``1025564694.nh``) even though the human-facing URL
drops it (``CDMD-10533-1025564694.htm``). Deriving the suffix by hand is what
CNKI-Redirect has to do for pages that lack the attribute; here it is not
needed.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

KCMS_DETAIL_URL = "https://kns.cnki.net/kcms/detail/detail.aspx"

# 知网空间 path segment -> CNKI database code. Segments are the lowercase form
# of the common codes; TOTAL and other suffixes are padding, not part of it.
DB_ALIASES: dict[str, str] = {
    "cjfd": "CJFD",  # 中国学术期刊
    "cdfd": "CDFD",  # 博士学位论文 (legacy)
    "cmfd": "CMFD",  # 硕士学位论文 (legacy)
    "cdmd": "CDMD",  # 博硕士学位论文
    "ccjd": "CCJD",  # 会议论文
    "cipd": "CIPD",  # 会议论文 (legacy)
    "ccnd": "CCND",  # 报纸
    "cyfd": "CYFD",  # 年鉴
    "cacd": "CACD",  # 专利
    "scpd": "SCPD",  # 标准
    "crld": "CRLD",  # 法律法规
}

# /Article/CDMD-10533-1025564694.htm
_ARTICLE_DB_PREFIX = re.compile(r"/Article/(?P<prefix>[A-Za-z]{4})(?P<tail>.+?)\.htm", re.I)
# /cjfd/Detail/RedirectSpace/ZXKC202625006
_REDIRECT_SPACE = re.compile(
    r"/(?P<alias>[a-z]{3,6})/Detail/RedirectSpace/(?P<filename>[^/?#]+)", re.I
)
_YEAR_PREFIX = re.compile(r"^(?:19|20)\d{2}[-_]")


def _normalize_dbcode(value: str | None) -> str | None:
    """``CJFDTOTAL`` / ``cjfd`` -> ``CJFD``."""
    if not value:
        return None
    cleaned = re.sub(r"[^A-Za-z]", "", value).upper()
    if len(cleaned) < 4:
        return None
    return cleaned[:4]


def dbcode_from_space_url(url: str) -> str | None:
    """Derive the database code from a 知网空间 record or article URL."""
    parsed = urlparse(url if "//" in url else "https:" + url)
    match = _REDIRECT_SPACE.search(parsed.path)
    if match:
        alias = _normalize_dbcode(match.group("alias"))
        if alias:
            return alias
    match = _ARTICLE_DB_PREFIX.search(parsed.path)
    if match:
        return _normalize_dbcode(match.group("prefix"))
    return None


def filename_from_space_url(url: str) -> str | None:
    """Derive the CNKI file name from a 知网空间 record or article URL.

    Only a fallback: prefer the page's ``data-fn`` attribute, which keeps the
    ``.nh`` suffix that thesis file names require.
    """
    parsed = urlparse(url if "//" in url else "https:" + url)
    match = _REDIRECT_SPACE.search(parsed.path)
    if match:
        return (match.group("filename") or "").lstrip("/") or None
    match = _ARTICLE_DB_PREFIX.search(parsed.path)
    if not match:
        return None
    tail = match.group("tail")
    # CDMD-10533-1025564694 -> 1025564694 ; CJFDTOTAL-ZXKC202625006 -> ZXKC202625006
    tail = tail.split("-")[-1]
    # mall.cnki.net/magazine/article/CCND/<filename>.htm reaches here as
    # "/<filename>": the leading separator is path syntax, not part of the name.
    tail = tail.lstrip("/")
    tail = _YEAR_PREFIX.sub("", tail)
    return tail or None


def dbcode_from_query(url: str) -> str | None:
    """Read ``dbcode`` back out of an already-built main-site link."""
    query = parse_qs(urlparse(url).query)
    for key in ("dbcode", "dbname", "dbtype"):
        values = query.get(key)
        if values:
            code = _normalize_dbcode(values[0])
            if code:
                return code
    return None


def build_kns_url(dbcode: str | None, filename: str | None) -> str | None:
    """Build the canonical ``kns.cnki.net`` link, or None when incomplete.

    A leading ``/`` is stripped rather than kept: callers that scrape the name
    out of a path segment (mall.cnki.net does this) would otherwise emit
    ``filename=/GJDW202505190013``, which is not the canonical link.
    """
    code = _normalize_dbcode(dbcode)
    name = (filename or "").strip().lstrip("/")
    if not code or not name:
        return None
    return f"{KCMS_DETAIL_URL}?dbcode={code}&filename={name}"


def is_kns_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "kns.cnki.net" or host.endswith(".kns.cnki.net")


def to_kns_url(
    space_url: str | None,
    *,
    dbcode: str | None = None,
    filename: str | None = None,
) -> str | None:
    """Map a CNKI Space URL to its CNKI main-site link.

    ``dbcode`` and ``filename`` are used when supplied (they come from the list
    page's own attributes) and are derived from ``space_url`` otherwise.
    """
    if space_url and is_kns_url(space_url):
        return space_url
    code = _normalize_dbcode(dbcode) or dbcode_from_space_url(space_url or "")
    name = (filename or "").strip() or filename_from_space_url(space_url or "")
    return build_kns_url(code, name)
