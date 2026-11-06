# -*- coding: utf-8 -*-
"""通用交付生成器：从专题的文献总表 xlsx 生成 HTML 索引、RIS 与 arXiv 下载脚本。

用法：
    uv run --with openpyxl python build_delivery.py <专题目录>
专题目录必须显式给出：技能目录是只读工具包，不充当工作区。

约定：
    * 读取专题目录下第一个带「文献总表」工作表的 .xlsx，表头须含
      题名 / 作者 / 年份 / 来源(或来源/期刊) / 文献类型 / 质量分级 / 相关性 / 主题标签 / 标识符 / 备注
    * 产出写到专题目录：
        文献下载索引.html       按文献类型分组的可点击索引（样式内联，断网可开）
        文献清单.ris            全量条目的 RIS
        批量下载_arXiv.ps1      arXiv 批量下载脚本；本专题无 arXiv 条目时为空占位
    * 不改动 xlsx 与既有 bib。
"""
import os
import re
import sys
import html
from collections import Counter

if len(sys.argv) < 2:
    sys.exit("用法：uv run --with openpyxl python build_delivery.py <专题目录>（技能目录只读，必须显式传入专题目录）")
BASE = os.path.abspath(sys.argv[1])

try:
    from openpyxl import load_workbook
except ImportError:
    sys.exit("需要 openpyxl：uv run --with openpyxl python build_delivery.py <专题目录>")

HTML_OUT = os.path.join(BASE, "文献下载索引.html")
RIS_OUT = os.path.join(BASE, "文献清单.ris")
PS1_OUT = os.path.join(BASE, "批量下载_arXiv.ps1")

# ---------------- 读取 xlsx ----------------
def find_workbook(folder):
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(".xlsx") or fn.startswith("~$"):
            continue
        path = os.path.join(folder, fn)
        try:
            wb = load_workbook(path, read_only=True)
            names = wb.sheetnames
            wb.close()
        except Exception:
            continue
        if "文献总表" in names:
            return path
    return None


WB = find_workbook(BASE)
if not WB:
    sys.exit("未在 %s 找到含「文献总表」工作表的 .xlsx" % BASE)


def text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def pick(row, idx, *names):
    for n in names:
        if n in idx:
            return text(row[idx[n]])
    return ""


wb = load_workbook(WB, read_only=True, data_only=True)
ws = wb["文献总表"]
raw = list(ws.iter_rows(values_only=True))
wb.close()

HDR = [text(c) for c in raw[0]]
IDX = {h: i for i, h in enumerate(HDR)}
RECS = []
for row in raw[1:]:
    title = pick(row, IDX, "题名", "标题")
    if not title:
        continue
    RECS.append({
        "no": pick(row, IDX, "序号"),
        "title": title,
        "author": pick(row, IDX, "作者"),
        "year": pick(row, IDX, "年份"),
        "venue": pick(row, IDX, "来源/期刊", "来源", "期刊"),
        "type": pick(row, IDX, "文献类型", "类型"),
        "grade": pick(row, IDX, "质量分级", "分级"),
        "rel": pick(row, IDX, "相关性"),
        "topic": pick(row, IDX, "主题标签", "主题"),
        "ident": pick(row, IDX, "标识符", "DOI", "链接"),
        "note": pick(row, IDX, "备注", "说明"),
    })

print("专题：%s" % BASE)
print("数据源：%s" % os.path.basename(WB))
print("条目：%d 条；质量分级 %s" % (len(RECS), dict(Counter(r["grade"] or "未标" for r in RECS))))


# ---------------- 链接解析 ----------------
def link_of(ident):
    s = ident.strip()
    if not s:
        return "", ""
    if re.match(r"^10\.\d{4,9}/", s):
        return "https://doi.org/" + s, "DOI"
    if "arxiv.org" in s.lower():
        return s, "arXiv"
    if "kns.cnki.net" in s:
        return s, "知网主站"
    if "cnki" in s.lower():
        return s, "知网空间（旧链接）"
    if s.lower().startswith("http"):
        return s, "外部链接"
    return "", "标识符待补"


# ---------------- 分组 ----------------
GROUP_ORDER = ["综述", "期刊论文（英文）", "期刊论文（中文）", "会议论文",
               "学位论文", "专著与教材", "团队/期刊资源页", "其他"]
GROUP_OF_TYPE = {
    "综述": "综述",
    "期刊论文(英文)": "期刊论文（英文）",
    "期刊论文(中文)": "期刊论文（中文）",
    "会议论文": "会议论文",
    "学位论文-硕士": "学位论文",
    "学位论文-博士": "学位论文",
    "专著": "专著与教材",
    "教材": "专著与教材",
    "资源页": "团队/期刊资源页",
}


def group_of(rec):
    t = rec["type"].replace("（", "(").replace("）", ")")
    return GROUP_OF_TYPE.get(t, "其他")


for r in RECS:
    r["group"] = group_of(r)
    r["url"], r["kind"] = link_of(r["ident"])

GROUPS = []
for g in GROUP_ORDER:
    members = [r for r in RECS if r["group"] == g]
    if members:
        GROUPS.append((g, members))


# ---------------- 1. arXiv 脚本 ----------------
ARXIV_IDS = []
for r in RECS:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", r["url"], re.I)
    if m:
        ARXIV_IDS.append(m.group(1))
    elif r["ident"].startswith("10.48550/arXiv."):
        ARXIV_IDS.append(r["ident"].rsplit(".", 1)[-1])
for fn in sorted(os.listdir(BASE)):
    if fn.startswith("references_") and fn.endswith(".bib"):
        for ln in open(os.path.join(BASE, fn), encoding="utf-8", errors="ignore"):
            m = re.search(r"eprint\s*=\s*\{([^}]+)\}", ln, re.I)
            if m:
                ARXIV_IDS.append(m.group(1).strip())
ARXIV_IDS = sorted(set(ARXIV_IDS), key=lambda x: (len(x), x))

if ARXIV_IDS:
    ps = ["# 批量下载 arXiv 预印本 PDF（%d 条）" % len(ARXIV_IDS)]
else:
    ps = ["# 批量下载 arXiv 预印本 PDF（本专题 arXiv 命中 0 条）",
          "# 说明：本专题检索源为 CNKI + CrossRef，未命中 arXiv 条目，本脚本为交付契约占位。",
          "# 日后新增 arXiv 条目时重跑 build_delivery.py 即可自动填充。"]
ps += [
    "# 用法（任选其一；Bypass 用于绕过默认执行策略限制）：",
    "#   pwsh -ExecutionPolicy Bypass -File .\\批量下载_arXiv.ps1",
    "#   powershell -ExecutionPolicy Bypass -File .\\批量下载_arXiv.ps1",
    "# 文件保存到 .\\PDF\\arXiv\\ ；文件名即 arXiv ID，请勿改名。已存在的自动跳过。",
    "",
    "$ErrorActionPreference = 'Continue'",
    "$outDir = Join-Path $PSScriptRoot 'PDF\\arXiv'",
    "New-Item -ItemType Directory -Force -Path $outDir | Out-Null",
    "$ids = @(",
]
for i, aid in enumerate(ARXIV_IDS):
    ps.append('  "%s"%s' % (aid, "," if i < len(ARXIV_IDS) - 1 else ""))
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
open(PS1_OUT, "w", encoding="utf-8-sig").write("\n".join(ps) + "\n")
print("已生成：%s（arXiv %d 条）" % (PS1_OUT, len(ARXIV_IDS)))


# ---------------- 2. RIS ----------------
def ris_type(rec):
    t = rec["type"]
    if "学位论文" in t:
        return "THESIS"
    if t in ("专著", "教材"):
        return "BOOK"
    if "会议论文" in t:
        return "CPAPER"
    if t == "资源页":
        return "GEN"
    if t == "综述" and re.search(r"conference|proceedings|symposium|workshop", rec["venue"], re.I):
        return "CPAPER"
    return "JOUR"


def split_authors(s):
    if not s:
        return []
    parts = re.split(r"\s*[,;、，]\s*|\s+and\s+", s)
    out = []
    for p in parts:
        p = re.sub(r"\s*(主编|编著|编|等)$", "", p.strip())
        if p:
            out.append(p)
    return out


def venue_fields(rec):
    """从 来源/期刊 列解析 刊名/会议名/出版社 与 卷(期): 起-止。解析不出就不写。"""
    src = rec["venue"]
    out = {}
    if not src:
        return out
    m = re.search(r"(\d+)\s*[\(（](\d+)[\)）]\s*[:：]\s*(\d+)\s*[-–~]\s*(\d+)", src)
    if m:
        out["VL"], out["IS"], out["SP"], out["EP"] = m.group(1), m.group(2), m.group(3), m.group(4)
    name = re.split(r",\s*(?:19|20)\d{2}\b", src)[0]
    name = re.split(r",\s*ISBN", name)[0].strip().rstrip(",")
    if not name:
        name = src
    if ris_type(rec) == "CPAPER":
        out["T2"] = name
    elif ris_type(rec) == "BOOK":
        pb = re.search(r"(科学出版社|机械工业出版社|电子工业出版社|中国电力出版社|高等教育出版社|人民邮电出版社)", src)
        out["PB"] = pb.group(1) if pb else name
    else:
        out["JO"] = name
    return out


ris_blocks = []
for r in RECS:
    lines = ["TY  - " + ris_type(r)]
    for a in split_authors(r["author"]):
        lines.append("AU  - " + a)
    lines.append("TI  - " + r["title"])
    vf = venue_fields(r)
    for k in ("T2", "JO", "PB"):
        if k in vf:
            lines.append("%s  - %s" % (k, vf[k]))
    if r["year"]:
        lines.append("PY  - " + r["year"])
    for k in ("VL", "IS", "SP", "EP"):
        if k in vf:
            lines.append("%s  - %s" % (k, vf[k]))
    if r["url"]:
        lines.append("UR  - " + r["url"])
        if "kns.cnki.net" in r["url"]:
            lines.append("DB  - CNKI")
    meta = []
    if r["grade"]:
        meta.append("质量分级 %s" % r["grade"])
    if r["rel"]:
        meta.append("相关性：%s" % r["rel"])
    if r["topic"]:
        meta.append("主题：%s" % r["topic"])
    if r["note"]:
        meta.append(r["note"])
    if meta:
        lines.append("N1  - " + "；".join(meta))
    lines.append("ER  - ")
    ris_blocks.append("\n".join(lines))

open(RIS_OUT, "w", encoding="utf-8", newline="\n").write("\n\n".join(ris_blocks) + "\n")
print("已生成：%s（%d 条）" % (RIS_OUT, len(ris_blocks)))


# ---------------- 3. HTML ----------------
grade_cnt = Counter(r["grade"] for r in RECS if r["grade"])
rel_cnt = Counter(r["rel"] for r in RECS if r["rel"])
cnki_n = sum(1 for r in RECS if "kns.cnki.net" in r["url"])
doi_n = sum(1 for r in RECS if r["kind"] == "DOI")

parts = ["""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>文献下载索引 · %s</title>
<style>
body{font-family:"Microsoft YaHei",system-ui,sans-serif;margin:24px;background:#f7f8fa;color:#1f2328;line-height:1.6}
h1{font-size:22px;border-bottom:2px solid #0969da;padding-bottom:8px}
h2{font-size:17px;margin-top:28px;color:#0969da}
table{border-collapse:collapse;width:100%%;background:#fff;margin-top:8px;font-size:13px}
th,td{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef2f6}
tr:nth-child(even){background:#fafbfc}
a{color:#0969da;text-decoration:none}
a:hover{text-decoration:underline}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:9px;background:#e8f0fe;color:#0b4f9e;white-space:nowrap}
.tag.a{background:#e6f4ea;color:#137333}
.tag.b{background:#e8f0fe;color:#0b4f9e}
.tag.c{background:#f1f3f4;color:#5f6368}
.note{background:#fff8e1;border-left:4px solid #f0b429;padding:10px 14px;margin:16px 0;font-size:13px}
.stat{font-size:13px;background:#fff;border:1px solid #d0d7de;padding:10px 14px;border-radius:6px}
.src{color:#57606a;font-size:12px}
</style></head><body>
<h1>文献下载索引 · %s</h1>
""" % (html.escape(os.path.basename(BASE)), html.escape(os.path.basename(BASE)))]

parts.append("""<div class="note">
<b>使用说明</b><br>
1. 题名即链接：<span class="tag">DOI</span> 指向 doi.org，<span class="tag">知网主站</span> 指向 kns.cnki.net 记录页（<b>全文需机构账号</b>）；<br>
2. 本专题未命中 arXiv 条目，<code>批量下载_arXiv.ps1</code> 为契约占位脚本，日后新增 arXiv 条目重跑生成器即可；<br>
3. 导入 Zotero / EndNote / JabRef：使用同目录 <code>文献清单.ris</code>（全量）与 <code>04_英文文献_仅DOI.bib</code>（仅英文 DOI 部分）；<br>
4. 质量分级 A/B/C 与相关性标注沿用 <code>02_检索说明与检索式.md</code> 第 4 节规则。
</div>""")

parts.append('<div class="stat">共 <b>%d</b> 条；质量分级 A <b>%d</b> / B <b>%d</b> / C <b>%d</b>；'
             '相关性：直接 <b>%d</b>、间接 <b>%d</b>、背景 <b>%d</b>、资源页 <b>%d</b>；'
             '链接：DOI <b>%d</b>、知网主站 <b>%d</b>。</div>'
             % (len(RECS), grade_cnt.get("A", 0), grade_cnt.get("B", 0), grade_cnt.get("C", 0),
                rel_cnt.get("直接", 0), rel_cnt.get("间接-单向交错", 0),
                sum(v for k, v in rel_cnt.items() if k.startswith("背景")), rel_cnt.get("资源", 0),
                doi_n, cnki_n))

for gname, members in GROUPS:
    parts.append("<h2>%s · %d 条</h2>" % (html.escape(gname), len(members)))
    parts.append("<table><tr><th style='width:38px'>#</th><th>题名</th>"
                 "<th style='width:52px'>年份</th><th style='width:230px'>来源</th>"
                 "<th style='width:150px'>分级 / 相关性</th><th style='width:120px'>主题</th>"
                 "<th style='width:88px'>链接</th></tr>")
    for i, r in enumerate(members, start=1):
        t = html.escape(r["title"])
        if r["url"]:
            tcell = '<a href="%s" target="_blank">%s</a>' % (html.escape(r["url"]), t)
        else:
            tcell = t
        gcls = r["grade"].lower() if r["grade"] in ("A", "B", "C") else ""
        badge = '<span class="tag %s">%s</span> / %s' % (gcls, html.escape(r["grade"] or "—"), html.escape(r["rel"] or "—"))
        if r["url"]:
            lcell = '<a href="%s" target="_blank"><span class="tag">%s</span></a>' % (html.escape(r["url"]), html.escape(r["kind"]))
        else:
            lcell = '<span class="tag">无链接</span>'
        parts.append("<tr><td>%d</td><td>%s</td><td>%s</td><td class='src'>%s</td>"
                     "<td>%s</td><td class='src'>%s</td><td>%s</td></tr>"
                     % (i, tcell, html.escape(r["year"]), html.escape(r["venue"][:90]),
                        badge, html.escape(r["topic"]), lcell))
    parts.append("</table>")

parts.append("</body></html>")
open(HTML_OUT, "w", encoding="utf-8").write("\n".join(parts))
print("已生成：%s（%d 组）" % (HTML_OUT, len(GROUPS)))
print("完成：%d 条 → html / ris / ps1" % len(RECS))
