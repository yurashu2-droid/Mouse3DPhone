param([switch]$Worker, [int]$Port = 8767)
$ErrorActionPreference = 'Stop'
$petRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$petOutput = Join-Path $petRoot 'dist\bullet-pet'
New-Item -ItemType Directory -Path $petOutput -Force | Out-Null
$petLog = Join-Path $petOutput 'launcher.log'

if (-not $Worker) {
    try {
        $petArguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Worker -Port ' + $Port
        Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList $petArguments -WorkingDirectory $petRoot | Out-Null
    } catch {
        $_ | Out-String | Set-Content -LiteralPath $petLog -Encoding UTF8
        throw
    }
    exit
}

$petRule = 'BulletPet-Temporary-' + [guid]::NewGuid().ToString('N')
$petRuleAdded = $false
$petProcess = $null
try {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $Port is already in use. Open http://127.0.0.1:$Port/ if the game is already running."
    }
    $petPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $petPython)) {
        $petPython = (Get-Command python.exe -ErrorAction Stop).Source
    }
    New-NetFirewallRule -Name $petRule -DisplayName 'Bullet Pet temporary LAN game' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Program $petPython -RemoteAddress LocalSubnet -Profile Any | Out-Null
    $petRuleAdded = $true
    $petReady = Join-Path $petOutput 'ready.json'
    Remove-Item -LiteralPath $petReady -ErrorAction SilentlyContinue
    $petArguments = '-X utf8 "' + (Join-Path $PSScriptRoot 'server.py') + '" --port ' + $Port + ' --ready-file "' + $petReady + '"'
    $petProcess = Start-Process -FilePath $petPython -ArgumentList $petArguments -WorkingDirectory $petRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $petOutput 'server.log') -RedirectStandardError (Join-Path $petOutput 'server-error.log')
    for ($petTry = 0; $petTry -lt 80; $petTry++) {
        if (Test-Path -LiteralPath $petReady) { break }
        if ($petProcess.HasExited) { throw 'Game server exited. See dist/bullet-pet/server-error.log.' }
        Start-Sleep -Milliseconds 100
    }
    if (-not (Test-Path -LiteralPath $petReady)) { throw 'Game server did not become ready.' }
    "Started $(Get-Date). LocalSubnet TCP $Port. Rule: $petRule" | Set-Content -LiteralPath $petLog -Encoding UTF8
    Start-Process "http://127.0.0.1:$Port/" | Out-Null
    # PC page has an explicit server shutdown button. No hidden permanent service.
    if (-not $petProcess.WaitForExit(7200000)) { $petProcess.Kill() }
} catch {
    $_ | Out-String | Add-Content -LiteralPath $petLog -Encoding UTF8
} finally {
    if ($petProcess -and -not $petProcess.HasExited) { $petProcess.Kill() }
    if ($petRuleAdded) {
        Remove-NetFirewallRule -Name $petRule -ErrorAction Continue
        "Temporary LAN rule removed $(Get-Date)." | Add-Content -LiteralPath $petLog -Encoding UTF8
    }
}
