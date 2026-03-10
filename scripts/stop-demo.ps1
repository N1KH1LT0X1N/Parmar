$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root ".demo-processes.json"

$targets = @(
    @{ Name = 'uvicorn'; Pattern = 'uvicorn*app.main:app*--port 8000' },
    @{ Name = 'vite'; Pattern = 'vite*--host*127.0.0.1*--port*5173*' },
    @{ Name = 'npm-vite'; Pattern = 'npm*run*dev*' }
)

$ports = @(8000, 5173)
$killed = @()

if (Test-Path $pidFile) {
    try {
        $tracked = Get-Content $pidFile -Raw | ConvertFrom-Json
        foreach ($pid in @($tracked.backendPid, $tracked.frontendPid)) {
            if ($pid) {
                $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($proc) {
                    Stop-Process -Id $pid -Force
                    $killed += [PSCustomObject]@{ Id = $pid; Type = 'tracked' }
                }
            }
        }
    }
    catch {
    }

    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

foreach ($target in $targets) {
    $pattern = $target.Pattern
    $matches = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and ($_.CommandLine -like "*$pattern*")
    }

    foreach ($proc in $matches) {
        if (-not ($killed | Where-Object { $_.Id -eq $proc.ProcessId })) {
            Stop-Process -Id $proc.ProcessId -Force
            $killed += [PSCustomObject]@{ Id = $proc.ProcessId; Type = $target.Name }
        }
    }
}

foreach ($port in $ports) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($listener in $listeners) {
        $pid = $listener.OwningProcess
        if ($pid -and -not ($killed | Where-Object { $_.Id -eq $pid })) {
            Stop-Process -Id $pid -Force
            $killed += [PSCustomObject]@{ Id = $pid; Type = "port-$port" }
        }
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
