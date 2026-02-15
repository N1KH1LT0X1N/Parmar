$ErrorActionPreference = 'SilentlyContinue'

$targets = @(
    @{ Name = 'uvicorn'; Pattern = 'uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000' },
    @{ Name = 'vite'; Pattern = 'vite --host 127.0.0.1 --port 5173' },
    @{ Name = 'npm-vite'; Pattern = 'npm run dev' }
)

$killed = @()

foreach ($target in $targets) {
    $matches = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and ($_.CommandLine -like "*${($target.Pattern)}*")
    }

    foreach ($proc in $matches) {
        Stop-Process -Id $proc.ProcessId -Force
        $killed += [PSCustomObject]@{ Id = $proc.ProcessId; Type = $target.Name }
    }
}

if ($killed.Count -eq 0) {
    Write-Host "No demo processes found to stop."
    exit 0
}

Write-Host "Stopped demo processes:"
$killed | Sort-Object Id -Unique | ForEach-Object {
    Write-Host "- PID $($_.Id) ($($_.Type))"
}
