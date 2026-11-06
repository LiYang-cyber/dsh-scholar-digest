# cnki-search（链接映射分支）

本目录是 [Biogod2020/cnki-search](https://github.com/Biogod2020/cnki-search) 的分支快照，供 dsh-scholar-digest 的 preset 直接引用。

上游从知网空间（`search.cnki.com.cn`）的公开检索接口取题录，返回的链接指向知网空间页面；这类页面在机构 IP 或已登录状态下也不提供下载。本分支在**服务端**把链接换算为知网主站（`kns.cnki.net`）文献页，其余检索行为保持不变：

```
url        = https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=<dbcode>&filename=<filename>
space_url  = 原知网空间链接（仅用于 get_record 回读摘要）
```

完整改动清单、映射规则、匿名回退策略与实测记录见 [CHANGES.md](CHANGES.md)。

## 工具

| 工具 | 作用 |
|---|---|
| `search` | 按主题、篇名、关键词、全文或摘要检索；可限定作者、导师、年份、文献类型 |
| `get_record` | 根据检索得到的链接读取摘要与学位信息；支持主站链接与空间链接回读 |

`search` 参数：`query`、`field`（`theme`/`title`/`keyword`/`content`/`summary`）、`page`（1–50）、`author`、`advisor`、`year`、`kind`（`all`/`journal`/`thesis`/`phd`/`master`）、`sort`（`relevance`/`date`/`downloads`/`cites`）。

返回 `status`：`ok` 正常；`blocked` 接口拒绝或触发校验页；`error` 参数或网络错误。`blocked` 不是零结果。

## 运行

```bash
# 本仓库内（工作目录为本目录）
uv run --directory . cnki-search
```

进程在 stdio 上等待 MCP 宿主，没有交互提示。需要 [uv](https://github.com/astral-sh/uv) 与 Python 3.12+。

## 测试

```powershell
uv run --directory . --extra dev pytest -m "not live" -q
$env:RUN_LIVE_CNKI=1; uv run --directory . --extra dev pytest -m live -s   # 联网回归，按需手动跑
```

## 上游与许可

- 上游：<https://github.com/Biogod2020/cnki-search>（MIT，Copyright (c) 2026 Biogod2020）
- 本目录沿用上游 MIT 许可，许可原文见 [LICENSE](LICENSE)
- 本分支的改动、实测事实与已知缺陷见 [CHANGES.md](CHANGES.md)

本目录只读使用：不要在这里放专题数据、下载的 PDF 或凭据。
