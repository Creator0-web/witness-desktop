$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# Remove only obsolete root-level CODE shadows and generated Python/build cache.
$stale = @(
  "ai.py","blocker.py","camera.py","camtest.py","chat.py","chattest.py",
  "config.py","correlations.py","data.py","db.py","difficulty.py","export.py",
  "finance.py","habits.py","journal.py","lifedata.py","memory.py","mic.py",
  "patterns.py","pipeline.py","presence.py","score.py","stats_engine.py",
  "strategist.py","timeutil.py","tracker.py","video_memories.py","voice.py",
  "weekly.py","xp_triggers.py"
)
foreach ($name in $stale) {
  if (Test-Path -LiteralPath $name -PathType Leaf) {
    Write-Host "Removing stale root module: $name"
    Remove-Item -LiteralPath $name -Force
  }
}

# A folder merge on Windows replaces matching files but leaves old runtime files
# behind. Instead of making the person manually delete them every release, move
# any known personal/runtime artifact OUT of the Git checkout before validation.
# We never inspect or print file contents, and especially never open secrets.json.
$runtimeFiles = @(
  "witness.db","witness_data.json","secrets.json","profile.json",
  "import_history.json",".pending_legacy_import.json",".session_active.json",
  "progression.json","conversation.json","xp_triggers.json","xp_triggers_fired.json",
  "ui_settings.json","vision_history.json","trail_history.json","stats_model.json",
  "life_data.json","block_lock.txt"
)
$runtimeDirs = @(
  "recaps","sos_videos","video_memories","day_breakdown_data","insight_data",
  "journals","Backups","crash_reports",".restore_staging",".backup_tmp"
)
$foundRuntime = @()
foreach ($name in $runtimeFiles) { if (Test-Path -LiteralPath $name) { $foundRuntime += $name } }
foreach ($name in $runtimeDirs) { if (Test-Path -LiteralPath $name) { $foundRuntime += $name } }
if ($foundRuntime.Count -gt 0) {
  $base = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "WITNESS\release-quarantine" } else { Join-Path $env:TEMP "WITNESS-release-quarantine" }
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $quarantine = Join-Path $base $stamp
  New-Item -ItemType Directory -Path $quarantine -Force | Out-Null
  foreach ($name in $foundRuntime) {
    Write-Host "Quarantining runtime artifact: $name"
    Move-Item -LiteralPath $name -Destination (Join-Path $quarantine $name) -Force
  }
  Write-Host "Runtime artifacts moved safely to: $quarantine"
}

Get-ChildItem -Path . -Directory -Filter __pycache__ -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch "\\.git(\\|$)" } |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -File -Filter *.pyc -Recurse -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch "\\.git(\\|$)" } |
  Remove-Item -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force build,dist,release -ErrorAction SilentlyContinue

python packaging\validate_source_tree.py
if ($LASTEXITCODE -ne 0) {
  throw "Repository still contains unsafe release artifacts. See validation output above."
}
Write-Host "Repository cleanup complete. Review GitHub Desktop changes before committing."
