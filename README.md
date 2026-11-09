# dsh-scholar-digest

> 给 DeepSeek Harness 的学术研究 agent preset + 文献交付技能：多源检索 → 核验去重 → HTML / XLSX / BibTeX / RIS / arXiv 脚本五件套。
>
> An agent preset and skill pair for DeepSeek Harness: multi-source literature retrieval, verified metadata, and a reproducible five-piece offline deliverable. CNKI (知网) links are mapped from 知网空间 to the download-capable main site server-side, so no browser login or redirect userscript is involved.

[安装](#安装) · [工作流](#工作流) · [目录](#目录结构) · [示例](examples/README.md) · [English](#english)

## 它提供什么

**一个插件，两件东西：**

- **「学术研究」agent preset**：学术 persona + 文献数据源（CNKI 主站链接映射、arXiv、PubMed / Europe PMC、Semantic Scholar）+ 常规文件/搜索/网页/任务工具。新建会话时在 preset 选择器里选它。
- **`download-paper` skill**：规定「一个专题 = 一个交付目录」，把检索结果整理成可离线浏览的 **HTML 索引**、**xlsx 总表**、**BibTeX**、**RIS**、**arXiv 批量下载脚本**，并带来源追溯与交付自检。

CNKI 服务端（本仓库 `servers/cnki-search`）随插件一起安装，路径由插件在运行时解析，不需要你手动配置目录。

## 安装

前置：DeepSeek Harness **0.2.2-rc.1 及以上**（见 `engines.dsh`）、[uv](https://github.com/astral-sh/uv)（CNKI / arXiv / Semantic Scholar 源用它启动）、Node.js（PubMed 源经 `npx` 启动）。

```powershell
# npm 安装（推荐）
dsh plugin --profile desktop add dsh-scholar-digest

# 或从 GitHub 安装
dsh plugin --profile desktop add github:LiYang-cyber/dsh-scholar-digest

# 本地开发：直接链接一个 checkout
dsh plugin --profile desktop add link:D:\path\to\dsh-scholar-digest

# 卸载
dsh plugin --profile desktop remove dsh-scholar-digest
```

装好后重启 / 重载应用：新建会话时 preset 选择器里会多出「学术研究」，技能目录里会出现 `download-paper`。

> 如果你之前用 `cordis.patch.yml` 手动定义过同名 preset（`id: academic`），先删掉那段再装插件，否则 preset id 会重复。

## 使用

1. 新建会话，preset 选「学术研究」。
2. 建专题：`<项目>\_archive` 与 `<项目>\<专题名>\`（`scripts/new-topic.ps1` 会建好骨架，也可以手建）。
3. 用 preset 里的检索工具取候选：`mcp__cnki__search`、`mcp__arxiv__*`、`mcp__pubmed__*`、`mcp__semantic-scholar__*`。
4. 生成五件套（命令见 `skills/download-paper/AGENTS.md` §3）。
5. 打开 HTML 索引点着下载 PDF；交付前按 AGENTS.md §4 自检。

```powershell
# 示例：用技能里的生成器把一份 xlsx 总表变成 HTML / RIS / arXiv 脚本
uv run --with openpyxl python "<插件目录>\skills\download-paper\build_delivery.py" "<项目>\<专题>"
```

## 工作流

```
研究主题
   │  preset：CNKI（主站链接）+ arXiv + PubMed + Semantic Scholar
   ▼
候选条目 ── 去重（DOI / arXiv ID / PMID / S2 ID / kns 主站 URL）── 核验 ── 分级
   │  skill：同一份条目数据
   ▼
<项目>/<专题>/  文献下载索引.html · 表格.xlsx · 文献清单.bib · 文献清单.ris · 批量下载_arXiv.ps1
   │  过程产物（检索记录、DOI 对照、知网条目清单）
   ▼
<项目>/_archive/<专题>/
```

下载动作由你在知网或出版商官方页面完成；HTML 页只负责把「点哪里」按主题分组摆好。

## 目录结构

```
dsh-scholar-digest/
├─ package.json               dsh.bundle 清单（dsh plugin add 的入口）
├─ cordis.patch.yml           bundle patch：挂载 lib/index.js 一行
├─ lib/
│  ├─ index.js                Host 插件：注册技能 provider + 学术 preset
│  ├─ preset.js               由 preset-standard 派生的 preset 行（生成物）
│  └─ skill-provider.js       serving skills/download-paper 的 skills provider
├─ locale/{en,zh}.json        插件行显示名与描述
├─ icon.svg                   插件图标
├─ preset/                    手动安装用的 preset 生成器（可选）
│  ├─ gen-preset.py           从已安装 DSH 派生 preset → YAML patch
│  ├─ build-preset-module.py  把 patch 转成 lib/preset.js
│  └─ cordis-patch.example.yml
├─ skills/download-paper/     技能：工作流 + 交付契约 + 生成器
├─ servers/cnki-search/       CNKI MCP 服务端（上游 Biogod2020/cnki-search 的链接映射分支）
└─ examples/                  虚构数据的完整交付示例
```

## 手动安装（定制 / 旧版本）

不装插件、只想把 preset 写进 profile 的 patch 层时：

```powershell
# 生成 patch，并写入 desktop profile（自动备份，只替换标记之间的块）
python .\preset\gen-preset.py --from-cli --cnki-dir "$PWD\servers\cnki-search" `
  --update-patch "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml"

# 漂移检查
python .\preset\gen-preset.py --from-cli --cnki-dir "$PWD\servers\cnki-search" `
  --check "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml"
```

这种方式下技能需要单独装进项目 `.agents\skills\download-paper`。两种方式二选一，不要同时启用同一个 preset id。

## 示例

[`examples/demo-topic/`](examples/demo-topic/) 是用**虚构数据**跑出来的完整交付示例，可直接打开 `文献下载索引.html` 看形态。重新生成：

```powershell
uv run --with openpyxl python examples/build_demo_dataset.py
uv run --with openpyxl python skills/download-paper/build_delivery.py examples/demo-topic
```

## 兼容性与维护

- **宿主要求**：`engines.dsh = ">=0.2.2-rc.1 <0.3.0-0"`，并在 `dsh.compatibility.dshReleases` 里声明 `0.2.2-rc.1+` 兼容。插件只依赖 Host 服务（`ctx.skills`、`ctx.agentPresets`）与 Node 内置模块，不引入额外运行时依赖；preset 行清单来自 0.2.2-rc.1 的 `preset-standard`，更旧的 0.2.x 上 preset 可能挂不起来。
- 在 **DSH 0.2.2-rc.1 + Windows** 上实测。DSH 升级后重新生成 `lib/preset.js`：

```powershell
python .\preset\gen-preset.py --from-cli --cnki-dir "C:/Users/you/.dsh/cnki-kns" --out .\preset\cordis-patch.example.yml
uv run --with pyyaml python .\preset\build-preset-module.py .\preset\cordis-patch.example.yml .\lib\preset.js 0.2.2-rc.1
```

- CNKI 服务端自带测试：`uv run --directory .\servers\cnki-search --extra dev pytest -m "not live" -q`。

## 已知限制

- preset 定义在宿主启动时 eager 挂载，四个文献 MCP 进程随应用常驻，与是否选中该 preset 无关。
- 知网服务端走知网空间公开接口：覆盖空间题录，不是 KNS 全部馆藏；`kind=thesis` 等上游既有缺陷见 [servers/cnki-search/CHANGES.md](servers/cnki-search/CHANGES.md)。
- 全文能否打开取决于机构 IP 或登录状态；本项目不处理登录态。
- 只在 Windows 上实测；脚本参数与路径按跨平台写，其他平台未验证。

## 合规

- 不绕过访问控制：不内置 cookie/token，不模拟登录，不破解验证码；全文下载由用户在知网或出版商官方页面手动完成。
- 检索走公开接口，请遵守知网与各数据源的使用条款；面向个人或授权范围内的科研检索，不用于批量抓取或再分发全文。
- arXiv 下载脚本保留 3 秒请求间隔，请勿修改。
- 仓库内不包含真实文献 PDF、检索记录或机构凭据。

## 相关项目与差异

已有方案多走「复用浏览器登录态（CDP）、Playwright 自动化、机构 SSO 或中继账号」的自动下载路线。本项目选另一条曲线：不碰登录态、不做风控对抗，把「拿到可下载的链接」和「把链接摆成一份能点着下载的交付物」做扎实。

- [Biogod2020/cnki-search](https://github.com/Biogod2020/cnki-search)：`servers/cnki-search` 的上游（MIT），本项目只加了链接换算那一层。
- CNKI-Redirect 一类油猴脚本：在浏览器端做同样的空间→主站跳转；本项目把这一层放到 MCP 服务端。
- `nature-academic-search`：可选多源检索 MCP，来自 [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)，不属于本仓库。

## 许可与致谢

本仓库：MIT，见 [LICENSE](LICENSE)。`servers/cnki-search` 沿用上游 MIT（Copyright (c) 2026 Biogod2020），改动见该目录 `CHANGES.md`。

## English

`dsh-scholar-digest` is a DeepSeek Harness plugin that ships two things: an **academic research preset** (academic persona plus four literature MCP sources, where the bundled CNKI server maps 知网空间 metadata links to the `kns.cnki.net` page institutional users can actually open) and the **`download-paper` skill** (turn a search topic into one delivery directory: offline HTML index, XLSX table, BibTeX, RIS, and an arXiv batch-download script, all from one normalized record set).

Install: `dsh plugin --profile desktop add dsh-scholar-digest` (npm) or `dsh plugin --profile desktop add github:LiYang-cyber/dsh-scholar-digest`. Host requirement: DSH `>=0.2.2-rc.1 <0.3.0-0` (`engines.dsh`), plus `uv` and Node.js; tested on Windows with 0.2.2-rc.1.

Scope: retrieval and packaging only. It does not automate full-text downloads, does not manage login state, and does not bypass access controls. MIT licensed; the CNKI server is a fork of [Biogod2020/cnki-search](https://github.com/Biogod2020/cnki-search) (MIT).
