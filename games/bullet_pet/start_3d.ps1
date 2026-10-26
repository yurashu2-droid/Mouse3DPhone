param([int]$Port = 8767)
$ErrorActionPreference = 'Stop'
$petRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$petEngineCandidates = @(
    (Join-Path $petRoot 'runtime\Godot.exe'),
    (Join-Path $petRoot 'dist\godot-runtime\Godot_v4.7.2-stable_win64.exe')
)
$petEngine = $petEngineCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $petEngine) {
    $petCommand = Get-Command godot.exe -ErrorAction SilentlyContinue
    if ($petCommand) { $petEngine = $petCommand.Source }
}
if (-not $petEngine) {
    throw 'Godot runtime is missing. Use the BulletPet-PC-3D.zip package, or put Godot 4 in runtime/Godot.exe.'
}
$petReady = $false
try {
    $petConfig = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/config" -TimeoutSec 2
    $petReady = $petConfig.version -eq '0.4.0'
} catch {}
if (-not $petReady) {
    & (Join-Path $PSScriptRoot 'start.ps1') -Port $Port
    for ($petTry = 0; $petTry -lt 100; $petTry++) {
        try {
            $petConfig = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/config" -TimeoutSec 1
            if ($petConfig.version -eq '0.4.0') { $petReady = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 200
    }
}
if (-not $petReady) { throw 'Game server did not start. See dist/bullet-pet/launcher.log.' }
$petArguments = '--path "' + (Join-Path $PSScriptRoot 'godot') + '" -- --port=' + $Port
Start-Process -FilePath $petEngine -ArgumentList $petArguments -WorkingDirectory $petRoot | Out-Null
