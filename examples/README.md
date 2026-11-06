# examples · 交付物长什么样

`demo-topic/` 是一份用虚构数据跑出来的完整交付目录，用来展示 `skills/download-paper` 的五件套形态：

| 文件 | 说明 |
|---|---|
| `01_示例文献清单.xlsx` | 输入数据（含「文献总表」工作表，可被 `build_delivery.py` 直接读取） |
| `文献下载索引.html` | 单文件、断网可开的索引页：题名即链接，按文献类型分组 |
| `文献清单.ris` | 全量 3 条的 RIS，中文条目带 `DB  - CNKI` |
| `文献清单.bib` | 对应 BibTeX；含 arXiv 条目的 `eprint` / `archiveprefix` |
| `批量下载_arXiv.ps1` | 从 bib 的 `eprint` 生成的 arXiv 下载脚本（含 3 秒礼貌间隔） |

**这些数据全部是虚构的**：题名、作者、期刊名、DOI `10.9999/...`、arXiv `2401.99991` 与知网 filename 都只是占位符，用于演示结构，不要当作真实文献引用。

## 重新生成

```powershell
# 1. 重建示例数据（虚构条目）
uv run --with openpyxl python examples/build_demo_dataset.py

# 2. 用技能里的生成器重跑交付物
uv run --with openpyxl python skills/download-paper/build_delivery.py examples/demo-topic
```

第 2 步会覆盖 `文献下载索引.html`、`文献清单.ris`、`批量下载_arXiv.ps1`；`文献清单.bib` 是手写的配套示例。

## 看什么

- 浏览器打开 `文献下载索引.html`：分组、题名链接、arXiv 条目旁的 PDF 直链。
- `文献清单.ris`：条数（3）与表格行数一致，每条以 `TY  -` 开头、`ER  -` 结尾。
- `批量下载_arXiv.ps1`：`$ids` 里是 `2401.99991`，脚本自带 `Start-Sleep -Seconds 3`。
- xlsx：首行冻结 + 自动筛选，且「文献总表」是唯一数据源。
