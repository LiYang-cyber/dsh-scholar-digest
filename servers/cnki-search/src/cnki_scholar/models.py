"""Records returned by the CNKI Space search surface, plus CNKI-main-site links."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "blocked", "error"]


class Record(BaseModel):
    title: str
    #: CNKI main site link (kns.cnki.net). This is the link to hand to the user.
    url: str
    #: CNKI Space link. Kept only so get_record can re-read the page.
    space_url: str | None = None
    #: 4-letter CNKI database code, e.g. CJFD / CDMD / CCJD.
    dbcode: str | None = None
    #: CNKI file name, e.g. ZXKC202625006 or 1025564694.nh.
    filename: str | None = None
    authors: str | None = None
    year: str | None = None
    venue: str | None = None
    kind: str | None = None
    snippet: str | None = None


class SearchResponse(BaseModel):
    status: Status
    provider: Literal["cnki"] = "cnki"
    query: str
    field: str = "theme"
    page: int = 1
    returned_count: int = 0
    records: list[Record] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int | None = None
    error: str | None = None


class RecordDetail(BaseModel):
    status: Status
    provider: Literal["cnki"] = "cnki"
    #: CNKI main site link for the same record.
    url: str
    #: The CNKI Space page actually fetched.
    space_url: str | None = None
    title: str | None = None
    abstract: str | None = None
    institution: str | None = None
    degree: str | None = None
    year: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
