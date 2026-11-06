# -*- coding: utf-8 -*-
"""汇总「可确认」的 DOI，输出纯文本列表（每行一个）。

用法：python export_doi_list.py <专题目录>
专题目录必须显式给出：技能目录是只读工具包，不充当工作区。

取数三路：
  1. arXiv 官方 API —— 预印本若已正式发表，API 会返回登记的 DOI（权威元数据）
  2. 目录内 references_*.bib —— 工具导出时已带 doi 字段的条目
  3. Crossref —— 对**英文**标题做匹配，并用标题相似度校验（< 0.90 一律不采纳）

关于知网中文文献：CNKI MCP 工具（search / get_record）不返回 DOI 字段，
Crossref、OpenAlex、Semantic Scholar 对中文标题均无法正确匹配（实测返回同名异文），
因此知网条目不在本列表中，也不臆造。知网部分请用「知网文献.ris / .bib」导入。

产物（均为过程产物，写入调用项目根 _archive\\<专题名>\\，专题目录只留交付物）：
  DOI列表.txt     纯 DOI，每行一个（严格按要求，无表头无注释）
  DOI对照表.csv   DOI ↔ 标题 ↔ 来源 ↔ 匹配方式，便于核对
"""
import os
import re
import sys
import csv
import json
import time
import difflib
import urllib.request
import urllib.parse

if len(sys.argv) < 2:
    sys.exit("用法：python export_doi_list.py <专题目录>（技能目录只读，必须显式传入专题目录）")
BASE = os.path.abspath(sys.argv[1])
UA = {"User-Agent": "lit-review-doi-list/1.0 (mailto:research@example.org)"}


def archive_dir(base):
    """过程产物统一收进调用项目根 _archive\\<专题名>\\。

    仅当父目录下已存在 _archive\\（本项目内的使用情形）才归到调用项目根；
    否则退回本目录内的 _archive\\，以免污染项目外目录的上级。
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
DOI_TXT = os.path.join(ARCHIVE, "DOI列表.txt")
DOI_CSV = os.path.join(ARCHIVE, "DOI对照表.csv")


def fetch(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode("utf-8", "replace")


def norm(s):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", (s or "").lower())


def is_chinese(s):
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


# ---------- 1. 收集 BibTeX ----------
bib_files = [f for f in sorted(os.listdir(BASE)) if f.startswith("references_") and f.endswith(".bib")]
entries = []
for fn in bib_files:
    cur = None
    for ln in open(os.path.join(BASE, fn), encoding="utf-8").read().splitlines():
        s = ln.strip()
        if s.startswith("@"):
            if cur:
                entries.append(cur)
            m = re.match(r"@(\w+)\{([^,]+),", s)
            cur = {"key": m.group(2), "fields": {}} if m else None
            continue
        if cur is None:
            continue
        if s == "}":
            entries.append(cur)
            cur = None
            continue
        m = re.match(r"(\w+)\s*=\s*\{(.*)\}\s*,?\s*$", s)
        if m:
            cur["fields"][m.group(1).lower()] = m.group(2).strip()
    if cur:
        entries.append(cur)

arx_ids, bib_dois = [], []
for e in entries:
    f = e["fields"]
    aid = f.get("eprint")
    if aid:
        arx_ids.append(aid)
    if f.get("doi"):
        bib_dois.append({"doi": f["doi"].rstrip("."), "title": f.get("title", ""),
                         "src": "BibTeX(工具导出)", "ref": e["key"]})
arx_ids = list(dict.fromkeys(arx_ids))
print("BibTeX 条目 %d；arXiv ID %d；bib 中自带 DOI %d" % (len(entries), len(arx_ids), len(bib_dois)))

# ---------- 2. arXiv API ----------
arx_dois = []
if arx_ids:
    try:
        xml = fetch("http://export.arxiv.org/api/query?id_list=%s&max_results=300" % ",".join(arx_ids), timeout=120)
        for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
            blk = m.group(1)
            mid = re.search(r"<id>http://arxiv\.org/abs/([^<]+)</id>", blk)
            mdoi = re.search(r"<arxiv:doi[^>]*>([^<]+)</arxiv:doi>", blk)
            mj = re.search(r"<arxiv:journal_ref[^>]*>([^<]+)</arxiv:journal_ref>", blk)
            mti = re.search(r"<title>(.*?)</title>", blk, re.S)
            if mid and mdoi:
                arx_dois.append({
                    "doi": mdoi.group(1).strip(),
                    "title": re.sub(r"\s+", " ", (mti.group(1) if mti else "")).strip(),
                    "src": "arXiv API（已发表版本登记）",
                    "ref": "arXiv:" + re.sub(r"v\d+$", "", mid.group(1)),
                    "note": ("已发表于 " + re.sub(r"\s+", " ", mj.group(1)).strip()) if mj else "",
                })
        print("arXiv API 返回 DOI：%d 条" % len(arx_dois))
    except Exception as exc:
        print("!! arXiv API 失败：%s" % exc)

# ---------- 3. Crossref（仅英文标题，带本地缓存） ----------
CACHE_PATH = os.path.join(ARCHIVE, "crossref_cache.json")
cr_cache = {}
if os.path.exists(CACHE_PATH):
    try:
        cr_cache = json.load(open(CACHE_PATH, encoding="utf-8"))
    except Exception:
        cr_cache = {}

cr_dois, cr_checked, cr_hits = [], 0, 0
for e in entries:
    f = e["fields"]
    if f.get("eprint") or f.get("doi"):
        continue
    title = f.get("title", "")
    if not title or is_chinese(title):
        continue
    cr_checked += 1
    key = norm(title)

    if key in cr_cache:
        res = cr_cache[key]
        cr_hits += 1
    else:
        u = ("https://api.crossref.org/works?rows=3&select=DOI,title,container-title,type"
             "&query.bibliographic=" + urllib.parse.quote(title))
        res, r = None, None
        for attempt in range(3):
            try:
                r = json.loads(fetch(u, timeout=25))
                break
            except urllib.error.HTTPError as he:
                if he.code == 429 and attempt < 2:
                    time.sleep(4)
                    continue
                print("  [ERR] %s -> HTTP %s" % (title[:44], he.code))
                break
            except Exception as exc:
                print("  [ERR] %s -> %s" % (title[:44], str(exc)[:40]))
                break
        if r is not None:
            best = None
            for it in (r.get("message", {}).get("items") or []):
                cand = (it.get("title") or [""])[0]
                sim = difflib.SequenceMatcher(None, norm(title), norm(cand)).ratio()
                if best is None or sim > best[1]:
                    best = (it.get("DOI"), sim, cand)
            res = {"doi": best[0], "sim": round(best[1], 3), "cand": best[2][:90]} if best else {"doi": None, "sim": 0, "cand": ""}
            cr_cache[key] = res
            try:
                json.dump(cr_cache, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            except Exception:
                pass
        time.sleep(1.2)

    if res and res.get("doi") and res.get("sim", 0) >= 0.90:
        cr_dois.append({"doi": res["doi"], "title": title,
                        "src": "Crossref 标题匹配（相似度 %.2f）" % res["sim"],
                        "ref": e["key"], "note": "匹配到：" + res["cand"][:70]})
        print("  [OK %.2f] %s" % (res["sim"], title[:54]))
    else:
        print("  [--] %s  (最高相似度 %.2f，未采纳)" % (title[:54], (res or {}).get("sim", 0)))
print("Crossref：尝试 %d 条，命中 %d 条，缓存复用 %d 条" % (cr_checked, len(cr_dois), cr_hits))

# ---------- 4. 汇总 ----------
seen, rows = set(), []
for group in (arx_dois, bib_dois, cr_dois):
    for d in group:
        k = d["doi"].lower()
        if k in seen:
            continue
        seen.add(k)
        rows.append(d)

with open(DOI_TXT, "w", encoding="utf-8") as fh:
    for d in rows:
        fh.write(d["doi"] + "\n")

with open(DOI_CSV, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["DOI", "标题", "来源/匹配方式", "标识符", "备注"])
    for d in rows:
        w.writerow([d["doi"], d["title"], d["src"], d.get("ref", ""), d.get("note", "")])

print("\n合计可确认 DOI：%d 个" % len(rows))
print("  其中 arXiv 已发表：%d" % len(arx_dois))
print("  其中 BibTeX 自带：%d" % len(bib_dois))
print("  其中 Crossref 匹配：%d（共尝试 %d 条英文标题）" % (len(cr_dois), cr_checked))
print("已生成：", DOI_TXT)
print("已生成：", DOI_CSV)
