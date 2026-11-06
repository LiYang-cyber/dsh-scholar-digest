from __future__ import annotations

from pathlib import Path

from cnki_scholar.parse import is_challenge_html, parse_detail_html, parse_list_html

FIXTURES = Path(__file__).parent / "fixtures"

PENG_TITLE = "SCA3发病年龄的临床预测模型构建与罕见变异关联研究"


def test_parse_peng_listresult_maps_thesis_to_kns_url() -> None:
    html = (FIXTURES / "listresult_peng_sca3.html").read_text(encoding="utf-8")
    records = parse_list_html(html)
    assert records, "shipped parser must see at least one list-item"
    match = next((item for item in records if PENG_TITLE in item.title), None)
    assert match is not None
    # The main-site link, built from the record's own dbcode + filename.
    assert match.url.startswith("https://kns.cnki.net/kcms/detail/detail.aspx?")
    assert "dbcode=CDMD" in match.url
    # data-fn keeps the .nh suffix that the visible URL drops.
    assert "filename=1025564694.nh" in match.url
    assert match.dbcode == "CDMD"
    assert match.filename == "1025564694.nh"
    assert match.space_url and "cdmd.cnki.com.cn" in match.space_url
    assert match.authors and "彭林柳" in match.authors
    assert match.year == "2023"
    assert match.kind == "博士论文"


def test_parse_journal_listresult_maps_to_kns_url() -> None:
    html = (FIXTURES / "listresult_journal.html").read_text(encoding="utf-8")
    records = parse_list_html(html)
    assert records
    first = records[0]
    assert first.title
    assert first.url.startswith("https://kns.cnki.net/kcms/detail/detail.aspx?")
    assert "dbcode=CJFD" in first.url
    assert first.dbcode == "CJFD"
    assert first.filename
    assert first.space_url and "cnki.com.cn" in first.space_url


def test_challenge_html_is_detected_and_has_no_records() -> None:
    html = (FIXTURES / "challenge_kns.html").read_text(encoding="utf-8")
    assert is_challenge_html(html)
    assert parse_list_html(html) == []


def test_parse_detail_reads_degree_fields() -> None:
    html = """
    <html><head><title>SCA3发病年龄的临床预测模型构建与罕见变异关联研究--《中南大学》2023年博士论文</title></head>
    <body>
    【摘要】：背景: 脊髓小脑性共济失调3型。
    【学位授予单位】： 中南大学
    【学位级别】： 博士
    【学位授予年份】： 2023
    </body></html>
    """
    detail = parse_detail_html(html, "https://cdmd.cnki.com.cn/Article/CDMD-10533-1025564694.htm")
    assert detail.status == "ok"
    assert PENG_TITLE in (detail.title or "")
    assert detail.institution == "中南大学"
    assert detail.degree == "博士"
    assert detail.year == "2023"
    assert detail.abstract and "脊髓小脑" in detail.abstract
