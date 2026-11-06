# dsh-scholar-digest

> 给 DeepSeek Harness 的学术研究 preset + 文献交付技能：多源检索 → 核验去重 → HTML / XLSX / BibTeX / RIS / arXiv 脚本五件套。
>
> An agent preset and skill pair for DeepSeek Harness: multi-source literature retrieval, verified metadata, and a reproducible five-piece offline deliverable. CNKI (知网) links are mapped from 知网空间 to the download-capable main site server-side, so no browser login or redirect userscript is involved.

[English summary](#english) · [许可](#许可与致谢)

## 解决什么问题

知网只对外提供「知网空间」（`search.cnki.com.cn`）的公开题录接口，返回的链接指向知网空间页面；这类页面在机构 IP 或已登录状态下也不提供下载，能下载的是知网主站的文献页。于是「Agent 查到一批文献之后」和「人真的把 PDF 下下来、把引用整理好」之间，缺一层东西。

本项目补两件事：

1. **preset**：把知网空间题录的链接在服务端换算为 `kns.cnki.net` 主站链接（`servers/cnki-search`），并同屏挂上 arXiv、PubMed / Europe PMC、Semantic Scholar，让学术会话里的检索一次到位。
2. **skill**：`download-paper` 规定「一个专题 = 一个交付目录」，把检索结果整理成可离线浏览的 **HTML 索引**、**xlsx 总表**、**BibTeX**、**RIS**、**arXiv 批量下载脚本**，并带来源追溯与交付自检。

## 是什么，不是什么

| 是 | 不是 |
|---|---|
| DSH preset：学术 persona + 多源检索工具 | 全自动下载器：不代替你在知网/出版商页面点下载 |
| 服务端链接换算：空间链接 → 主站链接 | 浏览器插件方案：不需要装跳转脚本 |
| 交付物生成：五件套 + 自检清单 | 论文写作器：不生成正文，不做综述代写 |
| 可复现：同一份条目数据生成全部交付物 | 登录态管理：不保存 cookie、不碰机构认证 |

## 组成

```
dsh-scholar-digest/
├─ preset/                    DSH 学术研究 preset 生成器与安装说明
│  ├─ gen-preset.py           从已安装 DSH 的 preset-standard 派生 preset
│  ├─ cordis-patch.example.yml 生成出的 patch 示例（路径为占位符）
│  └─ README.md               安装、参数、维护
├─ skills/download-paper/     Agent Skill：批量检索与五件套交付
│  ├─ SKILL.md / AGENTS.md    工作流与交付契约
│  └─ *.py / scripts/         生成器与建专题入口
├─ servers/cnki-search/       CNKI MCP 服务端（上游 Biogod2020/cnki-search 的链接映射分支）
└─ examples/                  虚构数据的完整交付示例
```

## 快速开始

前置：DeepSeek Harness 0.2.x、[uv](https://github.com/astral-sh/uv)、Node.js（PubMed 源经 `npx` 启动）。

```powershell
git clone https://github.com/LiYang-cyber/dsh-scholar-digest.git
cd dsh-scholar-digest

# 1) 让 preset 指向本仓库的 CNKI 服务端，并写入 desktop profile 的 patch 层（自动备份）
python .\preset\gen-preset.py --from-cli --cnki-dir "$PWD\servers\cnki-search" `
  --update-patch "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml"

# 2) 把技能装进你的项目（目录联接，仓库更新后立即生效）
New-Item -ItemType Junction -Path "<你的项目>\.agents\skills\download-paper" -Target "$PWD\skills\download-paper"

# 3) 新建会话选「学术研究」，然后：
#    建专题 → 用检索工具取候选 → 生成五件套（命令见 skills/download-paper/AGENTS.md）
```

`desktop` profile 由 Electron 独占、拒绝 `--dump-default-config`，所以生成器默认从 CLI 管理的 `web` profile 派生（两者共享 `preset-standard`）。完整参数与排错见 [preset/README.md](preset/README.md)。

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

打开 HTML 索引，题名即链接：英文条目跳 DOI / arXiv，中文条目跳知网主站详情页，arXiv 条目旁边有 PDF 直链。下载动作由你在官方页面完成，脚本只负责把「点哪里」按主题分组摆好。

## 示例

[`examples/demo-topic/`](examples/demo-topic/) 是用**虚构数据**跑出来的完整交付示例，可直接打开 `文献下载索引.html` 看形态。重新生成：

```powershell
uv run --with openpyxl python examples/build_demo_dataset.py
uv run --with openpyxl python skills/download-paper/build_delivery.py examples/demo-topic
```

## 兼容性与维护

- 在 **DSH 0.2.2-rc.1 + Windows** 上实测；preset 的插件清单从当前 DSH 的 `preset-standard` 派生，不手抄。
- DSH 升级后重跑一次即可，`--check` 会在 preset 块落后时以非零码退出：

```powershell
python .\preset\gen-preset.py --from-cli --cnki-dir "$PWD\servers\cnki-search" `
  --check "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml"
```

## 已知限制

- preset 定义在宿主启动时 eager 挂载，五个 MCP 进程随应用常驻，与是否选中该 preset 无关。
- 知网服务端走知网空间公开接口：覆盖的是空间题录，不是 KNS 全部馆藏；`kind=thesis` 等上游既有缺陷见 [servers/cnki-search/CHANGES.md](servers/cnki-search/CHANGES.md)。
- 全文能否打开取决于你的机构 IP 或登录状态；本仓库不处理这块。
- 只在 Windows 上实测过，脚本参数与路径都按跨平台写，其他平台未验证。

## 合规

- 不绕过任何访问控制：不内置 cookie/token，不模拟登录，不破解验证码；全文下载由用户在知网或出版商官方页面手动完成。
- 检索走公开接口，请遵守知网与各数据源的使用条款；项目面向个人或授权范围内的科研检索，不用于批量抓取或再分发全文。
- arXiv 下载脚本保留 3 秒请求间隔，这是 arXiv 的礼貌间隔，请勿修改。
- 仓库内不包含任何真实文献 PDF、检索记录或机构凭据。

## 相关项目与差异

智搜生态里已经有一批做得更重的方案：复用浏览器登录态（CDP）、Playwright 自动化、机构 SSO 或中继账号，把「检索 + 下载」做成全自动 MCP server 或工作台。它们在你**有权限、且愿意承担风控维护成本**时更省事。

本项目选的是另一条曲线：**不碰登录态、不做风控对抗**，把「拿到可下载的链接」和「把链接摆成一份能点着下载的交付物」这两步做扎实。所以它更轻、更容易长期维护，也更适合放在公开仓库里。

- [Biogod2020/cnki-search](https://github.com/Biogod2020/cnki-search)：`servers/cnki-search` 的上游，MIT；本项目只做了链接换算那一层。
- CNKI-Redirect 一类油猴脚本：在浏览器端做同样的空间→主站跳转；本项目把这层放到 MCP 服务端，Agent 拿到的 `url` 直接就是主站链接。
- `nature-academic-search`（可选源）：由 [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills) 提供的多源检索 MCP，不属于本仓库。

## 许可与致谢

本仓库：MIT，见 [LICENSE](LICENSE)。

- `servers/cnki-search` 是 [Biogod2020/cnki-search](https://github.com/Biogod2020/cnki-search) 的分支快照，沿用上游 MIT 许可（Copyright (c) 2026 Biogod2020），改动见该目录 `CHANGES.md`。
- 感谢上游作者把「匿名题录检索」这件事做成了一个可复用的 MCP server。

## English

`dsh-scholar-digest` is a DeepSeek Harness agent preset plus an Agent Skill for literature work:

- **preset** — an academic persona with five MCP literature sources. The bundled `servers/cnki-search` maps the CNKI Space (`cnki.com.cn`) metadata link to the main-site `kns.cnki.net` URL that institutional users can actually open, server-side; no browser login or redirect userscript is involved.
- **skill (`download-paper`)** — turns a search topic into a self-contained delivery directory: an offline HTML index, an XLSX table, BibTeX, RIS, and an arXiv batch-download script, all generated from one normalized record set, with a source-traceability contract and a pre-delivery checklist.

Scope: retrieval and packaging only. The project does not automate full-text downloads, does not manage login state, and does not bypass access controls; download links are opened by the user on the official pages.

Requires DeepSeek Harness 0.2.x, `uv`, and Node.js. Tested on Windows with DSH 0.2.2-rc.1. MIT licensed; the CNKI server is a fork of [Biogod2020/cnki-search](https://github.com/Biogod2020/cnki-search) (MIT).
