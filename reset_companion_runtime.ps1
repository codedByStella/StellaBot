param([switch]$NoPause)

function Clear-CompanionMemory {
    $repoRoot = $PSScriptRoot
    $companionEntry = Join-Path $repoRoot 'companion.py'
    $runtimeDir = Join-Path $repoRoot '.companion_runtime'

    if (-not (Test-Path -LiteralPath $companionEntry)) {
        Write-Host "companion.py was not found beside this script." -ForegroundColor Red
        return
    }

    $running = @(Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'companion\.py' })

    if ($running.Count -gt 0) {
        $pids = ($running | ForEach-Object { $_.ProcessId }) -join ', '
        Write-Host "Companion is still running (PID $pids). Close Companion's window first, then run this again." -ForegroundColor Yellow
        return
    }

    if (-not (Test-Path -LiteralPath $runtimeDir -PathType Container)) {
        Write-Host "Nothing to clear. Companion has no runtime data directory."
        return
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $archive = Join-Path $repoRoot "memory_archive-$stamp"

    try {
        Move-Item -LiteralPath $runtimeDir -Destination $archive -ErrorAction Stop
    }
    catch {
        Write-Host "Could not archive Companion runtime data: $($_.Exception.Message)" -ForegroundColor Red
        return
    }

    Write-Host ""
    Write-Host "Done. Companion will create a fresh runtime directory next launch." -ForegroundColor Green
    Write-Host "Kept: companion_profile.json, .env, .venv, companion.py, and checked-in reference artifacts."
    Write-Host ""
    Write-Host "Archive: $archive"
    Write-Host "To undo: Move-Item -LiteralPath '$archive' -Destination '$runtimeDir'"
    Write-Host "To delete archive: Remove-Item -LiteralPath '$archive' -Recurse"
}

Clear-CompanionMemory

if (-not $NoPause) {
    Write-Host ""
    Read-Host "Press Enter to finish" | Out-Null
}