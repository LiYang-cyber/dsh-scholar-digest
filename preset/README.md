# preset · DSH 学术研究 preset

一套挂进 DeepSeek Harness 的学术研究 agent preset：学术 persona + 文献数据源 + 工具集。preset 本身只是一段 YAML 记录，由 `gen-preset.py` 从当前 DSH 的 `preset-standard` 派生，因此跟着 DSH 版本走。

## 它做了什么

- **persona** 换成学术助手：要求每条文献结论都能对应到工具返回，区分来源原话与推断，知网条目只引用 `url` 字段里的 `kns.cnki.net` 主站链接。
- **文献源**：CNKI（本仓库 `servers/cnki-search`，带主站链接映射）、arXiv、PubMed / Europe PMC、Semantic Scholar；可选 nature-academic-search。
- **工具集**：沿用 `preset-standard` 的文件、搜索、网页、任务、子代理、计划、压缩等插件；`tool-plugin-manager` 在学术会话里关掉，模型不能自行安装插件。
- **技能根**：可选 `--skill-dir` 把某个目录注册为 custom skill root（默认沿用 DSH 配置，项目里装 `.agents/skills` 就能被发现）。

## 前置条件

- DSH 0.2.x（在 0.2.2-rc.1 上验证；`preset-standard` 的插件清单随版本变化，脚本从已安装版本派生）
- `uv`（CNKI / arXiv / Semantic Scholar 服务器通过 `uv` / `uvx` 启动）
- Node.js（PubMed 通过 `npx` 启动）
- 可选环境变量：`SEMANTIC_SCHOLAR_API_KEY`、`PUBMED_EMAIL`、`NCBI_API_KEY`

## 安装

### 1. 准备 CNKI 服务端

preset 默认指向 `$DSH_HOME/cnki-kns`。可以把这个仓库的 `servers/cnki-search` 复制过去：

```powershell
$DSH_HOME = "$env:USERPROFILE\.dsh"
Copy-Item -Recurse "<repo>\servers\cnki-search" "$DSH_HOME\cnki-kns"
uv run --directory "$DSH_HOME\cnki-kns" --extra dev pytest -m "not live" -q
```

也可以直接指到仓库里（`--cnki-dir <repo>/servers/cnki-search`），省一份副本。

### 2. 生成并写入 preset

```powershell
# 先看效果：输出完整 patch 到文件
python <repo>\preset\gen-preset.py --from-cli --cnki-dir "<repo>\servers\cnki-search" `
  --out "$env:TEMP\academic-patch.yml"

# 直接写入 profile 的 patch 层（自动备份，只替换标记之间的块）
python <repo>\preset\gen-preset.py --from-cli --cnki-dir "<repo>\servers\cnki-search" `
  --update-patch "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml"
```

`desktop` profile 由 Electron 独占、拒绝 `--dump-default-config`，所以派生源用 CLI 管理的 `web` profile（`--from-cli` 默认如此）。也可以先 `dsh --profile web --dump-default-config > dump.yml`，再把 `dump.yml` 当位置参数传进来。

### 3. 让新会话默认选中（可选）

```powershell
python <repo>\preset\gen-preset.py --from-cli --out "$env:TEMP\academic-patch.yml" --set-default
```

生成的 `agent-preset-registry` 条目把 `default` 指向 `academic`；已有 profile 里把它合并进 `cordis.patch.yml` 即可。只想手动切换时跳过这一步。

### 4. 重启 / 重载

桌面版会热重载 `cordis.patch.yml`；新建会话时在 preset 选择器里选「学术研究」，工具列表里应出现 `mcp__cnki__*` / `mcp__arxiv__*` / `mcp__pubmed__*` / `mcp__semantic-scholar__*`。

## 维护

DSH 升级后重新派生，不要手改块内清单：

```powershell
python <repo>\preset\gen-preset.py --from-cli --cnki-dir "<repo>\servers\cnki-search" `
  --check "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml"
```

`--check` 在块落后时以非零码退出。手抄的插件清单在 DSH 改版时最容易坏：任何一行解析不到，整个 preset 就挂不起来（`preset-standard` 在 0.2.2-rc.1 删掉了 `dsh-tool-subagent-control/list-agents` 子路径、把 `modelSelectionSettings` 拆成 `modelSelection` / `modelDiscovery`，就是这一类）。

## 参数

| 参数 | 说明 |
|---|---|
| `--from-cli` / `--profile` | 从 `dsh --profile <name> --dump-default-config` 派生（默认 `web`） |
| `--cnki-dir` | CNKI 服务端目录（默认 `$DSH_HOME/cnki-kns`） |
| `--skill-dir` | 额外注册为 custom skill root；默认不动 `preset-standard` 的 skill-filesystem |
| `--academic-search-dir` | 启用可选的 nature-academic-search MCP（指向其 `mcp-server` 目录） |
| `--out` | 输出完整 patch 文件（含标记与说明头） |
| `--preset-only` | 只输出 preset 块 |
| `--update-patch` | 原位替换目标 patch 中标记之间的内容，写备份 |
| `--check` | 漂移检查，落后时非零退出 |
| `--set-default` | 配合 `--out`，把新会话默认 preset 指向 academic |

## 已知限制

- preset 定义在宿主启动时 eager 挂载，所以五个 MCP 进程随应用常驻，与是否选中无关；随会话按需启动需要在 DSH 侧支持，当前做不到。
- CNKI 服务端匿名检索只覆盖知网空间的公开题录接口；全文能否下载取决于机构 IP / 登录态。
- `kind=thesis` 等在知网空间接口上的既有缺陷见 `servers/cnki-search/CHANGES.md`。
