$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$source = "D:\AgiCode"
$dest = "D:\AgiCode_backups\agicode_$timestamp"
$maxBackups = 7

Write-Host "[AgiCode Backup] 开始备份..." -ForegroundColor Cyan

# 创建备份目录
if (-not (Test-Path "D:\AgiCode_backups")) {
    New-Item -ItemType Directory -Path "D:\AgiCode_backups" -Force | Out-Null
}

# 排除 __pycache__ 和 .pytest_cache
Copy-Item -Path $source -Destination $dest -Recurse -Force -Exclude @("__pycache__", ".pytest_cache", "*.pyc")

Write-Host "[AgiCode Backup] ✅ 备份完成: $dest" -ForegroundColor Green

# 清理旧备份（保留最近7个）
$backups = Get-ChildItem "D:\AgiCode_backups" -Directory | Sort-Object Name -Descending
if ($backups.Count -gt $maxBackups) {
    $backups[$maxBackups..($backups.Count-1)] | ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force
        Write-Host "[AgiCode Backup] 🗑️ 删除旧备份: $($_.Name)" -ForegroundColor Yellow
    }
}

Write-Host "[AgiCode Backup] ✅ 完成 (保留 $maxBackups 个备份)" -ForegroundColor Green
