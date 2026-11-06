[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $ProjectRoot,
    [Parameter(Mandatory = $true)] [string] $Topic,
    [int] $YearFrom = 0,
    [int] $YearTo = 0,
    [string[]] $Languages = @('中文', '英文'),
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath($ProjectRoot)
if (-not (Test-Path -LiteralPath $project -PathType Container)) {
    throw "ProjectRoot does not exist: $project"
}
if ($Topic.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0 -or [string]::IsNullOrWhiteSpace($Topic)) {
    throw 'Topic must be a non-empty valid directory name.'
}

$topicRoot = [IO.Path]::GetFullPath((Join-Path $project $Topic))
if (-not $topicRoot.StartsWith($project + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Topic must resolve inside ProjectRoot: $topicRoot"
}
if ((Test-Path -LiteralPath $topicRoot) -and -not $Force) {
    throw "Topic directory exists; choose another Topic or use -Force to add missing scaffolding: $topicRoot"
}

New-Item -ItemType Directory -Force -Path $topicRoot | Out-Null
@('raw', 'cache', 'PDF\arXiv', 'PDF\CNKI', 'PDF\other') | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $topicRoot $_) | Out-Null
}

# 过程产物统一落在 <项目>\_archive\<专题>\，专题目录只留交付物（见 AGENTS.md §0/§3）。
$archiveRoot = Join-Path $project '_archive'
New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null

$planPath = Join-Path $topicRoot '检索说明与检索式.md'
if (-not (Test-Path -LiteralPath $planPath)) {
    $yearRange = if ($YearFrom -and $YearTo) { "$YearFrom–$YearTo" } elseif ($YearFrom) { "$YearFrom 起" } else { '待确定' }
    $today = Get-Date -Format 'yyyy-MM-dd'
    $lines = @(
        "# $Topic：检索说明与检索式",
        '',
        "- 检索日期：$today",
        "- 年份范围：$yearRange",
        "- 语种：$($Languages -join '、')",
        '- 数量目标：待确定',
        '- 纳入标准：待补充',
        '- 排除标准：待补充',
        '',
        '## 研究问题',
        '',
        '待补充。',
        '',
        '## 概念组与同义词',
        '',
        '待补充中英文概念组。',
        '',
        '## 检索式与数据源',
        '',
        '| 数据源 | 检索式 | 时间 | 返回数 | 备注 |',
        '| --- | --- | --- | ---: | --- |',
        '| 待补充 | 待补充 | 待补充 | 0 | |',
        '',
        '## 筛选与核验记录',
        '',
        '待补充去重、纳入、排除及字段核验过程。'
    )
    Set-Content -LiteralPath $planPath -Value $lines -Encoding utf8
}

$readmePath = Join-Path $topicRoot 'README.md'
if (-not (Test-Path -LiteralPath $readmePath)) {
    $lines = @(
        "# $Topic",
        '',
        '本目录是独立文献检索任务。`raw/` 保存原始检索结果，`cache/` 保存可重建缓存，`PDF/` 保存合法取得的全文。',
        '最终交付应包含 HTML、XLSX、BibTeX、RIS 和 `批量下载_arXiv.ps1`，并由同一份规范化条目数据生成。',
        '',
        '不要在本目录保存 API key、token、cookie 或账号信息。'
    )
    Set-Content -LiteralPath $readmePath -Value $lines -Encoding utf8
}

Write-Host "Topic workspace: $topicRoot" -ForegroundColor Green
Write-Host "Research plan: $planPath" -ForegroundColor Green
Write-Host "Process archive: $archiveRoot" -ForegroundColor Green
