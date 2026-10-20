param([switch]$Worker, [int]$Port = 5005)
$ErrorActionPreference = 'Stop'
$monitorRoot = Split-Path -Parent $PSScriptRoot
$outputDirectory = Join-Path $monitorRoot 'dist'
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$launchLog = Join-Path $outputDirectory 'udp-monitor-launch.txt'
if (-not $Worker) {
    try {
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Worker -Port ' + $Port
        Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList $arguments -WorkingDirectory $monitorRoot | Out-Null
    } catch {
        $_ | Out-String | Set-Content -LiteralPath $launchLog -Encoding UTF8
        throw
    }
    exit
}

$ruleName = 'SpatialPointer-UDP-Monitor-' + [guid]::NewGuid().ToString('N')
$ruleAdded = $false
try {
    $pythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        $pythonPath = (Get-Command python.exe -ErrorAction Stop).Source
    }
    if (Get-NetUDPEndpoint -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "UDP $Port is already in use. Stop Blender's UDP receiver, or use -Port 5006."
    }
    if (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue) {
        throw 'The monitor page port 8766 is already in use.'
    }
    New-NetFirewallRule -Name $ruleName -DisplayName 'Spatial Pointer temporary UDP diagnostic' -Direction Inbound -Action Allow -Protocol UDP -LocalPort $Port -Program $pythonPath -RemoteAddress LocalSubnet -Profile Any | Out-Null
    $ruleAdded = $true
    $pythonArguments = @((Join-Path $PSScriptRoot 'udp_monitor.py'), '--port', "$Port")
    $addresses = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and $_.InterfaceAlias -notlike 'vEthernet*'
    }
    foreach ($address in $addresses) { $pythonArguments += @('--pc-ip', $address.IPAddress) }
    "Started $(Get-Date). Temporary firewall rule: $ruleName" | Set-Content -LiteralPath $launchLog -Encoding UTF8
    & $pythonPath @pythonArguments
    if ($LASTEXITCODE -ne 0) { throw "Receiver exited with code $LASTEXITCODE. See udp-monitor-status.json." }
} catch {
    $_ | Out-String | Add-Content -LiteralPath $launchLog -Encoding UTF8
} finally {
    if ($ruleAdded) {
        Remove-NetFirewallRule -Name $ruleName -ErrorAction Continue
        "Temporary firewall rule removed $(Get-Date)." | Add-Content -LiteralPath $launchLog -Encoding UTF8
    }
}
