# -*- coding: utf-8 -*-
"""从文献清单 Markdown 导出「知网部分」的 RIS 与 BibTeX。

用法：python export_cnki_refs.py <专题目录>
专题目录必须显式给出：技能目录是只读工具包，不充当工作区。

产物：
    知网文献.ris / 知网文献.bib   交付物，写在目标目录下
    知网条目清单.csv              过程产物，写在调用项目根 _archive\\<专题名>\\ 下

说明：
  * 作者、题名、刊名/授予单位、类型、知网文献号(URL) 均来自清单，即 CNKI MCP 工具返回值；
  * 年份：工具对多数条目未返回，改由知网文献号推断（期刊/报纸的编号内嵌年月），
    推断结果在条目备注中标注，引用前请核对；
  * 卷、期、页码、DOI：工具未返回，且经实测无法从公开接口获取，故一律留空，不臆造。
"""
import os
import re
import sys
import csv

if len(sys.argv) < 2:
    sys.exit("用法：python export_cnki_refs.py <专题目录>（技能目录只读，必须显式传入专题目录）")
BASE = os.path.abspath(sys.argv[1])
mds = [f for f in os.listdir(BASE) if f.endswith(".md") and "清单" in f]
if not mds:
    sys.exit("未在 %s 找到 *清单*.md" % BASE)
MD = os.path.join(BASE, sorted(mds)[0])

RIS_OUT = os.path.join(BASE, "知网文献.ris")
BIB_OUT = os.path.join(BASE, "知网文献.bib")


def archive_dir(base):
    """过程产物（非交付物）统一收进调用项目根 _archive\\<专题名>\\。

    仅当父目录下已存在 _archive\\（本项目内的使用情形）才归到调用项目根按专题分目录；
    否则退回本目录内的 _archive\\，以免对项目外的任意目录重跑时污染其上级目录。
    专题目录只保留交付物：清单 md、*.bib、*.ris、文献下载索引.html / .xlsx、
    批量下载_arXiv.ps1、PDF\\。
    """
    base = os.path.abspath(base)
    parent_arch = os.path.join(os.path.dirname(base), "_archive")
    cand = (os.path.join(parent_arch, os.path.basename(base))
            if os.path.isdir(parent_arch) else os.path.join(base, "_archive"))
    try:
        os.makedirs(cand, exist_ok=True)
        return cand
    except OSError:
        return base


ARCHIVE = archive_dir(BASE)

SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")
URL_RE = re.compile(r"https?://[^\s|)\]<>]+")
HEADER_WORDS = {"文献", "报道", "检索库", "主题组", "库", "年份"}
SKIP_GROUP_KEYS = ("检索说明", "结论速览", "空白点", "引用与核验", "附", "统计", "配套文件", "交付")
KIND_RE = re.compile(r"(期刊|硕士学位论文|博士学位论文|硕士论文|博士论文|硕士|博士|报纸|中国会议|会议)[（(]([^）)]+)[）)]")


def year_from_cnki_id(fn):
    """知网文献号内嵌年月，此处据此还原年份。

    期刊  4位刊名码 + 4位年 + 2位期 + 3位流水   e.g. GYDQ202311003 -> 2023, 第11期
    报纸  4位报名码 + 4位年 + 2位月 + 2位日 + 4位版 e.g. GJDW202505190013 -> 2025-05-19
    学位  纯数字编号，不含年月，返回空
    """
    m = re.match(r"^[A-Z]+(\d{4})(\d{2})(\d{2})(\d{4})$", fn)
    if m:
        return m.group(1), "%s-%s-%s" % (m.group(1), m.group(2), m.group(3)), "第%s版" % m.group(4)
    m = re.match(r"^[A-Z]+(\d{4})([A-Z]?\d{1,2})(\d{1,3})$", fn)
    if m:
        return m.group(1), "", "第%s期" % m.group(2)
    return "", "", ""


items = []
group = ""
skipping = True
for ln in open(MD, encoding="utf-8").read().splitlines():
    if ln.startswith("## "):
        group = ln[3:].strip()
        skipping = any(k in group for k in SKIP_GROUP_KEYS)
        continue
    if skipping or not ln.startswith("|") or SEP_RE.match(ln.strip()):
        continue
    cells = [c.strip() for c in ln.strip().strip("|").split("|")]
    if len(cells) < 2:
        continue
    first = re.sub(r"[*`]", "", cells[0]).strip()
    if not first or first in HEADER_WORDS:
        continue

    cn_urls = [u.rstrip(".,;") for u in URL_RE.findall(ln) if "cnki" in u]
    if not cn_urls:
        continue
    space = cn_urls[0]

    db, fn = "", ""
    # 主站链接（当前写法）：kns.cnki.net/kcms/detail/detail.aspx?dbcode=XXX&filename=YYY
    # dbcode 与 filename 只能原样取自 CNKI 工具返回的 url 字段，不可按 URL 规则推导——
    # 实测学位论文返回的是 dbcode=CDMD&filename=<编号>.nh，与空间题录页形式推不出的一致。
    m = re.search(r"[?&]dbcode=([A-Za-z]+)[^&\s|)]*&filename=([^&\s|)]+)", space)
    if m:
        db, fn = m.group(1).upper(), m.group(2)
    else:
        # 旧写法（知网空间题录页），保留向后兼容
        for pat, dbc in ((r"CJFDTOTAL-([A-Za-z0-9]+)\.htm", "CJFD"),
                         (r"CPFDTOTAL-([A-Za-z0-9]+)\.htm", "CPFD"),
                         (r"/CCND/([A-Za-z0-9]+)\.htm", "CCND"),
                         (r"CDMD-\d+-([A-Za-z0-9]+)\.htm", None)):
            m = re.search(pat, space)
            if m:
                fn = m.group(1)
                db = dbc or ("CDFD" if "博士" in ln else "CMFD")
                break
    if not fn:
        continue

    m = re.match(r"^(.*?)《(.+?)》$", first)
    if m:
        authors_raw, title = m.group(1), m.group(2)
    else:
        authors_raw, title = "", first
    authors = [a.strip() for a in re.split(r"[；;、]", authors_raw) if a.strip()]

    kind, venue = "期刊", ""
    for c in cells[1:4]:
        mm = KIND_RE.search(c)
        if mm:
            kind, venue = mm.group(1), mm.group(2)
            venue = re.sub(r"[，,]\s*导师.*$", "", venue).strip()
            break

    # 按知网库代码兜底修正文献类型（清单里报道类的第 3 列是"主体"而非"报纸"）
    if db == "CCND":
        kind = "报纸"
        m_news = re.search(r"[（(]([^）)]{2,12}报)[）)]", first)
        venue = m_news.group(1) if m_news else (venue or "报纸")
    elif db in ("CMFD", "CDFD", "CDMD") and kind == "期刊":
        kind = "博士" if (db == "CDFD" or "博士" in ln) else "硕士"

    year, date, issue = year_from_cnki_id(fn)
    if not year:
        for c in cells[1:4]:
            m2 = re.search(r"\b(19|20)\d{2}\b", c)
            if m2:
                year = m2.group(0)
                break
    year_src = "由知网文献号推断" if year and not date == "" or year else ""

    # URL 一律用知网空间题录页：它由 CNKI MCP 工具直接返回，且实测返回 200、免登录可读摘要。
    # 曾用 kns.cnki.net/kcms/detail/detail.aspx?dbcode=..&filename=.. 拼接直链，实测该端点
    # 对任意 filename（含不存在的编号）都返回 200，无法证明指向正确文献，故弃用。
    space_url = space
    items.append({"group": group, "title": title, "authors": authors, "kind": kind,
                  "venue": venue, "year": year, "date": date, "issue": issue,
                  "fn": fn, "db": db, "space": space_url})

print("解析知网条目：%d 条" % len(items))

# ---------------- RIS ----------------
RIS_TYPE = {"期刊": "JOUR", "报纸": "NEWS", "中国会议": "CONF", "会议": "CONF",
            "硕士": "THES", "博士": "THES", "硕士论文": "THES", "博士论文": "THES",
            "硕士学位论文": "THES", "博士学位论文": "THES"}

ris = []
for it in items:
    t = RIS_TYPE.get(it["kind"], "JOUR")
    ris.append("TY  - %s" % t)
    for a in it["authors"]:
        ris.append("AU  - %s" % a)
    ris.append("TI  - %s" % it["title"])
    if t == "JOUR":
        if it["venue"]:
            ris.append("JO  - %s" % it["venue"])
    elif t == "THES":
        if it["venue"]:
            ris.append("T2  - %s" % it["venue"])
    elif t == "NEWS":
        if it["venue"]:
            ris.append("JO  - %s" % it["venue"])
    elif t == "CONF":
        if it["venue"]:
            ris.append("T2  - %s" % it["venue"])
    if it["year"]:
        ris.append("PY  - %s" % it["year"])
    if it["date"]:
        ris.append("DA  - %s" % it["date"])
    ris.append("UR  - %s" % it["space"])
    ris.append("DB  - CNKI")
    note = "CNKI %s: %s" % (it["db"], it["fn"])
    if it["year"]:
        note += "；年份由知网文献号推断，引用前请核对"
    if it["issue"]:
        note += "；%s" % it["issue"]
    note += "；卷期页与 DOI 未获取；链接为知网空间题录页（免登录可读摘要）"
    ris.append("N1  - %s" % note)
    ris.append("ER  - ")
    ris.append("")

open(RIS_OUT, "w", encoding="utf-8").write("\n".join(ris))
print("已生成：", RIS_OUT)

# ---------------- BibTeX ----------------
BIB_TYPE = {"期刊": "article", "报纸": "misc", "中国会议": "inproceedings", "会议": "inproceedings",
            "硕士": "mastersthesis", "硕士论文": "mastersthesis", "硕士学位论文": "mastersthesis",
            "博士": "phdthesis", "博士论文": "phdthesis", "博士学位论文": "phdthesis"}

bib = ["% 知网（CNKI）文献 BibTeX —— 由清单导出",
       "% 作者、题名、刊名/授予单位、url 均来自 CNKI MCP 工具返回值；",
       "% 年份多由知网文献号内嵌的年月推断（工具未直接返回），已在 note 中标注；",
       "% 卷、期、页码与 DOI 工具未返回，且实测无法从公开接口获取，故不臆造。",
       "% url 为知网空间题录页：实测返回 200，免登录可读题名/作者/摘要。",
       ""]
for it in items:
    typ = BIB_TYPE.get(it["kind"], "article")
    bib.append("@%s{cnki_%s," % (typ, it["fn"]))
    bib.append("  title = {%s}," % it["title"])
    if it["authors"]:
        bib.append("  author = {%s}," % " and ".join(it["authors"]))
    if typ in ("article",):
        if it["venue"]:
            bib.append("  journal = {%s}," % it["venue"])
    elif typ in ("mastersthesis", "phdthesis"):
        if it["venue"]:
            bib.append("  school = {%s}," % it["venue"])
        bib.append("  type = {%s}," % ("博士学位论文" if typ == "phdthesis" else "硕士学位论文"))
    else:
        if it["venue"]:
            bib.append("  howpublished = {%s}," % it["venue"])
    if it["year"]:
        bib.append("  year = {%s}," % it["year"])
    bib.append("  url = {%s}," % it["space"])
    note = "CNKI %s: %s" % (it["db"], it["fn"])
    if it["issue"]:
        note += "；%s" % it["issue"]
    if it["year"]:
        note += "；年份由知网文献号推断，引用前请核对"
    note += "；卷期页与 DOI 未获取；链接为知网空间题录页"
    bib.append("  note = {%s}," % note)
    bib.append("}")
    bib.append("")

open(BIB_OUT, "w", encoding="utf-8").write("\n".join(bib))
print("已生成：", BIB_OUT)

# ---------------- 知网条目清单（含可直接打开的题录页 URL，过程产物 → _archive） ----------------
DOWN_CSV = os.path.join(ARCHIVE, "知网条目清单.csv")
with open(DOWN_CSV, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["序号", "标题", "作者", "期刊/授予单位", "年份", "类型", "知网题录页URL"])
    for i, it in enumerate(items, start=1):
        w.writerow([i, it["title"], "；".join(it["authors"]), it["venue"], it["year"],
                    it["kind"], it["space"]])
print("已生成：", DOWN_CSV)

# ---------------- 统计 ----------------
import collections
kinds = collections.Counter(it["kind"] for it in items)
yrs = sum(1 for it in items if it["year"])
print("类型分布：", dict(kinds))
print("有年份的条目：%d / %d" % (yrs, len(items)))
