# WITNESS Windows distribution / updating

## Target user experience

A user downloads **WITNESS-Setup.exe once**, installs it, and launches WITNESS
from the Start menu/desktop. WITNESS checks for a newer stable release shortly
after startup, every 10 minutes while open, and on throttled window re-activation. When a release exists, a compact
**UPDATE vX.Y.Z** button appears in the top bar. **Update & Restart** downloads
the release installer, verifies its published SHA-256 hash, exits WITNESS,
updates only the installed program files, and reopens WITNESS.

Personal history is outside the install directory under the local profile owned
by `profile_runtime.py`, so installer replacement must never include/delete
`%LOCALAPPDATA%\WITNESS`.

As of v7.55 the profile also owns rotating local backups (`Backups/`) and crash reports
(`crash_reports/`). These are user data, not release assets, and must never be copied into
the source repository or installer.

## Distribution pieces

- `packaging/witness.spec` — Windows PyInstaller **onedir** build.
- `packaging/WITNESS.iss` — per-user Inno Setup installer targeting
  `%LOCALAPPDATA%\Programs\WITNESS` with no administrator requirement.
- `release_channel.json` — update-channel metadata. Source builds deliberately
  have a blank repository and therefore do no network update checks.
- `update_manager.py` — checks GitHub Releases, downloads the fixed installer
  asset, validates `WITNESS-Setup.exe.sha256`, then schedules the installer.
- `ui_qt/update_service.py` — moves network/download work off Qt's GUI thread.
- `.github/workflows/release-windows.yml` — on a version tag, uses a Windows
  runner to build/test/package and publish the installer to GitHub Releases.

## One-time release-host setup

The updater needs a publicly readable release endpoint. The provided workflow
uses the repository's own GitHub Releases. For a consumer/no-login build, that
release repository must be public. If the source should remain private, use a
separate public binaries/release repository or another HTTPS host and adapt the
release workflow/update channel; do not embed personal GitHub credentials into
WITNESS.

For the provided same-repository flow:

1. Put the clean WITNESS source in a GitHub repository.
2. Commit the project, including `.github/workflows/release-windows.yml`.
3. Ensure `app_version.VERSION` matches the release you are about to publish.
4. Create/push tag matching `app_version.VERSION` (current release: `v7.58.2`).
5. GitHub Actions builds on Windows and creates a Release containing exactly:
   `WITNESS-Setup.exe` and `WITNESS-Setup.exe.sha256`.
6. Give new users the Setup EXE from the latest published release.

The CI step runs `packaging/prepare_release.py`, which embeds the repository
slug in the packaged copy of `release_channel.json`. Development ZIPs keep the
repository blank so they cannot accidentally self-update.


### v7.58.2 multimedia acceptance check

For Webcam + Mic, record a short spoken/countdown + clap clip and verify mouth/clap sync after the new camera pre-roll/native-cadence correction. Screen + Mic and Screen + Camera + Mic are regression checks and should remain unchanged.

The shared SOS/Daily Recording Studio uses the Qt Multimedia modules already packaged for the intervention video player. History → Calendar → Videos now reuses the same recorder and saves accepted clips directly to the selected day.
Before publishing broadly, the Windows GitHub build should be acceptance-tested with the three local recording
modes (Webcam + Mic, Screen + Mic, Screen + Camera + Mic), including one Square and one Triangle overlay.
This does not add a new network service and does not alter Rapid Screen Guard.

## Release-source hygiene (v7.52.1+)

The first v7.52.0 repository upload accidentally retained old flat/root Python modules
from the pre-reorg project, including a legacy `db.py`. That can shadow `shared/db.py`
during packaging and produce an installed-app startup crash. Before every release:

1. Run `powershell -ExecutionPolicy Bypass -File packaging\clean_repository.ps1` in the
   Git checkout if it has ever contained an older flat WITNESS tree.
2. v7.55+ automatically moves any known stale **runtime/personal leftovers** created by Windows
   folder-merging out of the Git checkout into
   `%LOCALAPPDATA%\WITNESS\release-quarantine\<timestamp>`. It identifies them only by known
   names and never reads their contents. This includes `secrets.json`; it is quarantined, never
   opened. Obsolete flat root code and caches are still removed.
3. Review GitHub Desktop. Runtime leftovers should no longer require manual `Remove-Item`; the
   quarantine lives outside the repository. `core/` and the real local profile are never cleanup
   targets.
4. `python packaging/validate_source_tree.py` must print `WITNESS release source validation OK`.
   Validation still hard-fails if any unsafe artifact remains.
5. Commit the cleanup/version changes, then create the matching version tag.

The GitHub workflow runs that validation again before PyInstaller. It also uses a hardened
frozen smoke test: the GUI process is waited on with a timeout and must write a marker after
the canonical DB/game backend and Qt shell construct successfully. The installer clears only
the old program directory before copying the new onedir build so stale application modules
cannot survive an update; `%LOCALAPPDATA%\WITNESS` personal data is outside that directory.

## Every future WITNESS release

1. Change `app_version.VERSION` / display build tag.
2. Test source normally.
3. Commit.
4. Tag that exact commit `v<app_version.VERSION>` and push the tag.
5. CI produces and publishes the installer. Existing installed users discover
   it automatically; no ZIP replacement is required on their computers.

## Local Windows build (optional)

If a Windows machine needs to build an installer without GitHub Actions, first
put the desired repository slug in `release_channel.json`, install Inno Setup 6,
and run:

`powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1`

The installer and SHA-256 file land in `release\`.

## Important release hardening still pending

- **Code signing:** the first internal builds are unsigned. Windows may warn
  about an unknown publisher. Before broad distribution, sign both the app and
  installer with a trusted Windows code-signing certificate (or move to a
  signed MSIX/Microsoft Store path).
- **Secrets:** API keys are profile-isolated but still plain text today. Move
  them to Windows-protected storage before broad distribution.
- **Remaining Layer-1 migration:** Qt now starts both the active-window tracker and the rapid
  ScreenVision browser guard inside Qt; Windows testing of v7.57.2 reports the drift detector working well. Legacy webcam/presence, phone, open-ended voice/chat and
  pattern-narration runtimes remain separate future product decisions.

## v7.52.2 live updater proof

This patch is intentionally tiny. Publish/tag `v7.52.2` while v7.52.1 remains installed.
Do **not** manually download the v7.52.2 installer for the verification. Launch/restart v7.52.1,
wait for its startup release check, click `UPDATE v7.52.2`, accept Update & Restart, and verify
that WITNESS reopens as v7.52.2 with the same local profile. The updater restart passes `/updated`;
v7.52.2 briefly renders a green `UPDATED TO v7.52.2` badge so success is visually explicit.

A successful test proves: latest-release discovery, version comparison, background download,
published SHA-256 verification, silent program-file replacement, restart, and local-profile
preservation all work together.


## v7.56.1 live update discovery

Installed WITNESS no longer requires a restart simply to notice a release published after the app
was opened. The Qt shell keeps the startup check, polls the stable channel every 10 minutes, and also
requests a throttled check when the main window becomes active after at least 60 seconds since the
last request. `UpdateService` still performs the actual network request in a daemon thread, so this
must not block UI paint/Activity feedback. Discovery only surfaces the update button; installation
continues to require explicit **Update & Restart** confirmation.
