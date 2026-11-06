from __future__ import annotations

import os

import pytest

from cnki_scholar.kns import build_kns_url
from cnki_scholar.service import get_record, search_cnki

PENG_TITLE = "SCA3发病年龄的临床预测模型构建与罕见变异关联研究"
JOURNAL_SPACE = "https://www.cnki.com.cn/Article/CJFDTOTAL-DGJY202522081.htm"
ABSENT = "https://www.cnki.com.cn/Article/CJFDTOTAL-ZZZZ99999999.htm"


def _live() -> None:
    if os.environ.get("RUN_LIVE_CNKI") != "1":
        pytest.skip("set RUN_LIVE_CNKI=1 to hit 知网空间")


@pytest.mark.live
def test_live_search_peng_dissertation() -> None:
    _live()
    response = search_cnki(PENG_TITLE, field="title")
    assert response.status == "ok", response.error
    hit = next((item for item in response.records if PENG_TITLE in item.title), None)
    assert hit is not None
    # search reports the CNKI main-site link in url, not the 知网空间 page.
    assert hit.url.startswith("https://kns.cnki.net/kcms/detail/detail.aspx?")
    assert hit.space_url and hit.space_url.startswith("http")
    assert hit.url == build_kns_url(hit.dbcode, hit.filename)


@pytest.mark.live
def test_live_space_url_round_trips_to_the_same_main_site_link() -> None:
    _live()
    detail = get_record(JOURNAL_SPACE)
    assert detail.status == "ok", detail.error
    assert detail.url == build_kns_url("CJFD", "DGJY202522081")
    assert detail.space_url == JOURNAL_SPACE
    assert detail.title


@pytest.mark.live
def test_live_missing_article_is_reported_as_not_found() -> None:
    _live()
    # The host answers HTTP 200 with its /404.htm shell; that is a miss, not a record.
    detail = get_record(ABSENT)
    assert detail.status == "error"
    assert detail.error == "record_not_found"


@pytest.mark.live
def test_live_keyword_search_returns_sca3_records() -> None:
    _live()
    response = search_cnki("脊髓小脑性共济失调3型", field="keyword")
    assert response.status == "ok", response.error
    assert response.returned_count >= 1
    blob = " ".join(item.title for item in response.records)
    assert "脊髓小脑" in blob or "SCA3" in blob or "共济失调" in blob
