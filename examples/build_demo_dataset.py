"""Build the fictional demo dataset used by examples/demo-topic.

The workbook follows the input contract of skills/download-paper/build_delivery.py:
the first sheet is 文献总表 with the required headers.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

OUT = Path(__file__).resolve().parent / "demo-topic" / "01_示例文献清单.xlsx"

HEADERS = [
    "序号", "题名", "作者", "年份", "来源", "文献类型",
    "质量分级", "相关性", "主题标签", "标识符", "备注",
]

ROWS = [
    [
        1,
        "示例研究：面向文献工作流的批量汇总方法",
        "示例作者甲；示例作者乙",
        2024,
        "示例学报",
        "期刊论文(中文)",
        "A",
        "高",
        "文献工作流",
        "https://kns.cnki.net/kcms/detail/detail.aspx?dbcode=CJFD&filename=EXAMPLE202401001",
        "示例数据：链接与编号均为虚构",
    ],
    [
        2,
        "Example Study on Citation-Graph Assisted Screening",
        "Example, A.; Sample, B.",
        2023,
        "Example Journal of Literature Engineering",
        "期刊论文(英文)",
        "A",
        "高",
        "citation graph",
        "10.9999/example.2023.001",
        "示例数据：DOI 为虚构",
    ],
    [
        3,
        "示例预印本：可复现的文献交付流水线",
        "示例作者丙",
        2024,
        "arXiv preprint",
        "会议论文",
        "B",
        "中",
        "pipeline",
        "https://arxiv.org/abs/2401.99991",
        "示例数据：arXiv ID 为虚构",
    ],
]


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "文献总表"
    ws.append(HEADERS)
    for row in ROWS:
        ws.append(row)

    head_fill = PatternFill("solid", fgColor="DDEBF7")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center")

    widths = [6, 46, 26, 8, 34, 16, 10, 8, 16, 72, 28]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    wb.create_sheet("说明").append(
        ["本工作簿是示例数据：题名、作者、来源、DOI 与 arXiv 编号均为虚构，仅用于演示交付流程。"]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
