"""CNKI Space -> kns.cnki.net mapping rules."""

from __future__ import annotations

from cnki_scholar.kns import (
    build_kns_url,
    dbcode_from_query,
    dbcode_from_space_url,
    filename_from_space_url,
    is_kns_url,
    to_kns_url,
)

KCMS = "https://kns.cnki.net/kcms/detail/detail.aspx"


def test_journal_article_url_maps_to_kns() -> None:
    space = "https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm"
    assert dbcode_from_space_url(space) == "CJFD"
    assert filename_from_space_url(space) == "ZXKC202625006"
    assert to_kns_url(space) == f"{KCMS}?dbcode=CJFD&filename=ZXKC202625006"


def test_protocol_relative_and_lowercase_variants() -> None:
    assert to_kns_url("//www.cnki.com.cn/Article/CJFDTOTAL-JYGS202616043.htm") == (
        f"{KCMS}?dbcode=CJFD&filename=JYGS202616043"
    )
    assert dbcode_from_space_url("https://www.cnki.com.cn/article/cjfdtotal-abc123.htm") == (
        "CJFD"
    )


def test_thesis_url_maps_to_cdmd() -> None:
    space = "https://cdmd.cnki.com.cn/Article/CDMD-10533-1025564694.htm"
    assert dbcode_from_space_url(space) == "CDMD"
    # The visible URL drops the .nh suffix; the caller must pass data-fn.
    assert filename_from_space_url(space) == "1025564694"
    assert to_kns_url(space) == f"{KCMS}?dbcode=CDMD&filename=1025564694"
    assert to_kns_url(space, dbcode="CDMD", filename="1025564694.nh") == (
        f"{KCMS}?dbcode=CDMD&filename=1025564694.nh"
    )


def test_explicit_dbcode_and_filename_win() -> None:
    space = "https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm"
    assert to_kns_url(space, dbcode="CJFDTOTAL", filename=" abc123 ") == (
        f"{KCMS}?dbcode=CJFD&filename=abc123"
    )


def test_kns_url_is_not_rewritten() -> None:
    already = f"{KCMS}?dbcode=CJFD&filename=ZXKC202625006"
    assert is_kns_url(already)
    assert to_kns_url(already) == already
    assert dbcode_from_query(already) == "CJFD"


def test_unknown_shapes_do_not_invent_a_link() -> None:
    assert to_kns_url("https://example.com/whatever.htm") is None
    assert to_kns_url("") is None
    assert to_kns_url(None) is None
    assert build_kns_url("CJFD", None) is None
    assert build_kns_url(None, "abc") is None
    # A dbcode too short to be real is rejected rather than truncated.
    assert build_kns_url("CJ", "abc") is None


def test_only_kns_host_counts_as_main_site() -> None:
    assert is_kns_url("https://kns.cnki.net/kcms/detail/detail.aspx?x=1")
    assert not is_kns_url("https://www.cnki.com.cn/Article/CJFDTOTAL-a.htm")
    assert not is_kns_url("https://kns.cnki.net.evil.example/x")


def test_anonymous_fallback_targets_are_host_correct() -> None:
    from cnki_scholar.service import _space_redirect_target

    # Theses need the granting-institution code, which only the 知网空间 path
    # carries. Every institution-less form 302s to /404.htm, so no link is
    # offered rather than a guessed one.
    assert _space_redirect_target("x", "CDMD", "1025564694.nh") is None
    assert _space_redirect_target("x", "CDFD", "1025564694.nh") is None
    assert _space_redirect_target("x", "CMFD", "1025564694.nh") is None
    assert _space_redirect_target("x", "CJFD", "ZXKC202625006") == (
        "https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm"
    )
    # Newspapers live on the magazine mall; the /Article/CCNDTOTAL- form 404s.
    assert _space_redirect_target("x", "CCND", "GJDW202505190013") == (
        "https://mall.cnki.net/magazine/article/CCND/GJDW202505190013.htm"
    )
    assert _space_redirect_target("x", "CJFD", None) is None
    assert _space_redirect_target("x", None, "abc") is None


def test_mall_path_filename_drops_the_leading_separator() -> None:
    mall = "https://mall.cnki.net/magazine/article/CCND/GJDW202505190013.htm"
    assert dbcode_from_space_url(mall) == "CCND"
    # "/GJDW..." is path syntax, not part of the file name: the canonical link
    # has no slash there.
    assert filename_from_space_url(mall) == "GJDW202505190013"
    assert to_kns_url(mall) == f"{KCMS}?dbcode=CCND&filename=GJDW202505190013"
    # Defensive: a caller that passes the unclean name gets the clean link.
    assert build_kns_url("CCND", "/GJDW202505190013") == (
        f"{KCMS}?dbcode=CCND&filename=GJDW202505190013"
    )


def test_not_found_pages_are_recognised() -> None:
    from cnki_scholar.parse import is_not_found_html

    # www.cnki.com.cn/404.htm: an empty-title shell (recorded from the live host).
    assert is_not_found_html('<html><head><title></title></head><body>x</body></html>')
    assert is_not_found_html("<html><body>no title at all</body></html>")
    # mall.cnki.net serves a 1 KB page titled "404" when it throttles.
    assert is_not_found_html("<html><head><title>404</title></head><body>x</body></html>")
    # A real, if sparse, record page is not a 404.
    assert not is_not_found_html(
        "<html><head><title>某报文章-《国家电网报》2025-05-19-中国知网</title></head></html>"
    )
    # An untitled page that still carries record fields is not a 404 either.
    assert not is_not_found_html('<html><body><a data-dbcode="CJFD" data-fn="x"></a></body></html>')


def test_detail_page_keeps_the_main_site_link() -> None:
    from cnki_scholar.parse import parse_detail_html

    html = """
    <html><head><title>深度学习--《中学课程辅导》2026年25期</title></head>
    <body>
      <a href="//pay.cnki.net/zscsdoc/download?filename=ZXKC202625006" data-fn="ZXKC202625006"
         data-dbcode="CJFD" data-dflag="pdfdown">下载</a>
    </body></html>
    """
    space = "https://www.cnki.com.cn/Article/CJFDTOTAL-ZXKC202625006.htm"
    detail = parse_detail_html(html, space)
    assert detail.url == (
        "https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=CJFD&filename=ZXKC202625006"
    )
    assert detail.space_url == space
