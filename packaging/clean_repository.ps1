$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# Remove only obsolete root-level CODE shadows and generated Python/build cache.
# Personal WITNESS data is never deleted here; validation will stop instead.
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
