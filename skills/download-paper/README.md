# download-paper

文献调研技能包：从研究主题出发，批量检索、核验并交付一套可离线浏览的文献材料。技能入口见 [SKILL.md](SKILL.md)，交付契约见 [AGENTS.md](AGENTS.md)（权威）。

## 包结构

| 路径 | 作用 |
|---|---|
| `SKILL.md` | Agent 入口与端到端工作流 |
| `AGENTS.md` | 交付契约：五件套、单一数据源、生成命令、自检与边界 |
| `scripts/new-topic.ps1` | 在调用项目里建专题骨架（`raw/`、`cache/`、`PDF/`、检索说明） |
| `build_index.py` | 从 `*清单*.md` + `references_*.bib` 生成 HTML / xlsx / arXiv 下载脚本 |
| `build_delivery.py` | 从含「文献总表」的 xlsx 生成 HTML / RIS / arXiv 下载脚本 |
| `export_cnki_refs.py` | 导出知网部分的 RIS / BibTeX，过程清单落 `_archive` |
| `export_doi_list.py` | 汇总可确认的 DOI，产物落 `_archive` |
| `agents/openai.yaml` | 面向 Codex 的接口声明（其他 Agent 不读取） |

## 路径约定

技能目录只读。专题与生成物都在调用项目里：

```
<项目>\
├─ .agents\skills\download-paper\   ← 本技能（junction 或副本）
├─ _archive\<专题>\                 ← 过程产物
└─ <专题>\                          ← 五件套交付物
```

四个生成脚本都要求显式传入专题目录，省略参数直接报用法错误，不会把技能目录当工作区。

## 依赖

- `uv`：所有 Python 脚本经 `uv run` 运行，`--with xlsxwriter` / `--with openpyxl` 自动取包。
- PowerShell 7：`new-topic.ps1`。
- 网络：`export_doi_list.py` 访问 arXiv API 与 Crossref；`批量下载_arXiv.ps1` 访问 arxiv.org。
- 检索能力由本仓库 `preset/` 提供的 DSH「学术研究」preset 供给（CNKI / arXiv / PubMed / Semantic Scholar / academic-search）。

## 安装

把技能目录装进调用项目的 `.agents/skills/`，DSH 会在会话工作目录位于该项目时发现它：

```powershell
# Windows：目录联接，技能目录更新后项目立即生效
New-Item -ItemType Junction -Path "<项目>\.agents\skills\download-paper" `
  -Target "<本仓库>\skills\download-paper"

# macOS / Linux
ln -s "<本仓库>/skills/download-paper" "<项目>/.agents/skills/download-paper"
```

也可以直接复制目录，代价是每份副本都要跟随本仓库更新。

## 快速开始

```powershell
# 1. 建专题（同时建 <项目>\_archive）
<技能目录>\scripts\new-topic.ps1 -ProjectRoot <项目> -Topic <专题> -YearFrom 2021

# 2. 用学术 preset 的检索工具填清单与 bib

# 3. 生成交付物（命令与顺序见 AGENTS.md §3）

# 4. 按 AGENTS.md §4 自检后交付
```

## 只读约定

技能目录里不放专题数据、PDF、缓存或生成物；需要改脚本时改本目录，不要在项目副本上改。

## 历史产物

本仓库只发布技能包本身。开发过程中产生的具体专题成品、过程归档与一次性下载脚本未随仓库发布。
