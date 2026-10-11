$expected = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))
$listeners = @(Get-NetTCPConnection -LocalPort 8765,8766 -State Listen -ErrorAction SilentlyContinue)
$stopped = 0
foreach ($processId in ($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
    try {
        $process = Get-Process -Id $processId -ErrorAction Stop
        if ($process.Path -and [IO.Path]::GetFullPath($process.Path) -ieq $expected) {
            Stop-Process -Id $processId -ErrorAction Stop
            Write-Host "已关闭 WTStat 进程 $processId"
            $stopped++
        }
    } catch {
        Write-Host "无法检查或关闭进程 $processId：$($_.Exception.Message)"
    }
}
if ($stopped -eq 0) { Write-Host '未发现可关闭的 WTStat 进程。' }
