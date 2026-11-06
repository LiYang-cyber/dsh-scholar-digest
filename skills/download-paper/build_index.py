# -*- coding: utf-8 -*-
"""从文献清单 Markdown + BibTeX 生成便于下载/打开的索引文件。

用法：
    python build_index.py <专题目录>
专题目录必须显式给出：技能目录是只读工具包，不充当工作区。

目录内约定：
    *清单*.md                  文献清单正文（含 Markdown 表格）
    references_*.bib           BibTeX（可多个，自动合并；含 eprint 字段的判为 arXiv）

产物（专题目录下只保留这三类 + 下载脚本）：
    批量下载_arXiv.ps1           批量抓取 arXiv PDF
    文献下载索引.html            可点击索引
    文献下载索引.xlsx            多表工作簿（最后写，被 Excel 占用时有兜底）
"""
import os
import re
import sys
import html

if len(sys.argv) < 2:
    sys.exit("用法：python build_index.py <专题目录>（技能目录只读，必须显式传入专题目录）")
BASE = os.path.abspath(sys.argv[1])

mds = [f for f in os.listdir(BASE) if f.endswith(".md") and "清单" in f]
if not mds:
    sys.exit("未在 %s 找到 *清单*.md" % BASE)
MD = os.path.join(BASE, sorted(mds)[0])

XLSX = os.path.join(BASE, "文献下载索引.xlsx")
HTML = os.path.join(BASE, "文献下载索引.html")
PS1 = os.path.join(BASE, "批量下载_arXiv.ps1")

HEADER_WORDS = {"文献", "报道", "检索库", "主题组", "库", "年份"}
SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")
ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})")
S2ID_RE = re.compile(r"(?:Semantic Scholar ID:|paperId[\"\s:]+)\s*([0-9a-f]{40})")
DOI_RE = re.compile(r"DOI:\s*(10\.[^\s|)]+)")
URL_RE = re.compile(r"https?://[^\s|)\]<>]+")
SKIP_GROUP_KEYS = ("检索说明", "结论速览", "空白点", "引用与核验", "附", "统计", "配套文件", "交付")


def parse_bib(path):
    out = []
    cur = None
    for ln in open(path, encoding="utf-8").read().splitlines():
        s = ln.strip()
        if s.startswith("@"):
            if cur:
                out.append(cur)
            m = re.match(r"@(\w+)\{([^,]+),", s)
            cur = {"type": m.group(1), "key": m.group(2), "fields": {}} if m else None
            continue
        if cur is None:
            continue
        if s == "}":
            out.append(cur)
            cur = None
            continue
        m = re.match(r"(\w+)\s*=\s*\{(.*)\}\s*,?\s*$", s)
        if m:
            cur["fields"][m.group(1).lower()] = m.group(2).strip()
    if cur:
        out.append(cur)
    return out


def parse_all_bibs(folder):
    ents = []
    for fn in sorted(os.listdir(folder)):
        if fn.startswith("references_") and fn.endswith(".bib"):
            ents += parse_bib(os.path.join(folder, fn))
    return ents


# ---------------- 解析 Markdown ----------------
rows = []
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
    title = re.sub(r"[*`]", "", cells[0]).strip()
    if not title or title in HEADER_WORDS:
        continue

    link, kind = "", ""
    m = ARXIV_RE.search(ln)
    if m:
        link, kind = "https://arxiv.org/abs/%s" % m.group(1), "arXiv 预印本（可直下 PDF）"
    if not link:
        m = DOI_RE.search(ln)
        if m:
            link, kind = "https://doi.org/%s" % m.group(1), "DOI / 出版商页面"
    if not link:
        m = S2ID_RE.search(ln)
        if m:
            link, kind = "https://www.semanticscholar.org/paper/%s" % m.group(1), "Semantic Scholar 记录页"
    if not link:
        m = URL_RE.search(ln)
        if m:
            link = m.group(0).rstrip(".,;")
            if "arxiv.org" in link:
                kind = "arXiv 预印本（可直下 PDF）"
            elif "ieeexplore.ieee.org" in link:
                kind = "IEEE Xplore"
            elif "kns.cnki.net" in link:
                kind = "知网主站记录页（需机构账号）"
            elif "cnki" in link:
                kind = "知网空间题录页（旧链接）"
            elif "doi.org" in link or "mdpi.com" in link or "nature.com" in link:
                kind = "开放获取 / 出版商页面"
            else:
                kind = "外部链接"

    meta = ""
    for c in cells[1:4]:
        if c and c not in ("—", "-") and "http" not in c and len(c) < 30:
            meta += (" | " if meta else "") + c

    # 知网条目的 URL 取自清单正文：现为 kns.cnki.net 主站记录页，由 CNKI MCP 工具返回的
    # url 字段逐条取得（dbcode / filename 原样保留）。注意该端点对任意 filename（含不存在
    # 的编号）都返回 200，故链接只能来自工具返回值，不得按 URL 规则手工拼接。
    rows.append({"group": group, "title": title, "link": link, "kind": kind,
                 "meta": meta})

# ---------------- 本地 PDF 存放区（按来源分类） ----------------
PDF_ROOT = os.path.join(BASE, "PDF")
PDF_SUBS = {
    "arXiv": "脚本自动下载的 arXiv 预印本。文件名即 arXiv ID（如 2502.07826.pdf），请勿改名。",
    "知网": "从知网下载的全文（需机构账号）。建议命名：第一作者_年份_题名关键词.pdf",
    "其他": "IEEE Xplore / Springer / MDPI / 馆际互借等途径获取的全文。",
}


def ensure_pdf_layout(root):
    os.makedirs(root, exist_ok=True)
    for k in PDF_SUBS:
        os.makedirs(os.path.join(root, k), exist_ok=True)
    readme = os.path.join(root, "README.txt")
    if not os.path.exists(readme):
        lines = ["PDF 存放区 —— 按来源分类", "=" * 34, ""]
        for k, desc in PDF_SUBS.items():
            lines += ["[%s]" % k, "    " + desc, ""]
        lines += [
            "说明：",
            "1. arXiv 子目录由 批量下载_arXiv.ps1 自动填充；文件名即 arXiv ID，改名会使",
            "   文献下载索引.xlsx 中该条的「本地已下载」标记失效。",
            "2. 其他子目录可自行增删改名；重跑 build_index.py 后，PDF 下的全部文件会被重新",
            "   扫描并写入索引的「本地PDF清单」工作表。",
        ]
        open(readme, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def scan_local_pdfs(root):
    out = []
    if not os.path.isdir(root):
        return out
    for dirpath, _dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        for fn in filenames:
            if fn.lower().endswith(".pdf"):
                fp = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(fp)
                    mtime = os.path.getmtime(fp)
                except OSError:
                    continue
                out.append({"sub": "" if rel == "." else rel, "name": fn, "size": size, "mtime": mtime})
    return out


ensure_pdf_layout(PDF_ROOT)
local_pdfs = scan_local_pdfs(PDF_ROOT)
local_arx = {os.path.splitext(p["name"])[0].lower() for p in local_pdfs if p["sub"] == "arXiv"}

all_bib = parse_all_bibs(BASE)
arx_entries = [e for e in all_bib if e["fields"].get("eprint")]
oth_entries = [e for e in all_bib if not e["fields"].get("eprint")]
arx_ids = [e["fields"]["eprint"] for e in sorted(arx_entries, key=lambda x: x["fields"]["eprint"])]

print("目录：%s" % BASE)
print("Markdown 条目：%d ；BibTeX 合计：%d（arXiv %d / 其他 %d）" % (len(rows), len(all_bib), len(arx_entries), len(oth_entries)))
print("本地 PDF：%d 个（其中 PDF\\arXiv 下 %d 个）" % (len(local_pdfs), len(local_arx)))

# ---------------- 1. PowerShell 下载脚本 ----------------
ps = [
    "# 批量下载 arXiv 预印本 PDF（%d 条）" % len(arx_ids),
    "# 用法（任选其一；Bypass 用于绕过默认执行策略限制）：",
    "#   pwsh -ExecutionPolicy Bypass -File .\\批量下载_arXiv.ps1",
    "#   powershell -ExecutionPolicy Bypass -File .\\批量下载_arXiv.ps1",
    "# 文件保存到 .\\PDF\\arXiv\\ （PDF 为统一存放区，可按来源分目录）；已存在的自动跳过。",
    "",
    "$ErrorActionPreference = 'Continue'",
    "$outDir = Join-Path $PSScriptRoot 'PDF\\arXiv'",
    "New-Item -ItemType Directory -Force -Path $outDir | Out-Null",
    "$ids = @(",
]
for i, aid in enumerate(arx_ids):
    ps.append('  "%s"%s' % (aid, "," if i < len(arx_ids) - 1 else ""))
ps += [
    ")",
    "$ok = 0; $skip = 0; $fail = 0",
    "foreach ($id in $ids) {",
    "  $dest = Join-Path $outDir ($id + '.pdf')",
    "  if (Test-Path $dest) { $skip++; continue }",
    "  $url = \"https://arxiv.org/pdf/$id\"",
    "  try {",
    "    Invoke-WebRequest -Uri $url -OutFile $dest -TimeoutSec 90 -UserAgent 'Mozilla/5.0' -UseBasicParsing -ErrorAction Stop",
    "    Write-Host \"[OK]   $id\"",
    "    $ok++",
    "  } catch {",
    "    if (Test-Path $dest) { Remove-Item $dest -Force -ErrorAction SilentlyContinue }",
    "    Write-Host \"[FAIL] $id  $($_.Exception.Message)\"",
    "    $fail++",
    "  }",
    "  Start-Sleep -Seconds 3   # arXiv 礼貌请求间隔，勿删",
    "}",
    "Write-Host \"\"",
    "Write-Host \"完成：成功 $ok，跳过 $skip，失败 $fail。目录：$outDir\"",
]
open(PS1, "w", encoding="utf-8-sig").write("\n".join(ps) + "\n")
print("已生成：", PS1)

# ---------------- 2. HTML 索引 ----------------
groups = {}
for r in rows:
    groups.setdefault(r["group"], []).append(r)
cn = [r for r in rows if "cnki" in r["link"]]

parts = ["""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>文献下载索引</title>
<style>
body{font-family:"Microsoft YaHei",system-ui,sans-serif;margin:24px;background:#f7f8fa;color:#1f2328;line-height:1.6}
h1{font-size:22px;border-bottom:2px solid #0969da;padding-bottom:8px}
h2{font-size:17px;margin-top:28px;color:#0969da}
table{border-collapse:collapse;width:100%;background:#fff;margin-top:8px;font-size:13px}
th,td{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef2f6}
tr:nth-child(even){background:#fafbfc}
a{color:#0969da;text-decoration:none}
a:hover{text-decoration:underline}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:9px;background:#e8f0fe;color:#0b4f9e;white-space:nowrap}
.tag.pdf{background:#e6f4ea;color:#137333}
.tag.ok{background:#dff5e1;color:#0f6b2f;border:1px solid #a8d5b5}
.note{background:#fff8e1;border-left:4px solid #f0b429;padding:10px 14px;margin:16px 0;font-size:13px}
.stat{font-size:13px;background:#fff;border:1px solid #d0d7de;padding:10px 14px;border-radius:6px}
</style></head><body>
<h1>文献下载索引</h1>
<div class="note">
<b>使用说明</b><br>
1. 绿色 <span class="tag pdf">arXiv PDF</span> 标签为<b>可直接下载的全文</b>，点击即取；<br>
2. 知网条目指向<b>知网主站记录页</b>（kns.cnki.net），其 dbcode 与 filename 由 CNKI 工具返回的 url 字段逐条取得、未经改写；<b>打开与下载全文需机构账号</b>；<br>
3. 批量抓取 arXiv 全文：执行 <code>pwsh -ExecutionPolicy Bypass -File .\\批量下载_arXiv.ps1</code>；<br>
4. 导入 Zotero / EndNote / JabRef：使用目录下的 <code>references_*.bib</code> 与 <code>知网文献.ris</code>。
</div>
"""]

# 知网链接说明
CNKI_RULE = ("知网条目的链接为<b>知网主站记录页</b>"
             "（<code>kns.cnki.net/kcms/detail/detail.aspx?dbcode=..&amp;filename=..</code>），"
             "其 <code>dbcode</code> 与 <code>filename</code> 逐条取自 CNKI 工具返回的 <code>url</code> 字段，未经改写。"
             "该端点<b>对任意 filename（包括不存在的编号）都返回 200</b>，因此链接只能来自工具返回值，"
             "不得按 URL 规则手工拼接（学位论文尤其如此：实测返回 dbcode=CDMD&filename=&lt;编号&gt;.nh，"
             "与空间题录页形式推不出的一致）。知网主站检索与全文下载需机构账号登录。")
parts.append('<div class="note"><b>关于知网链接：</b>%s</div>' % CNKI_RULE)
parts.append('<div class="stat">Markdown 清单共 <b>%d</b> 条；BibTeX 合计 <b>%d</b> 条（arXiv <b>%d</b> / 其他 <b>%d</b>）；知网条目 <b>%d</b> 条。</div>'
             % (len(rows), len(all_bib), len(arx_entries), len(oth_entries), len(cn)))

for g in groups:
    parts.append("<h2>%s</h2>" % html.escape(g))
    parts.append("<table><tr><th style='width:40px'>#</th><th>标题</th><th style='width:150px'>链接类型</th><th style='width:260px'>链接</th></tr>")
    for i, r in enumerate(groups[g], start=1):
        t = html.escape(r["title"])
        if r["link"]:
            tcell = '<a href="%s" target="_blank">%s</a>' % (html.escape(r["link"]), t)
            extra = ""
            if "arxiv.org/abs/" in r["link"]:
                aid = r["link"].rsplit("/", 1)[-1]
                got = ' <span class="tag ok">已下载</span>' if aid.lower() in local_arx else ""
                extra = (' &nbsp;<a class="tag pdf" href="https://arxiv.org/pdf/%s" target="_blank">arXiv PDF</a>%s'
                         % (aid, got))
            lcell = '<a href="%s" target="_blank">%s</a>%s' % (html.escape(r["link"]), html.escape(r["link"][:70]), extra)
        else:
            tcell, lcell = t, "—"
        parts.append("<tr><td>%d</td><td>%s</td><td><span class='tag'>%s</span></td><td>%s</td></tr>"
                     % (i, tcell, html.escape(r["kind"] or "—"), lcell))
    parts.append("</table>")
parts.append("</body></html>")
open(HTML, "w", encoding="utf-8").write("\n".join(parts))
print("已生成：", HTML)

# ---------------- 3. XLSX（最后写） ----------------
from xlsxwriter import Workbook


def write_xlsx(path):
    wb = Workbook(path)
    hdr = wb.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1, "text_wrap": True, "valign": "vcenter"})
    cell = wb.add_format({"border": 1, "valign": "top", "text_wrap": True})
    link_fmt = wb.add_format({"border": 1, "valign": "top", "font_color": "#0563C1", "underline": 1, "text_wrap": True})

    ws = wb.add_worksheet("全部条目")
    for i, w in enumerate([6, 26, 62, 50, 24, 18]):
        ws.set_column(i, i, w)
    for c, h in enumerate(["序号", "主题分组", "标题", "链接（知网=主站记录页）", "链接类型", "年份/类型(部分)"]):
        ws.write(0, c, h, hdr)
    ws.freeze_panes(1, 0)
    for i, r in enumerate(rows, start=1):
        ws.write_number(i, 0, i, cell)
        ws.write(i, 1, r["group"], cell)
        ws.write(i, 2, r["title"], cell)
        if r["link"]:
            ws.write_url(i, 3, r["link"], link_fmt, r["link"][:120])
        else:
            ws.write(i, 3, "（无链接，见清单正文）", cell)
        ws.write(i, 4, r["kind"], cell)
        ws.write(i, 5, r["meta"], cell)
    ws.autofilter(0, 0, len(rows), 5)

    if arx_entries:
        ws2 = wb.add_worksheet("arXiv 可直下_全量")
        for i, w in enumerate([6, 78, 44, 44, 44, 12]):
            ws2.set_column(i, i, w)
        for c, h in enumerate(["序号", "标题", "作者", "摘要页", "PDF 直链", "本地已下载"]):
            ws2.write(0, c, h, hdr)
        ws2.freeze_panes(1, 0)
        for i, e in enumerate(sorted(arx_entries, key=lambda x: x["fields"]["eprint"]), start=1):
            f = e["fields"]
            aid = f["eprint"]
            ws2.write_number(i, 0, i, cell)
            ws2.write(i, 1, f.get("title", ""), cell)
            ws2.write(i, 2, f.get("author", ""), cell)
            ws2.write_url(i, 3, "https://arxiv.org/abs/%s" % aid, link_fmt, "https://arxiv.org/abs/%s" % aid)
            ws2.write_url(i, 4, "https://arxiv.org/pdf/%s" % aid, link_fmt, "https://arxiv.org/pdf/%s" % aid)
            ws2.write(i, 5, "是" if aid.lower() in local_arx else "", cell)
        ws2.autofilter(0, 0, len(arx_entries), 5)

    if oth_entries:
        ws3 = wb.add_worksheet("期刊会议_BibTeX")
        for i, w in enumerate([6, 74, 46, 12, 50]):
            ws3.set_column(i, i, w)
        for c, h in enumerate(["序号", "标题", "作者", "年份", "出版信息"]):
            ws3.write(0, c, h, hdr)
        for i, e in enumerate(oth_entries, start=1):
            f = e["fields"]
            venue = f.get("journal") or f.get("booktitle") or f.get("url") or ""
            ws3.write_number(i, 0, i, cell)
            ws3.write(i, 1, f.get("title", ""), cell)
            ws3.write(i, 2, f.get("author", ""), cell)
            ws3.write(i, 3, f.get("year", ""), cell)
            if venue.startswith("http"):
                ws3.write_url(i, 4, venue, link_fmt, venue)
            else:
                ws3.write(i, 4, venue, cell)
        ws3.autofilter(0, 0, len(oth_entries), 4)

    if cn:
        ws4 = wb.add_worksheet("知网主站链接")
        for i, w in enumerate([6, 26, 70, 60, 24]):
            ws4.set_column(i, i, w)
        for c, h in enumerate(["序号", "主题分组", "标题", "知网主站记录页URL（需机构账号）", "文献类型"]):
            ws4.write(0, c, h, hdr)
        for i, r in enumerate(cn, start=1):
            ws4.write_number(i, 0, i, cell)
            ws4.write(i, 1, r["group"], cell)
            ws4.write(i, 2, r["title"], cell)
            ws4.write_url(i, 3, r["link"], link_fmt, r["link"])
            ws4.write(i, 4, r["kind"], cell)
        ws4.autofilter(0, 0, len(cn), 4)

    if local_pdfs:
        ws5 = wb.add_worksheet("本地PDF清单")
        for i, w in enumerate([6, 18, 66, 12, 20]):
            ws5.set_column(i, i, w)
        for c, h in enumerate(["序号", "分类目录", "文件名", "大小(KB)", "修改时间"]):
            ws5.write(0, c, h, hdr)
        ws5.freeze_panes(1, 0)
        for i, p in enumerate(sorted(local_pdfs, key=lambda x: (x["sub"], x["name"])), start=1):
            import datetime as _dt
            ws5.write_number(i, 0, i, cell)
            ws5.write(i, 1, p["sub"] or "（PDF 根目录）", cell)
            ws5.write(i, 2, p["name"], cell)
            ws5.write_number(i, 3, round(p["size"] / 1024.0, 1), cell)
            ws5.write(i, 4, _dt.datetime.fromtimestamp(p["mtime"]).strftime("%Y-%m-%d %H:%M"), cell)
        ws5.autofilter(0, 0, len(local_pdfs), 4)

    wb.close()


try:
    write_xlsx(XLSX)
    print("已生成：", XLSX)
except Exception as exc:
    print("!! XLSX 写入失败：%s" % exc)
    alt = os.path.join(BASE, "文献下载索引_新.xlsx")
    try:
        write_xlsx(alt)
        print("!! 已改写入备用文件：", alt)
        print("!! 原因通常是原文件正在 Excel 中打开。关闭 Excel 后把备用文件改名即可，或重跑本脚本。")
    except Exception as exc2:
        print("!! 备用文件同样写入失败：%s" % exc2)
