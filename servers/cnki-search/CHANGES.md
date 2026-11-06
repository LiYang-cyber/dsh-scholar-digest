# cnki-kns —— 本次分支说明

本目录是 [Biogod2020/cnki-search](https://github.com/Biogod2020/cnki-search) 的**分支快照**，
只做一件事：**把返回的文献链接从知网空间（`cnki.com.cn`）换成知网主站（`kns.cnki.net`）**。

上游只返回知网空间链接，而那类页面在机构 IP 或已登录状态下**也不提供下载**；
能下载的是知网主站的文献页。所以这里不重写检索，只在服务端把链接换算掉。

## 改了什么

| 文件 | 改动 |
|---|---|
| `src/cnki_scholar/kns.py` | 新增。`dbcode` + `filename` → `kns.cnki.net/kcms/detail/detail.aspx` 的映射规则与解析函数；`filename` 去掉路径分隔符（`mall.cnki.net` 的杂志路径会把 `/` 带进来，拼出 `filename=/GJDW…` 这种非规范链接） |
| `src/cnki_scholar/parse.py` | 列表项解析时读取 `data-fn` 与 `/<dbalias>/Detail/RedirectSpace/` 链接，产出主站链接；详情页解析同样映射；新增 `is_not_found_html()` 识别知网那种「HTTP 200 的 404 页」 |
| `src/cnki_scholar/models.py` | `Record` / `RecordDetail` 增加 `space_url`、`dbcode`、`filename` 字段 |
| `src/cnki_scholar/service.py` | 映射失败时在 `warnings` 里显式报出，不静默返回知网空间链接；`get_record` 支持主站链接，遇到登录跳转时回退到**可推导**的匿名页面（期刊 → `www`，报纸 → `mall`），学位论文不猜链接而是如实报登录墙；不存在的文献返回 `record_not_found` 而不是一条空记录 |
| `src/cnki_scholar/server.py` | MCP 工具说明改为「引用 `url` 字段」 |

对外契约不变：工具名仍是 `search` / `get_record`，`url` 仍是那条要引用、要打开的链接。
只是 `url` 现在指向知网主站，知网空间原链接降级为 `space_url`（仅用于 `get_record` 回读摘要）。

## 映射规则

几乎所有知网文献都由 `dbcode` + `filename` 唯一确定，主站链接为：

```
https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=<dbcode>&filename=<filename>
```

两个值从知网空间页面的独立锚点读取：

- **`filename` 以 `data-fn` 属性为准**。学位论文的 `data-fn` 自带 `.nh` 后缀
  （`1025564694.nh`），而可见 URL 丢掉了它（`CDMD-10533-1025564694.htm`）；
  自己按 URL 拼后缀会拼错，这正是 CNKI-Redirect 油猴脚本必须代劳的那一步。
- `dbcode` 取来源行里 `/<dbalias>/Detail/RedirectSpace/<filename>` 的别名段
  （`cjfd` → `CJFD`），回退到文章 URL 的 `/Article/CJFDTOTAL-...` 前缀。

刻意**没有**移植 CNKI-Redirect 里那套 dbcode 解码（`CJFDTOTAL` 之类补位串的字符位置推算）：
它依赖 `index()` 返回 `-1` 时的负数索引，在 JS 与 Python 下行为不一致，且上面的锚点更直接可靠。

## 匿名回退与「不猜链接」

`get_record` 拿到的是 `kns.cnki.net` 主站链接时，无机构权限会 302 到登录页。此时只回退到
**能从 `dbcode` + `filename` 推导出来**的匿名页面：

| 类型 | dbcode | 匿名回退 |
|---|---|---|
| 期刊 | `CJFD` | `www.cnki.com.cn/Article/CJFDTOTAL-<filename>.htm` |
| 报纸 | `CCND` | `mall.cnki.net/magazine/article/CCND/<filename>.htm` |
| 学位论文 | `CDMD` / `CDFD` / `CMFD` | **无**：匿名页 URL 形如 `CDMD-<授予单位号>-<filename>.htm`，那个单位号只存在于知网空间路径里，`dbcode`+`filename` 复原不出来。`CDMD-<filename>.htm` 与 `CDMD-<filename>.nh.htm` 都 302 到 `/404.htm`，所以这里不生成链接，改为如实返回 `blocked` / `login_required_for_record` |

同理，知网对**不存在的文献**返回的是 HTTP 200 的 404 页（两种形态：`www` 上 `<title>` 为空的
`/404.htm` 外壳；`mall` 上限流时 1 KB 的 `<title>404</title>` 页）。两种都被识别为
`error` / `record_not_found`，不再被当成一条字段为空的记录。`mall` 上这两种含义无法区分，
所以该主机的 miss 会附一条 `soft_404_on_mall_host` 警告，提示先重试再下结论。

## 验证

```powershell
# 离线单元测试（含映射规则、fixtures 驱动的解析断言）
uv run --directory . pytest -m "not live" -q

# 联网回归
$env:RUN_LIVE_CNKI=1; uv run --directory . pytest -m live -s
```

联网回归覆盖四条：检索返回的 `url` 与 `dbcode`+`filename` 自洽、`space_url` 交回
`get_record` 能闭环出同一条主站链接、不存在的文献报 `record_not_found`、关键词检索仍能命中。
`-m live` 是选择加入的，CI/日常跑不到，所以分支契约变化时必须手动跑一次。

`uv run pytest` 若报 `Failed to initialize cache` 或找不到临时目录，说明当前环境
（沙箱 / 受限账户）的 uv 缓存或 `%TEMP%` 不可写，显式指定即可：

```powershell
$env:UV_CACHE_DIR="$env:TEMP\uvcache"; $env:TEMP="$env:TEMP\uvtmp"; $env:TMP=$env:TEMP
```

## 已实测确认的事实（2026-10）

- 主站链接有效：`kcms/detail/detail.aspx?dbcode=CJFD&filename=ZXKC202625006`
  在无机构访问权限时 302 到 `login.cnki.net` 登录页；机构 IP 下直接进入详情页。
- **主站链接无法自证**：该 URL 对任意 `filename`（含不存在的编号）都返回 200（或 302 到登录页），
  所以不能用 HTTP 状态码判断「这条链接确实指向目标文献」。判据只能是 `dbcode` + `filename`，
  而这两个值必须来自工具返回，不能按知网空间 URL 手工推导。
- 知网空间列表页 HTML 中，每个列表项都带 `data-fn`，来源行都带 `RedirectSpace` 链接，
  映射无需额外抓取详情页。
- **空间链接 → 主站链接可闭环**：把 `space_url` 交给 `get_record` 会回读页面上的
  `data-dbcode` / `data-fn`，返回与检索时一致的主站链接（期刊 `CJFD`、学位 `CDMD`、报纸 `CCND` 均已实测）。
  已知链接时这是比再检索一次更短、更权威的取链接方式。
- **`field=title` 是模糊召回，不是精确匹配**：用一整条标题检索会返回 20 条，目标可能排在十几位之后；
  `field=theme` 甚至可能一条都不命中。所以不能用「标题逐字相等」判断工具是否找对了文献，
  只能用 `space_url`（或 `dbcode`+`filename`）相等来判断。同一篇文献在检索接口与详情接口的
  标题排版还可能不同（中文与拉丁字符之间是否留空格）。
- **学位论文的 `filename` 带 `.nh` 后缀**，且 `data-fn` 才是权威来源；知网空间可见 URL 丢掉了它。
  学位论文的主站 `dbcode` 是 `CDMD`（不是 `CMFD`），也不能按链接猜。
- **`cdmd.cnki.com.cn` 会间歇性返回 HTTP 418**：连续请求后触发，等待一段时间自行恢复。
  遇到 418 应当重试，不要当作「文献不存在」。
- `kind=thesis` / `phd` / `master` 恒返回 0 条：上游的 `Type` 参数对知网空间接口无效，
  只在解析后按「博士论文/硕士论文」标签过滤，而该接口的列表里只有期刊。
  这是上游既有缺陷，本次**未修**。
- 知网空间不提供 DOI，详情页也没有 DOI 字段；不要从该数据源推断 DOI。
- `year` 对期刊常为空：知网空间期刊列表的 `p.source` 里只有「2026年25期」这类期号，
  没有独立年份 span。同为上游既有缺陷。
- 期刊链接可同时用 `dbcode=CCJD` 作为备选（CNKI-Redirect 的 `alter`），本次未启用。

## 如何跟上上游

上游只有 3 个 commit、版本 `0.1.0`，改动集中在上面 5 个文件。升级步骤：

```powershell
git clone --depth 1 https://github.com/Biogod2020/cnki-search.git <tmp>
# 用上游覆盖除 kns.py 之外的文件，再把下列改动重新应用：
#   parse.py / models.py / service.py / server.py
uv run --directory . pytest -m "not live" -q
```

映射逻辑本身与上游解耦：如果上游日后自己返回主站链接，`kns.to_kns_url()` 对已是
`kns.cnki.net` 的链接会原样返回，本分支可以直接退掉。

## 在 DSH 里的接线

本仓库 `preset/` 生成的 `mcp-cnki` 条目指向本目录：

```yaml
command: uv
args: [run, --directory, <本仓库>/servers/cnki-search, cnki-search]
```

用 `preset/gen-preset.py --cnki-dir <本仓库>/servers/cnki-search` 生成，重新派生不会被上游 `uvx` 配置覆盖。

生成器的派生源是 CLI 管理的 profile——`dsh --profile <name> --dump-default-config`；
由 Electron 独占的 desktop profile 拒绝 dump，需从 `web` 这类 CLI profile 派生。
脚本输出与手改过的 patch 折行不同，所以改完只做 YAML 语义对比，不逐行 diff。

## 许可

沿用上游 MIT，随 dsh-scholar-digest 一起发布；上游许可原文见 [LICENSE](LICENSE)。
