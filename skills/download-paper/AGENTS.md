# AGENTS.md · 文献调研交付契约

本文件是 download-paper 技能的交付契约，**唯一权威来源**；`README.md` 只描述包结构，两者冲突以本文件为准。

## 0 路径约定

- **技能目录**：本文件所在目录，只读。生成脚本在技能根，建专题入口在 `scripts/`。
- **调用项目根**：运行任务时的工作目录，也是专题的父目录。
- **专题目录**：`<项目>/<专题名>/`，一次任务一个，名字语义明确。
- **过程产物**：`<项目>/_archive/<专题名>/`。专题目录只放交付物与清单正文。
- 四个生成脚本都要求显式传入专题目录；省略参数会报用法错误，不会退回到技能目录。

## 1 交付契约：五件套，缺一不算完成

每个专题目录必须**同时**存在下列五类文件。

| # | 交付物 | 文件名 | 硬要求 |
|---|---|---|---|
| 1 | HTML 索引 | `文献下载索引.html` | 单文件、断网可开（样式内联，不引 CDN）；按主题分组成 `<h2>+<table>`；题名即链接，指向 arXiv abs / `doi.org` / 知网主站记录页 / 出版商页；arXiv 条目另给 `arXiv PDF` 直链，本地已有该 PDF 时标「已下载」 |
| 2 | BibTeX | `*.bib` | 每条有唯一 citekey；必含 `author` / `title` / `year`；arXiv 条目含 `eprint` 与 `archiveprefix`；中文条目含 `url`，出处与推断字段写进 `note`，不臆造卷期页码 |
| 3 | RIS | `*.ris` | 覆盖**专题条目全集**（条数 = 表格总数）；可与语种子集 bib 并存，但须在 HTML 说明里写明两者范围差；每条以 `TY  - ` 起、`ER  - ` 结束；中文条目带 `DB  - CNKI`；类型映射 JOUR / CPAPER / THESIS / BOOK / GEN |
| 4 | 表格 | `*.xlsx` | 至少一张「全部条目」表：题名、作者、年份、来源、文献类型、质量分级、相关性、主题标签、标识符、备注；首行冻结 + 自动筛选。有 arXiv 条目加「arXiv 可直下_全量」表，有本地 PDF 加「本地PDF清单」表 |
| 5 | arXiv 脚本 | `批量下载_arXiv.ps1` | 由 bib 的 `eprint` 生成；存到 `PDF\arXiv\`；文件名 = arXiv ID（改名会使索引「已下载」标记失效）；已存在跳过；每次请求间隔 3 秒（arXiv 礼貌间隔，**勿删**） |

### 1.5 专题没有 arXiv 条目时

仍须交付 `批量下载_arXiv.ps1`：空 `$ids` 列表 + 文件头注释写「本专题 arXiv 命中 0 条，脚本仅为契约占位」。**不得**以"没有 arXiv"为由省略该文件。

### 1.6 允许的附加交付（不替代五件套）

`*_文献清单.md`、检索说明/检索式 md、文献导读 md、专题自己的 `build_*.py` 等生成脚本。

---

## 2 单一数据源

- 同一专题的 bib / ris / html / ps1 / xlsx 必须从**同一份条目数据**生成，不得各自手改。改数据后整套重跑。
- 数据源两种形态，按专题既有结构选择：
  - **Markdown 表格型**：`*清单*.md` 的表格 + `references_*.bib` → `build_index.py`
  - **xlsx 内嵌型**：含「文献总表」的 `.xlsx` → `build_delivery.py`
- 中文条目的标识符**只能**用 CNKI 工具返回的 `url`（`kns.cnki.net/kcms/detail/detail.aspx?dbcode=..&filename=..`）。该端点对任意 filename 都返回 200，链接不可按 URL 规则手工拼接。

---

## 3 生成命令

`<技能目录>` 是本技能所在目录（项目里通常是 `<项目>\.agents\skills\download-paper`），`<专题>` 是 `<项目>\<专题名>`：

```powershell
# 索引 html / xlsx / ps1 —— 需要 xlsxwriter
uv run --with xlsxwriter python <技能目录>\build_index.py <专题>

# 知网 RIS / BibTeX —— 纯标准库；知网条目清单落到 <项目>\_archive\<专题名>\
uv run python <技能目录>\export_cnki_refs.py <专题>

# 通用交付生成器：从含「文献总表」的 xlsx 生成 html / ris / ps1
uv run --with openpyxl python <技能目录>\build_delivery.py <专题>

# DOI 列表与对照表 —— 需联网访问 arXiv API 与 Crossref，产物落 <项目>\_archive\<专题名>\
uv run python <技能目录>\export_doi_list.py <专题>
```

`uv` 全局缓存在沙箱下不可写，如遇 `Failed to initialize cache`，先设：

```powershell
$env:UV_CACHE_DIR = '<项目>\.uv-cache'
```

**顺序**：先放全文进 `PDF\` → 再跑 `build_index.py`（它会重扫 `PDF\`，刷新「本地PDF清单」表与「已下载」标记）。

脚本的过程文件（DOI 列表、对照表、知网条目清单、crossref 缓存）统一写进 `<项目>\_archive\<专题名>\`，专题目录只留五件套与清单正文。

---

## 4 交付前自检（逐条勾）

- [ ] 五件套齐全，且都在专题目录**顶层**（不放子目录）
- [ ] ris 条数 = 表格总条数；arXiv 条目全部出现在 ps1 的 `$ids` 中
- [ ] ps1 里 `Start-Sleep -Seconds 3` 仍在
- [ ] HTML 用浏览器打开：分组、外链、`已下载` 标记均正常，无 JS 报错
- [ ] xlsx 每张表有表头样式、冻结首行、自动筛选
- [ ] 报告给用户的条数，与 bib / ris / xlsx 实际条数一致（不一致先查再报）

---

## 5 边界（不要做）

- 不把过程文件（DOI 列表、缓存、核查 CSV、迁移快照）放进专题目录，一律进 `<项目>\_archive\<专题名>\`。
- 不在文件里写入真实 API key / token / 知网账号。
- 不手工拼知网链接；不改 arXiv PDF 文件名。
- 不把技能目录当工作区：不在其中建专题、存 PDF、跑生成脚本。
- 不为凑篇幅臆造参数、卷期页码、DOI 或全文链接。
