# 批量下载 arXiv 预印本 PDF（1 条）
# 用法（任选其一；Bypass 用于绕过默认执行策略限制）：
#   pwsh -ExecutionPolicy Bypass -File .\批量下载_arXiv.ps1
#   powershell -ExecutionPolicy Bypass -File .\批量下载_arXiv.ps1
# 文件保存到 .\PDF\arXiv\ ；文件名即 arXiv ID，请勿改名。已存在的自动跳过。

$ErrorActionPreference = 'Continue'
$outDir = Join-Path $PSScriptRoot 'PDF\arXiv'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$ids = @(
  "2401.99991"
)
$ok = 0; $skip = 0; $fail = 0
foreach ($id in $ids) {
  $dest = Join-Path $outDir ($id + '.pdf')
  if (Test-Path $dest) { $skip++; continue }
  $url = "https://arxiv.org/pdf/$id"
  try {
    Invoke-WebRequest -Uri $url -OutFile $dest -TimeoutSec 90 -UserAgent 'Mozilla/5.0' -UseBasicParsing -ErrorAction Stop
    Write-Host "[OK]   $id"
    $ok++
  } catch {
    if (Test-Path $dest) { Remove-Item $dest -Force -ErrorAction SilentlyContinue }
    Write-Host "[FAIL] $id  $($_.Exception.Message)"
    $fail++
  }
  Start-Sleep -Seconds 3   # arXiv 礼貌请求间隔，勿删
}
Write-Host ""
Write-Host "完成：成功 $ok，跳过 $skip，失败 $fail。目录：$outDir"
