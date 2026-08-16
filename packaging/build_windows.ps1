$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "Building WITNESS Windows desktop package..."
python packaging\validate_source_tree.py
if ($LASTEXITCODE -ne 0) { throw "Release source validation failed." }
python -m pip install --upgrade pip
python -m pip install -r packaging\requirements-desktop.txt

Remove-Item -Recurse -Force build, dist, release -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --clean packaging\witness.spec

$env:QT_QPA_PLATFORM = "offscreen"
$env:WITNESS_DATA_DIR = Join-Path $env:TEMP "witness-packaging-smoke"
$env:WITNESS_SMOKE_MARKER = Join-Path $env:TEMP "witness-packaging-smoke.ok"
Remove-Item -Recurse -Force $env:WITNESS_DATA_DIR -ErrorAction SilentlyContinue
Remove-Item -Force $env:WITNESS_SMOKE_MARKER -ErrorAction SilentlyContinue
$p = Start-Process -FilePath ".\dist\WITNESS\WITNESS.exe" -ArgumentList "--smoke-test" -PassThru
if (-not $p.WaitForExit(30000)) {
    try { $p.Kill() } catch {}
    throw "Frozen WITNESS smoke test timed out."
}
if ($p.ExitCode -ne 0) { throw "Frozen WITNESS smoke test exited $($p.ExitCode)." }
if (-not (Test-Path $env:WITNESS_SMOKE_MARKER)) {
    throw "Frozen WITNESS did not reach the Qt shell/backend smoke marker."
}

$iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    throw "Inno Setup 6 was not found. Install it, then run this script again."
}
$version = python -c "from app_version import VERSION; print(VERSION)"
& $iscc "/DMyAppVersion=$version" packaging\WITNESS.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed." }

$setup = Resolve-Path .\release\WITNESS-Setup.exe
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  WITNESS-Setup.exe" | Set-Content -Encoding ascii .\release\WITNESS-Setup.exe.sha256
Write-Host ""
Write-Host "Ready: $setup"
Write-Host "SHA256: $hash"
