# WITNESS — Dev Log

This file exists so work on this project survives across chat sessions.
The person building this uses AI to write all of it, and each new chat
starts with zero memory of previous ones. This file is the memory.

**⚠️ Before anything else: if `secrets.json` exists in this project,
never read, open, or ask to see its contents.** It holds real API
keys in plain text (Settings > Integrations, see `shared/
secrets_store.py`). Skip it entirely.

## Instructions for whichever AI is reading this

1. Read this whole file, and `ARCHITECTURE.md`, before writing or
   changing anything. Don't skim — the entries below record decisions
   and reasoning that aren't visible in the code itself.
2. Before you end your session (or before the chat is likely to run
   out of room), add a new entry at the **top** of the "Entries" section
   below, using the template provided. This is not optional — it is the
   only reason this system works across sessions. If you do meaningful
   work and don't log it, the next AI (and the person) will have no way
   to know what happened, why, or what's safe to build on.
   Also update `NEXT_CHAT_PROMPT.md`'s "CURRENT FOCUS RIGHT NOW"
   section — that file is what the person pastes into a brand new chat
   to onboard it instantly, so it needs to stay current too, not just
   this log.
3. Explicitly tell the person, in your own final message of the
   session, that you've updated this file (and `NEXT_CHAT_PROMPT.md`)
   — so they know to re-download the project before opening a new chat.
4. When you write your entry, **include this same instruction block**
   (or a clear equivalent) so the next AI knows to keep the chain going.
   Do not let this file stop propagating its own instructions.
5. Never edit or delete a previous entry. This is a log, not a summary
   — if something previous was wrong or got reversed, say so in a new
   entry, don't rewrite history.
6. If you touched `core/` (Layer 1), say so explicitly and say who
   authorized it (quote the request). Core changes should be rare and
   deliberate — flag them clearly so a future session doesn't assume
   core is still exactly as originally built.

### Entry template

```
## YYYY-MM-DD — [short title]
Requested by: [what the person asked for, briefly]
Touched: [files/folders changed]
Did NOT touch: [confirm core/ untouched, unless it was — say so if it was]
What changed and why: [plain description]
Left for next session: [anything incomplete or flagged for later]
```

---

## Entries

## 2026-08-17 -- v7.57.1 restore legacy ScreenVision + auto-start SOS video
Requested by: person tested v7.57.0 and said the modern popup/video UI was good, but protection felt materially slower/different than the old app. They specifically remembered sexual content being detected/shut down very quickly and asked to go back to the old drift settings while keeping the clean modern graphics. They also asked that the SOS video start automatically when the intervention opens rather than requiring a Play click.

Touched:
- `ui_qt/protection_runtime.py`: corrected the v7.57.0 integration omission. Qt now starts the unchanged legacy `ScreenVision` alongside the unchanged `WindowTracker`. Vision events feed the same modern red-line callback/browser shutdown/site-lock path. The existing hard whitelist remains identical to legacy `main.py`. The top-bar status distinguishes `SCREEN GUARD` from `TITLE ONLY` when the Anthropic key/runtime is unavailable.
- `ui_qt/protection_runtime.py`: redesigned intervention remains unchanged visually, but video playback is now armed from `showEvent()` after the native Qt video surface is visible. The first SOS video auto-starts for both real intervention and Settings preview; the remaining control is `NEXT RESET VIDEO`.
- `packaging/requirements-desktop.txt` / `packaging/witness.spec`: added the runtime dependencies required by frozen ScreenVision (`anthropic`, Pillow/ImageGrab, `mss`) and explicit hidden imports.
- `ui_qt/pages.py`: Settings copy now accurately says active-window + screen-vision protection.
- `app_version.py`, `qt_main.py`, `README.md`, `QT_BUILD.md`, `DISTRIBUTION.md`, `ARCHITECTURE.md`, `NEXT_CHAT_PROMPT.md`: advanced/documented v7.57.1 / `2026-08-17-b` and corrected the earlier claim that active-window tracking alone represented the old protection behavior.

Did NOT touch: **no file under `core/` was modified**. The person explicitly authorized going back to the old drift behavior/settings, but the correct fix required only reconnecting the already-existing frozen `core/vision.py`; its timing, adaptive trust logic, prompt and confirmation behavior remain byte-for-byte unchanged. `shared/game_engine.py` and `shared/db.py` are also unchanged. Camera/presence, phone detection, legacy voice/chat and PatternWatcher remain retired.

What changed and why:
v7.57.0 started only `WindowTracker`, which looks at foreground process/title text. That meant explicit red-line titles still shut down immediately, but sexual/suggestive imagery on otherwise ordinary browser pages was no longer being classified from the pixels. In the old full runtime, `ScreenVision` was separately started by `main.py`; it captured the browser screen and asked Claude Vision for FLAG/SAFE. That missing thread explains the person's report that v7.57.0 felt slow and different. v7.57.1 restores that exact old vision engine behind the modern Qt delivery.

Legacy ScreenVision timing preserved exactly: 45-second startup delay; SAFE browser trust scans every 300s, CAUTIOUS every 90s, DANGER every 30s; incognito/private and browsers with 3+ recorded incidents are DANGER; two consecutive FLAG results are required, with the second confirmation scan accelerated to about 10 seconds after the first. Window-title `RED_LINE_KEYWORDS` are still checked by WindowTracker every 5 seconds and do not wait for ScreenVision.

Validation:
- full-project `compileall` passes; AST parse passes for 73 Python files.
- every `core/*.py` file plus `shared/game_engine.py` and `shared/db.py` hash-identical to v7.57.0.
- static package source now includes ScreenVision dependencies/hidden imports. Final screenshot capture, Anthropic network classification, QtMultimedia autoplay and browser taskkill still require the real Windows/GitHub build test.

Left for next session:
Publish/tag `v7.57.1`, update installed WITNESS, and confirm top bar says **PROTECTION · ACTIVE · SCREEN GUARD** (not TITLE ONLY). Leave WITNESS open for >45 seconds before testing because that is the original ScreenVision startup delay. Test only with disposable browser tabs because confirmed red-lines intentionally kill supported browsers. Settings → Preview Intervention should now start the first SOS video automatically. If the person's remembered sub-30-second behavior still does not match, do not blindly shorten `core/vision.py`: first inspect which browser/trust state is being used and whether the older remembered version predates the current adaptive-trust ScreenVision v2.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing; never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were updated before ending the session.

## 2026-08-17 -- v7.57.0 modern drift protection + safe factory reset
Requested by: person explicitly asked to get the backend drift protection back into the modern installed app, specifically the automatic shutdown/browser-close protection and SOS video player, while leaving unnecessary old features retired. They also asked for a Settings factory-reset-style action that returns all scoring/progress to zero. They asked whether the old intervention UI should be redesigned to avoid bringing the old-app feel back; product decision is yes: preserve the proven Layer-1 behavior, redesign only its Qt delivery.

Touched:
- `ui_qt/protection_runtime.py` (new): focused bridge from unchanged `core/tracker.py` queue events into Qt. Starts active-window monitoring while the modern app is open, delivers the existing 0.5/2.5/4.5-minute distraction escalation as modern lightweight drift notices, opens a redesigned intervention at the existing 6.5-minute threshold, and on red-line reuses unchanged `core/nuclear.py` browser termination + `core/blocker.py` 120-minute site-lock attempt. Keeps the old hard whitelist outside core to prevent known safe work/service titles from triggering browser termination. Red-line actions run off the GUI thread. Real activity/flagged/red-line telemetry now feeds the existing DB/Shield path.
- `ui_qt/protection_runtime.py` also owns the new modern intervention/video delivery: dark current-era-compatible Qt surface, top-most hard red-line mode, embedded local SOS playback through QtMultimedia when available, next-video control, explicit RETURN/WALK AWAY action, and graceful no-video fallback. The old Tkinter popup/external-player visual is not reused.
- `ui_qt/shell.py` / `qt_main.py`: start/stop the focused protection runtime with the Qt app, show a top-bar PROTECTION ACTIVE state, route drift/red-line signals to the modern UI, keep smoke tests from starting live protection, and surface post-reset completion.
- `ui_qt/pages.py`: Settings now includes a Protection card (SOS folder + safe preview) and a typed-confirmation Factory Reset Progress danger action.
- `profile_runtime.py`: safe next-launch factory reset. It creates a forced safety backup first, stages a marker, then before `db.init()` on next launch removes scoring/progression/character state and historical telemetry/notes/demo/derived data. It preserves profile identity, `secrets.json`, SOS videos, Backups and active block state. Installed Windows builds schedule a short delayed restart so the reset can apply before SQLite reopens.
- `ui_qt/theme.py`: modern Protection badge styling.
- `packaging/requirements-desktop.txt` / `packaging/witness.spec`: release build now includes psutil + pywin32 for the existing WindowTracker and QtMultimedia for embedded SOS playback.
- `app_version.py`, `qt_main.py`, `README.md`, `QT_BUILD.md`, `DISTRIBUTION.md`, `ARCHITECTURE.md`, `NEXT_CHAT_PROMPT.md`: advanced/documented v7.57.0 / `2026-08-17-a`.

Did NOT touch: **no file under `core/` was modified**. The person authorized bringing drift protection back ("get that backend back into the app specificly drift protection"), but the implementation deliberately integrates the frozen existing core rather than altering its detection/escalation/red-line logic. `shared/game_engine.py` and `shared/db.py` are also unchanged. Camera/presence, phone detection, legacy voice/chat, PatternWatcher and ScreenVision remain retired from the Qt startup.

What changed and why:
The old app had valuable protection semantics but an obsolete visual/delivery layer. v7.57 treats Layer 1 as a service behind the modern product: the backend watches the active Windows process/title and writes real telemetry; Qt owns what the person sees. Normal drift now escalates without reviving the old dashboard, and red-line protection immediately attempts the old browser-close/site-lock behavior while showing a modern intervention with the person's local reset videos. This also restores honest Shield progression in the installed Qt app because clean/flagged monitoring evidence now exists while WITNESS is running. Factory reset is deliberately staged to next launch so an open SQLite database is never deleted in-process.

Validation:
- full-project `compileall` and AST parse pass for 73 Python files.
- isolated two-process factory-reset test passes: database/progression/UI/history removed; `secrets.json`, SOS video and rotating safety backup preserved; reset marker consumed and application result reported.
- release dependency/spec updated for Windows tracker + multimedia. Final frozen Windows runtime behavior (pywin32 active-window observation, actual taskkill, hosts-file permissions, QtMultimedia codecs/top-most behavior) still requires the GitHub Windows build and real-machine test.
- `core/*.py` plus `shared/game_engine.py` and `shared/db.py` are to be hash-compared against v7.56.1 before packaging.

Left for next session:
Publish/tag v7.57.0, let the installed app Update & Restart, and first confirm the top bar says PROTECTION ACTIVE. In Settings use Preview Intervention before intentionally testing drift. Test an ordinary distracting title long enough to verify 3 lightweight escalation notices then the intervention; separately test red-line browser-close behavior only when it is safe to lose open browser tabs. The existing hosts-file lock still requires Windows administrator rights, so browser termination should be treated as the guaranteed automatic action and the dialog must accurately show whether the timed site lock succeeded. Test local MP4 playback from Settings → Open SOS Video Folder. Finally test Factory Reset only after the safety backup is visible; expected restart state is all XP/Levels/records/Character/Core/Shield/history back at zero while integrations/SOS videos/backups remain.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing; never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were updated before ending the session.

## 2026-08-16 -- v7.56.1 3D control feel + live update discovery
Requested by: person tested v7.56.0 on Windows and said the 3D character interaction "honestly feels nice," but both manual drag axes felt inverted and rotation sensitivity was too high/fast for the powerful feel they want. They also reported that a newly published update only became visible after restarting WITNESS.

Touched:
- `ui_qt/character_3d.py`: reversed the v7.56.0 horizontal and vertical drag signs exactly from the Windows feedback, reduced yaw/pitch sensitivity to 0.0045 / 0.0035 radians-per-pixel target movement, and changed direct cursor snapping into target orientation + 16% per-frame easing. Auto Rotate is also slower (0.0032 target yaw/frame). The intent is an immediate but weighty, deliberate inspection feel. Reset now resets both rendered and target orientation.
- `update_manager.py`: update channel config now supports `check_minutes`, with backward-compatible `check_hours` fallback for older channel files.
- `release_channel.json`: stable installed build cadence set to 10 minutes; source repository remains intentionally blank.
- `ui_qt/shell.py`: startup update check remains; periodic release checks now use the minute cadence. A top-level `WindowActivate` event also requests a silent throttled check if at least 60 seconds have elapsed since the previous request, so a release published while WITNESS is already open can surface without restarting. Network work remains in `UpdateService`'s background thread and install still requires explicit Update & Restart.
- `app_version.py`, `qt_main.py`, `QT_BUILD.md`, `README.md`, `DISTRIBUTION.md`, `ARCHITECTURE.md`, `ui_qt/assets/3d/README.md`, `NEXT_CHAT_PROMPT.md`: advanced/documented v7.56.1 / `2026-08-16-g`, recorded that Windows testing positively validated the 3D interaction concept, and preserved the accepted slow-control direction as a production-3D requirement.

Did NOT touch: `core/` in any way; the person did not authorize Layer 1. Also did NOT modify `shared/game_engine.py` or `shared/db.py`; XP, Ghost, records, 8-stage progression, Undo reconciliation, Core/Charge/Shield semantics, themes and profile data remain unchanged.

What changed and why:
v7.56.0 successfully answered the important product question: direct 3D interaction feels good enough to continue. This patch therefore does not add more procedural character features; it tunes the interaction to the person's real Windows feedback and removes an update-discovery annoyance that came from the old six-hour polling interval. The next major 3D work should be production asset quality (rigged identity-consistent character), not ornamenting the placeholder mesh.

Validation:
- full-project `compileall` passes; AST parse passes for 72 Python files.
- static 3D interaction contract checks confirm reversed target signs, reduced sensitivity, eased yaw/pitch and slower Auto Rotate constants are present. Actual perceived direction/weight still requires Windows visual acceptance because PySide6 is not installed in this Linux sandbox.
- `update_manager.channel_config()` returns 10-minute cadence from the new source config and correctly falls back to 360 minutes when given an old `check_hours: 6` fixture. Source channel remains unconfigured (`repository: ""`).
- `packaging/validate_source_tree.py` passes.
- every `core/*.py` file plus `shared/game_engine.py` and `shared/db.py` remains hash-identical to v7.56.0.

Left for next session:
Publish/tag v7.56.1 and test the four drag directions + long slow rotations on Windows. The interaction should feel natural and more deliberate. For update discovery, a future tiny release can be published while WITNESS stays open: wait up to ~10 minutes or switch away/back after >60 seconds; the UPDATE button should appear without restarting. Since 3D interaction is now positively validated, the next major Character project is a production-quality rigged model/renderer while keeping the approved Portrait art as the high-fidelity fallback.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing; never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were updated before ending the session.

## 2026-08-16 -- v7.56.0 Theme Evolution + Interactive 3D Lab
Requested by: person liked the new dark/modern Character direction and asked whether the entire WITNESS UI could mature with the character (jungle early, increasingly structured/modern later). They also explicitly asked to use remaining pre-Monday time to try a real interactive 3D character rather than stopping at the 2.5D composite artwork.

Touched:
- `ui_qt/theme.py`: replaced the single static visual skin with a presentation-only three-era system tied to the canonical current Level: Levels 1-2 **WILD ERA** (deep jungle blacks/moss/soft radii), Levels 3-4 **FORGED ERA** (stone-charcoal/bronze/tighter structure), Levels 5-8 **NOIR ERA** (sleek near-black/steel/quiet gold/minimal radii). Semantic green/red/gold meaning is still preserved.
- `ui_qt/shell.py`: reads canonical `game_engine.level_status()` only to choose the visual era, shows the current era in the top bar, and reapplies QSS only when the broad era changes. Arena actions can trigger a lightweight next-turn theme sync; hidden pages are still never synchronously rebuilt.
- `ui_qt/character_3d.py` (new): dependency-free procedural 3D humanoid prototype using actual 3D mesh geometry, perspective projection, depth sorting and user rotation rendered through QPainter. Drag rotates 360 degrees, wheel zooms, double-click resets, optional Auto Rotate animates, Core Reserve controls an actual chest-space glow, Daily Charge adds an outer field, and stage styling progresses from barefoot/wild to tight tactical/tailored/Sovereign silhouettes. This is explicitly a prototype mesh, not a claim that the approved composite art has become a final rigged 3D model.
- `ui_qt/character_page.py`: Character now has **PORTRAIT | 3D LAB** modes. The approved original art remains the default/high-fidelity presentation; 3D Lab follows the same selected current/memory stage and state, so it can be judged inside the real app without replacing the art. Journey buttons now inherit the active era instead of hard-coding the older green card skin.
- `ui_qt/assets/3d/README.md`: documents the production rig/GLB contract if the interactive prototype earns a real 3D asset pass later.
- `app_version.py`, `qt_main.py`, `QT_BUILD.md`, `README.md`, `ARCHITECTURE.md`, `CHARACTER_ART.md`, `NEXT_CHAT_PROMPT.md`: advanced/documented v7.56.0 / `2026-08-16-f`.

Did NOT touch: `core/` in any way; the person did not authorize Layer 1. Also did NOT modify `shared/game_engine.py` or `shared/db.py`; XP, Ghost, records, the 8-stage Level ladder, Undo reconciliation, Core/Shield semantics and release/update pipeline remain canonical and unchanged.

What changed and why:
The previous product had a strong cinematic Character page but the surrounding app still read as one static green productivity skin. v7.56 makes the UI itself participate in progression without turning eight levels into eight unrelated themes. The three broad eras preserve usability while making advancement visible beyond the avatar. The 3D work is deliberately isolated as an in-app lab because a polished production character requires a rigged identity-consistent asset; the procedural renderer proves interaction/performance/feel first and introduces no new graphics dependency or packaging risk.

Validation:
- full Python `compileall` passes; theme era mapping/stylesheet generation tested for all Levels 1-8; final source-tree validator passes.
- final archive AST audit passes.
- `core/*.py`, `shared/game_engine.py`, and `shared/db.py` hashes are unchanged from v7.55.2.
- PySide6 is not installed in this Linux sandbox, so the definitive 3D visual/performance acceptance test is the Windows installed build.

Left for next session:
Publish/tag v7.56.0, let the proven updater install it, then judge three things on Windows before doing more: (1) whether WILD/FORGED/NOIR feels cohesive across Arena/History/Character rather than gimmicky, (2) whether 3D Lab rotation/zoom/idle stays smooth, and (3) whether the procedural mesh interaction is compelling enough to justify commissioning/generating one production rigged GLB character with outfit variants. Do **not** replace the approved portrait artwork merely because the prototype is 3D. If the lab feels crude but interaction is good, keep Portrait as default and upgrade the mesh asset later.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing; never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were updated before ending the session.

## 2026-08-16 -- v7.55.2 self-cleaning GitHub release build fix
Requested by: person reported that both v7.55.0/v7.55.1 GitHub Actions failed at `Validate clean release source`. GitHub's checkout log showed the tagged SHA `5b3270e`, and GitHub Desktop History showed that same commit contained the expected 28 root-module deletions. Person asked whether we could make a new file and redo it, noting they may originally have committed before running PowerShell.

Touched:
- `.github/workflows/release-windows.yml`: replaced the pre-clean hard-fail-only validation step with a GitHub-runner cleanup + validation step. Immediately after checkout/setup Python, the Windows job now runs `packaging/clean_repository.ps1`; that script removes documented obsolete root shadows, quarantines only known runtime artifact names, clears generated caches/build output, and validates the resulting source tree before `prepare_release.py` or PyInstaller can run. This makes release correctness independent of whether local cleanup happened before or after an earlier commit.
- `app_version.py`, `qt_main.py`, `QT_BUILD.md`, `README.md`, `DISTRIBUTION.md`, `ARCHITECTURE.md`, `NEXT_CHAT_PROMPT.md`: advanced/documented v7.55.2 / `2026-08-16-e` as a release reliability fix on top of the v7.55 Completion Pass.

Did NOT touch: `core/` in any way; no Layer-1 authorization was given. Also did NOT modify `shared/game_engine.py`, `shared/db.py`, Character mechanics, Core/Reserve semantics, onboarding, backup/restore behavior, updater behavior, or the eight-stage progression thresholds.

What changed and why:
The failed Actions run proved that relying on the tagged repository tree being pristine was too brittle for this Windows copy/merge workflow. Although the exact reason GitHub's validator saw stale root modules despite checking out the deletion SHA was not conclusively established, the build does not need to depend on that mystery. v7.55.2 makes the ephemeral CI checkout self-cleaning using the already-audited cleanup script, then validates it. Local cleanup is still recommended to keep Git history tidy, but a mistaken commit-before-cleanup ordering can no longer block the installer build by itself.

Validation:
- `python packaging/validate_source_tree.py` passes on the packaged v7.55.2 source.
- Full Python AST/compile validation passes.
- Final ZIP audit confirms no forbidden personal/runtime artifacts or `secrets.json` are included.
- Protected `core/*.py`, `shared/game_engine.py`, and `shared/db.py` are hash-identical to the v7.55.0 source used for this fix.
- PowerShell/GitHub-hosted Windows execution cannot be run in this Linux sandbox; the definitive acceptance test is one v7.55.2 tag run on GitHub Actions.

Left for next session:
Publish the fresh v7.55.2 source, commit/push it, create/push tag exactly `v7.55.2`, and confirm Actions gets past **Clean and validate release source** into dependency install/PyInstaller. Do not reuse failed v7.55.0/v7.55.1 tags. Once green, use the installed app's Update & Restart and then perform the v7.55 Core/Signature/Data Safety acceptance test. If the CI cleanup step itself fails, capture that exact step log before making another tag.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing; never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were updated before ending the session.

## 2026-08-16 -- v7.55.0 Completion Pass: Core Reserve, data safety, onboarding + release quarantine
Requested by: person approved building the remaining V1 completion ideas together after v7.54
looked good: finish the Character payoff, add Core/Reserve + Shield separation, make behavior
attributes more visible, keep reward sound restrained, permanently fix the repetitive release
cleanup, add real local backup/export/restore/crash safety, add new-user onboarding, and then stop
expanding scope so WITNESS can be used rather than endlessly rebuilt.

Touched:
- `shared/character_engine.py`: added an explicit user-controlled 14-day Core Reserve clock
  (`SPARK / AWAKE / BUILDING / STEADY / VIBRANT`) stored in existing `game_state`. Start/Reset
  never awards XP or changes Level, Daily Charge, unlocked forms or Protection Shield. Character
  snapshot now exposes optional local name/mission and sorts evidence-backed Attributes
  strongest-first with one current Signature.
- `ui_qt/character_page.py`: separated state visually: Daily Charge now drives a restrained outer
  green aura; Core Reserve drives the inner gold chest light. Added Core Reserve card + Start/Reset
  confirmation, Signature display, shield-shaped field refinement and a short dark/gold-ring
  EVOLUTION reveal only when the live canonical form actually changes. Existing art/parallax/
  fog/rain/cross-fades remain 2.5D and presentation-only.
- `ui_qt/assets/sounds/core.wav`, `ui_qt/audio.py`: tiny low-amplitude Core cue after explicit
  Start/Reset only. No passive timer/Reserve/Shield event is allowed to make sound.
- `ui_qt/onboarding.py` (new), `ui_qt/shell.py`: local-only first-run 3-step setup (optional
  name/mission, editable starter Activities+XP, short Ghost/Level explanation). Existing accounts
  with any previously configured Activity are not forced through it. Shell also surfaces a local
  recovery notice after an unclean prior session.
- `profile_runtime.py`: added transaction-consistent SQLite snapshots, up to 7 rotating compact
  backups, 12-hour startup rate limit, forced crash-recovery backup on an unclean prior session,
  full profile Export (including media when requested), safe staged next-launch Restore, session
  marker, local crash reports and backup-folder helpers. Backups/exports/restores deliberately
  exclude `secrets.json`. Restore is staged and applied before SQLite opens; it never swaps an open
  database.
- `qt_main.py`: installs a local uncaught-Python crash reporter and clean-session marker lifecycle
  around the Qt event loop.
- `ui_qt/pages.py`: Settings gained DATA SAFETY (Create Backup, Export Profile, Restore Backup,
  Open Backups) plus a rerunnable GETTING STARTED guide. Existing Local Profile, Sound, Demo and
  Activity controls remain.
- `packaging/clean_repository.ps1`: fixes the repeated Windows folder-merge problem. Known runtime/
  personal leftovers in the Git checkout are now moved by filename to
  `%LOCALAPPDATA%\WITNESS\release-quarantine\<timestamp>` before validation instead of requiring
  manual `Remove-Item`. Contents are never inspected; `secrets.json` is identified only by name
  and never opened. Obsolete root code/cache cleanup remains.
- `packaging/validate_source_tree.py`, `.gitignore`: expanded hard-fail/runtime exclusions for
  backup, crash, restore/session and historical personal-data artifacts.
- `app_version.py`, `qt_main.py`, `ARCHITECTURE.md`, `CHARACTER_ART.md`, `QT_BUILD.md`, `README.md`,
  `DISTRIBUTION.md`, `NEXT_CHAT_PROMPT.md`: advanced/documented v7.55.0 / `2026-08-16-d`.

Did NOT touch: `core/` in any way; the person did not authorize Layer 1. Every `core/*.py` hash
remains unchanged from the v7.54 baseline. Also did NOT modify `shared/game_engine.py` or
`shared/db.py`; canonical XP, Activity values, Ghost, records, eight-stage level thresholds, Undo
reconciliation, demotion grace/comeback, SQLite scoring schema and updater/hash/install architecture
are unchanged. No fitness/watch, cloud account, true 3D or fake Shield telemetry was added.

What changed and why:
The app already had a strong daily fight and visual evolution, but several product-completion
pieces were still conceptual. v7.55 makes the four character states explicit: Level/form is
long-term evolution; Daily Charge is today's output; Core Reserve is a separate user-defined
current-state clock; Shield is observed protection discipline. The same pass makes personal data
less fragile and first launch more intentional. Release cleanup now solves the exact repetitive
manual problem observed across v7.53/v7.54 without deleting unknown files or reading secrets.

Validation:
- Full-project `compileall` passes before final cleanup; final AST/compile validation is rerun on
  the packaged source.
- Isolated Core test: inactive -> Start at t=1000 -> 7 days = 50%/STEADY -> Reset = 0% with reset
  count incremented.
- Isolated real SQLite test created a canonical Activity/XP event, created a rotating backup and
  full export, verified both include a DB snapshot and neither contains `secrets.json`, then safely
  staged the backup for next-launch restore.
- Two-process crash test left a session marker intentionally; the next activation reported an
  unclean shutdown and forced a crash-recovery backup before DB open.
- Protected hashes: all `core/*.py` files, `shared/game_engine.py` and `shared/db.py` match the
  v7.54 pre-pass SHA-256 baselines exactly.
- PySide6 and PowerShell are not installed in this Linux sandbox, so actual Qt visuals/onboarding
  and the new quarantine script must receive one real Windows acceptance test before being called
  fully proven.

Left for next session:
Publish/tag v7.55.0 through the proven GitHub updater path. Windows acceptance should test Core
Start/Reset + Charge-vs-Core visuals, evolution reveal/Signature, Data Safety, first-run onboarding
(if an isolated fresh profile is practical), no random idle sound, and most importantly that
`clean_repository.ps1` automatically quarantines the familiar stale runtime leftovers instead of
requiring manual deletion. After that passes, freeze major feature scope and use WITNESS; fight
only concrete bugs/friction. Full Qt Layer-1 runtime integration, Windows code signing and protected
secret storage remain separate future engineering work.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing;
never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes
Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were
updated before ending the session.

## 2026-08-16 -- v7.54.0 eight-stage canonical ladder + Character Alive V2 + undo correction
Requested by: person tested the v7.53 Character art build, confirmed the first five forms looked/
worked well, noticed the old canonical app still stopped at Level 5 with old names, asked to build
the full eight-stage progression + animation pass, and reported a concrete bug: after spamming a
test Activity to watch upgrades and then undoing it, WITNESS stayed at Level 5.

Touched:
- `shared/game_engine.py`: canonical rolling ladder now maps one-for-one to the approved Character
  story: Wanderer 0, Seeker 5,000, Apprentice 12,800, Builder 24,100, Disciplined Man 39,200,
  Operator 55,000, Elite 75,000, Sovereign 100,000. The original first-five thresholds, 14-day
  exp(-0.10*d) rating, 85% demotion floor, 48h At-Risk grace, comeback multiplier, battle XP,
  Ghost and records remain unchanged. Added one-time ladder-state reconciliation for upgrades.
- `shared/game_engine.py`: explicit manual Undo/reversal now reconciles derived current + historical
  peak level immediately from the corrected immutable XP ledger. Undo is a correction, not weak
  performance, so false/test promotions no longer linger through the normal 48-hour demotion grace.
  Normal decay still keeps that grace. Progression display filters old persisted promotion/reclaim
  dots if the corrected ledger no longer supports the tier on that day.
- `shared/character_engine.py`: current form follows current canonical level; Journey unlocks follow
  historical peak level. The peak-rating value is a derived cache rather than an irreversible
  currency and is allowed to reconcile downward after Undo. Stage names/thresholds are forced from
  `game_engine.LEVELS` so Character and game ladder cannot silently drift apart again.
- `ui_qt/character_page.py`: Character Alive V2 keeps the approved composite art but adds restrained
  living-portrait motion: smooth pointer parallax, drag pan, small inspect zoom, tiny breathing/
  camera drift, drifting jungle fog + fireflies, city haze + rain, charge-responsive Core pulse,
  existing Shield field, and smooth cross-fades between forms. This is still 2.5D presentation,
  not fake 360-degree 3D.
- `ui_qt/widgets.py`: small Arena rank emblem now has eight ring segments and defaults to Wanderer.
- `ui_qt/arena.py`: top-tier copy now says Sovereign tier.
- `app_version.py`, `qt_main.py`, `ARCHITECTURE.md`, `CHARACTER_ART.md`, `QT_BUILD.md`, `README.md`,
  `DISTRIBUTION.md`, `NEXT_CHAT_PROMPT.md`: advanced/documented v7.54.0 / `2026-08-16-c`.

Did NOT touch: `core/` in any way; the person did not authorize Layer 1. Also did not modify
`shared/db.py`, Activity configured XP, Ghost calculations, records, SQLite schema, updater/hash/
installer logic, local-profile isolation, fitness integration, or the future Reserve timer.

What changed and why:
The v7.53 art journey had eight visual chapters but the canonical game still exposed only five old
rank names, creating an obvious product mismatch. The new ladder makes level and character language
identical. The reported stuck-Level-5 case was traced to two deliberate old behaviors interacting
poorly with test corrections: level demotion had a 48-hour grace and Character peak unlocks were
sticky. That behavior is sensible for real performance decay but wrong for Undo, because Undo says
that XP should never have counted. v7.54 preserves the normal grace while giving explicit ledger
corrections an immediate reconciliation path.

Validation:
- Full-project `compileall` passes.
- Isolated exact-threshold test confirms all 8 levels map to the intended names/thresholds.
- Isolated test Activity: +60,000 -> Operator; +60,000 again -> Sovereign; first Undo immediately
  returns to Operator/peak 6; second Undo immediately returns to Wanderer/peak 1. Character current
  form/unlocked memories reconcile with the corrected ledger and false milestones disappear.
- Simulated old v7.53 stale state (`current_level=5`, `peak_level=5`, zero corrected XP) self-heals
  to Level 1 Wanderer on first v7.54 ladder migration.
- Separate regression confirms ordinary below-floor performance still enters At-Risk with the full
  48-hour grace instead of immediately demoting.
- PySide6 is not installed in this Linux sandbox, so the new parallax/breathing/fog/cross-fade
  smoothness must be judged on the person's Windows installed build.

Left for next session:
Publish/tag v7.54.0 through the proven GitHub updater path. On Windows verify the previously stuck
level self-heals, then spam/undo a test Activity across levels 1-8 and inspect Character motion at
real display scaling. If motion feels too strong/too subtle, tune only the observed effect. Do not
jump to true 3D yet unless the living portrait still fails to create attachment. Reserve/Core timer,
independent environments, fitness integration and full Qt Layer-1 runtime migration remain later.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing;
never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes
Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were
updated before ending the session.

## 2026-08-16 -- v7.53.0 Character Art Progression V1: approved 8-form journey
Requested by: person completed the Character concept-art progression, explicitly preferred the
original fuller/healthier character set over later regenerated wirey/bonier versions, uploaded
the eight approved images in order, and asked to start putting that evolution into WITNESS.

Touched:
- `ui_qt/assets/character/` (new): bundled the approved full-resolution original art for
  Wanderer, Seeker, Apprentice, Builder, Disciplined Man, revised agile Operator, Elite and
  Sovereign.
- `CHARACTER_ART.md` (new): V1 art bible documenting identity continuity, the eight approved
  forms/worlds, Core/Charge/Shield meaning, world progression, motion rules and the explicit
  rejection of the later gaunt/wirey regeneration direction.
- `shared/character_engine.py`: added a downstream visual-evolution projection from the same
  canonical rolling Level Rating. Forms use permanent peak-rating milestones at 0 / 5,000 /
  12,800 / 24,100 / 39,200 / 55,000 / 75,000 / 100,000. The first five align with existing
  canonical game-level thresholds; forms 6-8 extend the same Rating curve beyond the current
  top V1 game level. This does NOT award XP, alter Ghost/records, or rewrite level math. Real
  peak visual progress is persisted only as an unlock; synthetic demo mode never permanently
  unlocks real-account forms. Full Character-page entry can reconcile old history from
  `game_engine.progression_snapshot()`, while the 2-second live path stays cheap.
- `ui_qt/character_page.py`: replaced the placeholder vector avatar with an image-led 2.5D
  Character scene. The approved art fills the main frame; drag pans/inspects, wheel zooms,
  double-click resets view, early chapters get subtle fireflies, city chapters restrained rain,
  today's existing Charge softly pulses the Core, and earned Shield state draws a subtle field.
  Added an 8-form Journey strip. Earned earlier forms can be revisited as memories; demo mode can
  preview all art for testing. Composite art is deliberately treated as stage/world chapters,
  not fake swappable environments, because body and background are currently one image.
- `packaging/witness.spec`: now explicitly bundles `ui_qt/assets/character/*.png` in frozen
  Windows builds.
- `app_version.py`, `qt_main.py`, `ARCHITECTURE.md`, `QT_BUILD.md`, `README.md`,
  `DISTRIBUTION.md`, `NEXT_CHAT_PROMPT.md`: advanced release/build docs to v7.53.0 /
  `2026-08-16-b` and recorded the new Character contract.

Did NOT touch: `core/` in any way; person did not authorize Layer 1. Also did not modify
canonical `shared/game_engine.py`, canonical `shared/db.py`, Activity XP, Ghost math, records,
rolling-level thresholds/decay/demotion rules, updater/hash/install logic, profile isolation, or
fitness integration. Protected-file hash comparison against v7.52.2 confirms all `core/*.py`,
`shared/game_engine.py` and `shared/db.py` remain byte-for-byte unchanged.

What changed and why:
The previous Character foundation proved interaction/state but its asset-free vector body was not
emotionally strong enough. The person designed a coherent visual story from wilderness to earned
authority and supplied the exact approved art. V1 now makes that art the hero while preserving the
backend boundary: real-life scoring produces canonical Level Rating; Character only projects that
history into a permanent form and current-state effects. Because the approved images are composite
character+environment scenes, V1 uses them honestly as chapters. Independent environment swapping
should wait for separated layers/3D models instead of showing an old body and calling it a new
environment.

Validation:
- Pure evolution boundary test: ratings 0/5,000/12,800/24,100/39,200/55,000/75,000/100,000 map
  to Wanderer/Seeker/Apprentice/Builder/Disciplined Man/Operator/Elite/Sovereign as intended.
- Empty-profile `character_engine.snapshot()` returns Wanderer cleanly without touching score.
- Character and packaging Python compile/AST checks pass.
- Protected canonical/core hash check vs v7.52.2: unchanged.
- Release source validator passes after cache cleanup; no DB, secrets, demo history or personal
  runtime data are included.
- PySide6 is not available in this Linux sandbox, so final visual sizing/pan/particle smoothness
  must be judged on the person's Windows install after publishing v7.53.0.

Left for next session:
Publish v7.53.0 through the now-proven GitHub pipeline, then let installed v7.52.2 discover it via
Update & Restart. On Windows, open CHARACTER and judge: full-frame art crop/quality, 8-form journey
strip at the person's screen size, Core pulse subtlety, Shield field, fireflies/rain, and demo-mode
preview. If the visual page feels right, do not reopen character art direction immediately; the
next meaningful product phase is either Reserve/Core behavior or full Qt Layer-1 runtime
integration. Independent swappable environments and true 3D remain later asset/runtime work.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing;
never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes
Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were
updated before ending the session.

## 2026-08-16 -- v7.52.2 updater end-to-end verification release
Requested by: person successfully installed the corrected v7.52.1 Windows desktop build and
asked to prove the remaining distribution promise: future versions should be discovered and
installed from inside WITNESS without manually downloading another installer.

Touched:
- `app_version.py`: patch version -> `7.52.2`, build tag `2026-08-16-a`, release name
  `Updater End-to-End Test`.
- `qt_main.py`: build/doc label updated to v7.52.2.
- `ui_qt/shell.py`: when WITNESS is relaunched by its updater with the existing `/updated`
  argument, the top bar briefly shows `✓ UPDATED TO v7.52.2` for 12 seconds. This is delivery
  feedback only; it does not touch score, profile data, or runtime state. Normal direct launches
  do not show the badge.
- `ARCHITECTURE.md`, `DISTRIBUTION.md`, `QT_BUILD.md`, `README.md`, `NEXT_CHAT_PROMPT.md`:
  documented the live updater verification step and expected publish/test flow.

Did NOT touch: `core/`; canonical `shared/game_engine.py`; canonical `shared/db.py`; Character
rules; Ghost/records/rolling levels; local-profile isolation; installer/updater download/hash
logic; or Qt responsiveness architecture.

What changed and why:
v7.52.1 proved the corrected packaged app can install and launch. v7.52.2 is intentionally a
minimal patch whose purpose is to prove the updater itself end-to-end. After GitHub publishes
`v7.52.2`, installed v7.52.1 should discover it on the normal startup check, expose
`UPDATE v7.52.2`, download the GitHub Release installer + SHA-256, exit, install over program
files only, and restart with the same `%LOCALAPPDATA%\WITNESS` profile. The temporary `/updated`
badge gives an unambiguous visual success signal after the automatic restart.

Validation:
- Source-tree release validator passes on the clean package.
- All Python files AST-parse successfully.
- `update_manager.is_newer("7.52.2", "7.52.1")` returns True.
- Release preparation accepts exact tag `v7.52.2` and embeds a repository slug only in a
  temporary test copy; checked-in/source `release_channel.json` remains blank by design.
- No database, secrets, profile, demo history, caches, build output or personal runtime data are
  included.

Left for next session:
Copy this source over the clean GitHub checkout, commit/push, tag exactly `v7.52.2`, wait for
the hardened Windows Action to turn green, then leave installed v7.52.1 in place and verify the
in-app `UPDATE v7.52.2` flow. Do NOT manually download v7.52.2 for the test. If the button does
not appear after startup, diagnose release/latest-channel visibility before changing updater
architecture. If download/install/restart fails, capture the exact UI error and GitHub release
assets. If it succeeds, desktop distribution/updating can be considered proven and work can
return to final Character/runtime/product polish.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing;
never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes
Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were
updated before ending the session.

## 2026-08-15 -- v7.52.1 Desktop Packaging Hotfix: stale-module guard + real frozen smoke test
Requested by: person successfully published the first `v7.52.0` Windows installer through
GitHub Actions, installed it, and immediately got an unhandled startup exception:
`AttributeError: module 'db' has no attribute 'game_state_get'` from
`game_engine.initialize()`. They need the installed-app/update path to be trustworthy before
using WITNESS as the normal daily app.

Touched:
- `app_version.py`: patch version -> `7.52.1`, display `v7.52.1`, Qt build
  `2026-08-15-f`, release name `Desktop Packaging Hotfix`.
- `.gitignore` (new): ignores Python caches/build outputs and all known local WITNESS
  runtime/personal-data artifacts (`witness.db`, `secrets.json`, profile/history folders, etc.)
  so they cannot accidentally enter a release checkout.
- `packaging/validate_source_tree.py` (new): hard release gate. Fails if obsolete pre-reorg
  root modules (`db.py`, `data.py`, `config.py`, tracker/core duplicates, archived duplicates,
  etc.), Python caches, or personal runtime files exist in the source root. Also verifies
  canonical `shared/db.py` exposes the DB API the game backend requires.
- `packaging/clean_repository.ps1` (new): Windows cleanup helper for the person's existing
  Git checkout. Removes ONLY known obsolete root-level code shadows plus Python/build caches;
  it does not delete personal WITNESS data. It then runs the validator and stops if unsafe
  artifacts remain.
- `packaging/witness.spec`: PyInstaller search precedence now mirrors the runtime section
  precedence and keeps project root last. Canonical `shared/`, `character/`, `core/`, etc.
  can no longer be silently outranked by an accidental legacy file at repository root.
- `qt_main.py`: adds an explicit canonical DB API contract check before `db.init()` /
  `game_engine.initialize()` so a wrong `db` import gives a direct packaging diagnostic.
  The `--smoke-test` path now writes `WITNESS_SMOKE_MARKER` only AFTER DB/game initialization
  and the real Qt shell construct successfully.
- `.github/workflows/release-windows.yml`: runs source-tree validation before packaging.
  Replaced the weak GUI-EXE smoke invocation with `Start-Process`, a 30-second wait/timeout,
  exit-code check, and required smoke-marker check. This prevents a GUI-subsystem launch from
  appearing green when startup actually died before the real shell was reached.
- `packaging/build_windows.ps1`: same source validation and hardened wait/marker smoke test for
  local Windows packaging.
- `packaging/WITNESS.iss`: before copying a new onedir build, deletes the OLD PROGRAM DIRECTORY
  contents under `%LOCALAPPDATA%\\Programs\\WITNESS`. This is safe because v7.51 moved all
  personal state to `%LOCALAPPDATA%\\WITNESS`; it prevents stale app modules from surviving an
  update/install. It does not touch the personal profile.
- `ARCHITECTURE.md`, `DISTRIBUTION.md`, `QT_BUILD.md`, `README.md`, `NEXT_CHAT_PROMPT.md`:
  documented the incident, repository hygiene invariant, stronger smoke test, install cleanup,
  patch release process, and exact next Windows/GitHub steps.

Did NOT touch: `core/` in any way; every `core/*.py` SHA-256 remains byte-for-byte identical
to v7.52. Also did not modify canonical scoring/Ghost/records/rolling-level rules in
`shared/game_engine.py`, canonical DB behavior in `shared/db.py`, Character rules, profile
isolation, History/Progression math, Activities, or Qt responsiveness/game delivery behavior.

What changed and why:
The first real GitHub repository screenshot revealed old flat/root modules still present even
though the clean v7.52 source package had already moved those modules into section folders.
In particular the old root `db.py` is the pre-game schema and does not provide
`game_state_get`; the installed exception is exactly what happens when that module wins over
canonical `shared/db.py`. The old release workflow's smoke step was also insufficient for a
windowed GUI executable: it only launched the EXE and checked `$LASTEXITCODE`, so the Action
could turn green without proving the application reached its backend + Qt shell. v7.52.1
fixes BOTH the contamination path and the false-positive test path rather than papering over
`game_engine.initialize()`.

The program/profile separation from v7.51 is what makes aggressive program-directory cleanup
safe: installed code is disposable; user XP/history/videos/settings remain outside it. This
hotfix is a delivery-only correction, not a game-engine change.

Validation:
- Python AST parse: 70 Python files, 0 parse errors after hotfix edits.
- `packaging/validate_source_tree.py` passes on the clean source after caches are removed and
  intentionally fails when a dummy legacy root shadow is introduced.
- Canonical DB API tokens required at startup are present in `shared/db.py`.
- Version/tag preparation is set for `7.52.1` / `v7.52.1`.
- `core/*.py`, `shared/game_engine.py`, and `shared/db.py` hashes match v7.52 exactly.
- Linux cannot execute the final Windows GUI binary. The real proof is the next GitHub
  `v7.52.1` Action: the hardened marker smoke test must turn green, then the person installs
  the new Setup once manually because broken v7.52.0 cannot launch its updater.

Left for next session:
The person should copy this v7.52.1 source into the existing `witness-desktop` Git checkout,
run `powershell -ExecutionPolicy Bypass -File packaging\\clean_repository.ps1`, review GitHub
Desktop deletions (old root duplicates), commit/push, tag **`v7.52.1`**, and wait for the Action.
If the Action is green, download/install that Setup manually over v7.52.0 and verify WITNESS
opens. After this one hotfix install, future working versions should use WITNESS's own
**Update & Restart** flow. If the hardened Action fails, diagnose the exact failed step rather
than weakening validation/smoke tests.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing;
never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes
Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were
updated before ending the session.

## 2026-08-15 -- v7.52 Desktop Distribution Foundation: Windows installer + one-click update pipeline
Requested by: person wants to stop downloading/replacing a ZIP for every future WITNESS
revision. They asked how a brand-new user can download WITNESS once as a normal desktop app
and then receive later improvements without manually reinstalling the project each time.

Touched:
- `app_version.py` (new): one release-version source of truth. Current version is `7.52.0`,
  display `v7.52`, Qt build tag `2026-08-15-e`.
- `release_channel.json` (new): stable update-channel metadata. In the checked-in/source ZIP,
  `repository` is intentionally blank, so development copies do not phone home or accidentally
  self-update from an arbitrary repository. The Windows release job writes the real repository
  slug into the packaged copy immediately before building.
- `update_manager.py` (new, standard library only): reads the packaged channel, queries the
  configured public GitHub repository's latest stable Release, compares numeric version tags,
  requires fixed release assets `WITNESS-Setup.exe` + `WITNESS-Setup.exe.sha256`, downloads the
  installer into a temporary WITNESS Updates folder, streams SHA-256 verification, and only
  schedules install after integrity verification succeeds. `launch_update_and_restart()` writes
  a temporary helper CMD that waits for the current process to exit, runs Inno Setup in silent
  per-user update mode, and reopens `%LOCALAPPDATA%\Programs\WITNESS\WITNESS.exe` on success.
- `ui_qt/update_service.py` (new): Qt signal/thread bridge. Release checks and installer downloads
  happen in daemon worker threads, never on the GUI thread.
- `ui_qt/shell.py`: build title now reads version/build from `app_version.py`; added a hidden
  top-bar Update button. Source builds see nothing. A packaged build checks ~3.5s after launch
  and every configured 6 hours; only a newer complete stable release surfaces `UPDATE vX.Y.Z`.
  Clicking it asks for explicit **Update & Restart**, shows download percentage, then exits after
  scheduling the verified installer. There is intentionally no surprise background install.
  v7.48 responsiveness rule is preserved: network/download I/O never blocks Arena paint/events.
- `qt_main.py`: frozen builds now treat `sys.executable`'s directory as the application/program
  directory while the existing v7.51 local profile still owns data. Added `--smoke-test` for the
  Windows CI release job: constructs the real Qt shell/backend offscreen and exits quickly.
- `packaging/witness.spec` (new): PyInstaller **onedir** build of the current Qt entry point,
  including the release-channel file and WITNESS sound assets. Onedir is deliberate: Inno Setup
  owns installation/updating and startup need not unpack a onefile bundle every run.
- `packaging/WITNESS.iss` (new): no-admin per-Windows-user installer under
  `%LOCALAPPDATA%\Programs\WITNESS`; fixed program location, Start-menu shortcut and desktop
  shortcut task, uninstall entry, application-close support for upgrades. It never installs into
  or deletes the separate `%LOCALAPPDATA%\WITNESS` profile folder.
- `packaging/requirements-desktop.txt`, `packaging/prepare_release.py`,
  `packaging/build_windows.ps1` (new): reproducible desktop-build dependencies, tag/version +
  release-repository preparation, and an optional local Windows builder producing Setup + hash.
- `.github/workflows/release-windows.yml` (new): canonical automated publisher. A pushed `v*`
  tag must exactly match `app_version.VERSION`; GitHub's Windows runner embeds `${github.repository}`
  into the packaged update channel, builds with PyInstaller, smoke-tests the frozen EXE in an
  isolated temp profile with Qt offscreen, installs Inno Setup, creates `WITNESS-Setup.exe`, writes
  the SHA-256 sidecar, and publishes both as a GitHub Release via `gh release create`.
- `DISTRIBUTION.md` (new): target end-user flow, one-time public release-host requirement, future
  release procedure, local Windows build option, and explicit pending hardening.
- `README.md`, `ARCHITECTURE.md`, `QT_BUILD.md`, `NEXT_CHAT_PROMPT.md`: documented the installed
  program/profile separation, updater contract, release workflow, source-build no-network rule,
  current limitations, and the true next step.

Did NOT touch: `core/` in any way. Every `core/*.py` SHA-256 remains byte-for-byte identical to
v7.51. The person did not authorize Layer-1 changes. Also did not alter canonical scoring/Ghost/
records/rolling-level math in `shared/game_engine.py`, Character projection rules, Activity
ledger semantics, History/Progression calculations, or v7.51 profile isolation. Packaging the
Qt shell also does NOT imply full runtime parity: `qt_main.py` still does not start the complete
Layer-1 tracker/voice/intervention runtime; legacy `main.py` remains the full-runtime reference.

What changed and why:
The v7.51 data boundary made in-place program updates safe, but there was still no product
release mechanism. v7.52 supplies that missing delivery layer. The intended user experience is
now: download/install `WITNESS-Setup.exe` once; use WITNESS normally; when a new stable Release
is published the installed app discovers it and offers one-click Update & Restart. The update
replaces program files only and the personal local profile persists untouched. GitHub Releases
is used as the first binary/update host because it provides versioned release assets and can be
queried without a WITNESS account when the release endpoint is public. The design keeps the
hosting adapter isolated in `update_manager.py` so it can later move to another HTTPS host or
Microsoft distribution path without changing the game/profile backend.

Important honesty/limitations:
- The current chat build environment is Linux. PyInstaller is not a cross-compiler, so this
  session CANNOT truthfully produce or run the final Windows `WITNESS-Setup.exe`. Instead it
  adds an automated `windows-latest` release job (and local Windows script) that builds/tests the
  Windows binary where it must be built. The first real installer appears after the source is
  placed in a GitHub repo/release host and a matching `v7.52.0` tag is pushed, or after the local
  Windows build script is run on a Windows machine with Inno Setup installed.
- For no-login clients using the provided GitHub API flow, the release endpoint must be publicly
  readable. If source privacy matters, use a separate public binaries-only release repo/host
  rather than embedding GitHub credentials into WITNESS.
- These internal/early installers are not code-signed yet, so Windows may show unknown-publisher
  or reputation warnings. Add trusted Windows code signing before broad public distribution.
- API secrets remain local/profile-isolated but plain-text `secrets.json` still needs DPAPI or
  equivalent Windows-protected storage before broad distribution.

Validation:
- Full-project `compileall` + AST parse after distribution edits: 69 Python files, 0 errors.
- `update_manager.is_newer()` exercised for newer/equal/older version cases.
- Mocked end-to-end release fixture: fake GitHub latest-release response advertised v7.53.0 with
  Setup + SHA assets; updater detected the new release, streamed a fake installer, checked the
  exact SHA-256, and produced the verified temp installer. Progress reached 100%.
- `packaging/prepare_release.py` tested with `testowner/witness-releases` + `v7.52.0`; it accepted
  the matching tag and correctly embedded the repo. Checked-in `release_channel.json` was then
  restored to its intentionally blank repository state.
- PyInstaller spec Python syntax and required Inno installer contract fields received static
  checks. YAML workflow parses structurally in the available parser (noting PyYAML 1.1 treats
  the literal GitHub key `on` as boolean, while GitHub Actions uses its own YAML semantics).
- Actual Windows PyInstaller/Inno/frozen-Qt validation is intentionally delegated to the supplied
  Windows release workflow because this Linux environment cannot validate a Windows executable.
- No database, `witness_data.json`, synthetic day history, `secrets.json`, profile settings, or
  other recognized runtime/user artifact is included in the source package.
- `core/*.py` hash set matches the captured v7.51 baseline exactly after final packaging.

Left for next session:
Establish the one real publicly-readable binary release endpoint. The simplest first path is to
put the clean source in a GitHub repository and push `v7.52.0`; the supplied Actions workflow
should produce/publish the first `WITNESS-Setup.exe`. If source must be private, adapt publishing
to a separate public binaries-only release repo/host instead. Install that first Setup on the
person's Windows machine and verify Start/desktop launch, `%LOCALAPPDATA%\WITNESS` profile
persistence, and a real v7.53 test release appearing as Update & Restart. Once distribution is
proven, return to product completion: full Qt runtime integration, DPAPI secret hardening, then
final Character/runtime polish. Do not reopen scoring architecture.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before editing;
never read/open/share `secrets.json`; keep `core/` frozen unless the person explicitly authorizes
Layer 1; add a NEW DEVLOG entry at the top (never edit/delete old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files were
updated before ending the session.

## 2026-08-15 -- v7.51 Local Profile Isolation: per-Windows-user data, clean packages, legacy import
Requested by: person wants WITNESS ready to run from brand-new data for each user without
adding usernames/passwords yet. They specifically want different users' backend history
kept separate, updates to stop overwriting personal progress, and a future path to a real
installed/updatable app.

Touched:
- `profile_runtime.py` (new): standard-library-only bootstrap imported before WITNESS
  data/config/core modules. On Windows the default data root is `%LOCALAPPDATA%\WITNESS`
  (overrideable with `WITNESS_DATA_DIR` for tests/dev). It creates/persists an anonymous
  UUID `profile_id` in `profile.json`, exports `WITNESS_APP_DIR` / `WITNESS_DATA_DIR` /
  `WITNESS_PROFILE_ID`, then changes process cwd to the local profile. This intentionally
  makes every historical relative data path resolve into that person's profile without
  rewriting frozen Layer 1.
- `profile_runtime.py`: recognized legacy migration list covers canonical DB/data, old
  progression/conversation/trigger/preferences/history files plus recaps, SOS/video
  memories, hourly history, insights and journals. If a build is placed directly over an
  old project-folder install and the profile has no DB yet, recognized data copies into
  the profile automatically. `stage_legacy_import()` lets a separate old folder be chosen;
  the copy is deferred until next process launch so it happens before SQLite is opened.
  Conflicting profile files are replaced only for an explicitly staged import; source data
  is copied, never deleted. Import history is recorded locally.
- `qt_main.py` and legacy `main.py`: activate the same profile boundary before importing
  shared/core/character data modules. This means both frontends still share the same one
  person's history, but application code no longer owns that history.
- `ui_qt/pages.py`: Settings gained **LOCAL PROFILE** with short profile ID, selectable
  data path, Open Data Folder, and Import Existing WITNESS Folder. Import validates the
  selected folder, explains that conflicting current profile data is replaced on restart,
  and stages the operation rather than touching an open SQLite connection.
- `shared/config.py`: documented that data paths remain relative on purpose because the
  profile bootstrap owns cwd. This is a compatibility contract, not unfinished path work.
- `shared/secrets_store.py`: documentation corrected from "project root" to active local
  profile. `secrets.json` remains plain text for now; DPAPI/Windows-protected secret storage
  is explicitly still future hardening.
- Cleaned the distributable source tree: removed bundled `witness_data.json` and synthetic
  `day_breakdown_data/`; package contains no `witness.db`, progression/preferences/history,
  notes/videos/insights/recaps, or `secrets.json`. New users therefore start from empty
  canonical tables rather than inheriting developer/demo state.
- `ui_qt/shell.py`: build tag -> `2026-08-15-d`. `README.md`, `ARCHITECTURE.md`,
  `QT_BUILD.md`, and `NEXT_CHAT_PROMPT.md` now document the profile boundary, migration
  workflow, clean-package rule, and next installer/updater implications.

Did NOT touch: `core/` in any way. Every `core/*.py` file is byte-for-byte identical to
v7.50. The person did not authorize Layer-1 behavior changes and none were necessary: cwd
is changed before Layer 1 loads, so even `vision_history.json`, `trail_history.json` and
`block_lock.txt` naturally become per-profile. Also did not change `shared/game_engine.py`
scoring, Ghost math, records, rolling levels, Character projection rules, Activities,
History/Progression calculations, or the Qt responsiveness architecture.

What changed and why:
The backend has always been conceptually single-user (one local SQLite DB, no cross-user
rows). The missing product boundary was *where that one user's files lived*: older builds
used the project working directory, which is wrong for distribution and updating. WITNESS
now defines one local profile per Windows account and keeps program code separate from
personal state. No `user_id` columns are added because each profile owns an independent DB.
This is intentionally simpler and safer for V1 than premature cloud auth. Two people using
the same Windows login would still share one profile; true multi-profile/login/cloud sync
is deferred.

Validation:
- Full-project AST + `compileall`: 65 Python files, 0 errors.
- Clean first launch in an isolated data root: generated a profile UUID, created canonical
  DB/data only in that root, and started with 0 scoring Activities, 0 XP events and 0 raw
  activity rows.
- Reopened the same root in a fresh process: exact same profile ID persisted.
- Started a second isolated data root: received a different UUID and separate empty DB.
- Automatic same-folder migration fixture: copied legacy DB + JSON + dated video into a
  fresh profile and preserved source files.
- Staged import fixture: selected a separate old folder containing DB/progression/hourly
  history, confirmed pending state, simulated restart, confirmed import applied before DB
  use and pending marker cleared.
- Runtime-write isolation fixture: wrote a note/DB state, video memory, day breakdown, old
  progression XP and Qt preference after profile activation; every artifact landed under
  the profile data root and the application source tree stayed clean.
- Clean-package audit: no recognized runtime/user artifact exists in the source tree.
- `core/*.py` SHA-256 set matches v7.50 exactly.

Left for next session:
Run v7.51 on the person's Windows machine. Settings -> Local Profile should show a path
under `%LOCALAPPDATA%\WITNESS`. If preserving current v7.50 data matters, choose the old
folder with Import Existing WITNESS Folder, close/reopen, and verify XP/Calendar/Character
history. After this boundary is proven, the product-completion work is PySide6 full-runtime
integration followed by Windows packaging/updating. Before broader distribution, replace
plain-text local API-key storage with Windows-protected/DPAPI-backed storage. Do not create
a cloud account system unless actual multi-device/recovery requirements justify it.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before
editing; never read/share `secrets.json`; keep `core/` frozen unless the person explicitly
authorizes Layer 1; add a NEW DEVLOG entry (never edit old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files
were updated before ending the session.

## 2026-08-15 -- v7.50 Character Foundation: interactive avatar, environments, traits, shield + passive-sound fix
Requested by: person liked v7.49's calm polish, reported an unsolicited/random sound
roughly every ~20 seconds while idle, then approved the dedicated Character/Avatar page
roadmap. They want a full-frame representation of the person that evolves with Level,
can be rotated/placed in environments, visually charges from real-world scoring, earns
behavioral attributes such as Persistence, and gains a protection shield after a long
clean drift/SOS streak. Fitness/watch/body-shape integration is explicitly deferred.

Touched:
- `shared/character_engine.py` (new): read/projection layer over canonical WITNESS data.
  It does NOT own XP. `live_state()` projects current level, daily charge and environment;
  `snapshot()` adds behavior-derived Attributes and Protection Shield progress. Charge is
  today's exact battle XP against the strongest useful daily target (prior record, Ghost
  finish, or 1,000-XP cold-start floor). Environment unlocks use peak level so earned
  scenes survive demotion. Only the selected environment ID is persisted via `game_state`.
  Attributes are explainable/descriptive only: Persistence (wins after losing days),
  Discipline (clean monitored shield progress), Momentum (current fight streak),
  Production (recent 7-day XP vs personal rolling best), and Focus (tracked/manual focus
  evidence). None award XP or alter score/level/records.
- `shared/character_engine.py`: Protection Shield uses only observed monitoring days. A
  day must have tracking evidence and zero flagged drift samples, red-lines and SOS events
  to count clean; missing data is never silently treated as success. Shield 1 unlocks at
  14 clean monitored days and strengthens at 30/60/90. The current Qt shell still does
  not start Layer-1 tracking, so real shield progress depends on existing runtime telemetry
  until the later full-runtime migration.
- `ui_qt/character_page.py` (new): dedicated CHARACTER page. The first renderer is an
  asset-free interactive 2.5D/vector avatar so the emotional/interaction contract can be
  proven without adding a fragile 3D engine/deployment dependency. Drag left/right rotates
  (pseudo-yaw), mouse wheel zooms. Permanent Level changes armor/form; current Charge
  changes a separate aura; shield progress/tiers draw a surrounding protection field.
  Environment scenes: Training Room, Winter (snow, breath, subtle shiver), Tropical
  (palms/ocean motion), Desert (dunes/dust), City Night (skyline/rain). Locked environments
  remain visible with their required level. The page also displays Level, Charge, Shield
  and transparent evidence behind each Attribute.
- `ui_qt/shell.py`: added CHARACTER to bottom navigation and advanced window build tag to
  `2026-08-15-c`. Character implements a cheap `live_refresh()` so the 2-second timer only
  updates live level/charge/environment; slower traits/shield are recalculated on full page
  refresh/entry, preserving the v7.48 responsiveness rules.
- `ui_qt/widgets.py`: small Arena `RankAvatar` is now clickable and opens the full Character
  page. It remains only a compact level emblem on Arena.
- `ui_qt/arena.py`: fixed the reported idle/random sound. Root cause was passive same-clock
  Ghost replay: on the 2-second live timer a historical Ghost event could cross the user's
  lead and call `audio.play("danger")` even though the person had not touched the app. The
  Ghost still advances and can show the visual "GHOST TOOK THE LEAD" warning, but passive
  timer transitions are now silent. Audio remains reserved for confirmed user actions and
  action-triggered milestones. Also wired the small rank emblem to CHARACTER.
- `QT_BUILD.md`, `README.md`, `ARCHITECTURE.md`, `NEXT_CHAT_PROMPT.md`, `qt_main.py`: advanced
  documentation/handoff to v7.50 Character Foundation and recorded the replaceable 2.5D
  renderer decision, character projection contract, shield honesty rule and sound fix.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work. Also did
not modify `shared/game_engine.py`, `shared/db.py`, `shared/demo_data.py`, Activity XP,
Ghost math, records, level thresholds/decay, Calendar/Progression math, or fitness data.
Character is downstream presentation/projection only.

What changed and why:
The Arena is for the daily fight; trying to place a full-body avatar there would crowd the
clearest part of the product. Character therefore becomes the emotional/evolution surface:
"who I have become" is permanent Level/form, while "how I am performing today" is Charge.
The first renderer deliberately proves rotation, environments, level evolution, shield and
behavior connection without committing WITNESS to a heavy 3D stack. A future true 3D model
can replace `AvatarStage` while continuing to consume `character_engine.snapshot()`.

Validation:
- Full-project AST sweep: 64 Python files, 0 syntax errors.
- Full `compileall`: clean.
- Empty-account `character_engine.snapshot()` returns sane Recruit/0-charge/locked-scene
  state without writing XP.
- 28-day synthetic fixture: Character reaches the canonical synthetic level, Charge reacts
  to today's actual synthetic ledger score, level-appropriate environments unlock, and the
  five Attributes populate from the same history.
- Protection fixture: inserted 15 consecutive monitored days with no flagged/red-line/SOS
  breach; Shield 1 unlocked with a 15-day clean streak as designed.
- Environment lock test: Level-1 state rejects selecting City Night and accepts Training.
- Character snapshot read test: XP sum was identical before/after reading character state.
- `shared/game_engine.py`, `shared/db.py`, and `shared/demo_data.py` SHA-256 remain unchanged
  from v7.49; every `core/*.py` hash matches the pre-change baseline byte-for-byte.
- Current Qt APIs used for custom painting/drag/wheel/combobox behavior were checked against
  official Qt for Python documentation. PySide6 itself is not installed in this Linux
  sandbox, so the actual Character render/drag/zoom/environment animation must be judged on
  the person's Windows machine.

Left for next session:
Run v7.50 on Windows. Open CHARACTER from the nav or by clicking the Arena rank emblem;
with 28-day demo history Level 2 should make Winter selectable. Test drag rotation, wheel
zoom, scene motion, charge aura, Attributes, shield messaging, and confirm the old random
idle sound is gone. Send a screenshot/bugs. If this foundation feels right, stop adding
major structural features and make the next product phase **PySide6 full-runtime integration**
so the polished Qt shell can host the proven tracker/voice/intervention system without
rewriting frozen Layer 1. Fitness remains deferred.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG before
editing; never read/share `secrets.json`; keep `core/` frozen unless the person explicitly
authorizes Layer 1; add a NEW DEVLOG entry (never edit old entries) and update
NEXT_CHAT_PROMPT.md after meaningful work. Tell the person directly that both handoff files
were updated before ending the session.

## 2026-08-15 -- PySide6 Alive Pass 2: rank avatar, impact feedback, restrained sound
Requested by: person confirmed the v7.48 responsiveness fix "works great now" and
approved the next polish pass: character/avatar evolution, stronger level-up/record
moments, better hover states, subtle sound and a little more life in the Battle area,
without adding clutter or making the app slow again.

Touched:
- `ui_qt/widgets.py`: new `RankAvatar`, an asset-free evolving player emblem driven
  only by canonical level/name. The silhouette, rank chevrons and outer ring gain
  visual weight as levels rise; `celebrate()` adds a short gold ring only on a real
  level-up. `BattleBar` now has a lightweight confirmed-score shockwave at the live
  endpoint. Activity cards opt into hover state without being rebuilt.
- `ui_qt/arena.py`: player HUD now uses `RankAvatar`; current-tier progress text adds
  `% conquered`; confirmed Activity scores trigger the BattleBar impact plus subtle
  XP sound before deferred canonical refresh. Level-up, record and overtake banners
  have a stronger two-line entrance and matching rare milestone sound. Ghost taking
  the lead gets a quiet danger cue. All milestone decisions still compare BEFORE/
  AFTER canonical `game_engine.dashboard_snapshot()` state; Qt does not invent XP.
- `ui_qt/audio.py` (new) + `ui_qt/assets/sounds/*.wav` (new): tiny low-amplitude WAV
  cues for XP, overtake, record, level-up and danger. Playback uses Windows stdlib
  `winsound.PlaySound(..., SND_ASYNC)` and silently no-ops if unavailable. No new
  Python package or network dependency.
- `ui_qt/prefs.py` (new): delivery-only `ui_settings.json` preference for Sound
  Feedback. Safe to delete; it contains no scoring state or secrets.
- `ui_qt/pages.py`: Settings now has a FEEDBACK card and Sound Feedback ON/OFF
  toggle. Turning it on plays one quiet confirmation tone.
- `ui_qt/theme.py`: restrained Activity-card hover/focus refinement; no new accent
  family. Palette remains charcoal/white + green, red only danger, gold milestones.
- `ui_qt/shell.py`, `qt_main.py`, `QT_BUILD.md`, `README.md`: advanced visual build
  to v7.49 / `2026-08-15-b` and documented Alive Pass 2.
- `ARCHITECTURE.md`, `NEXT_CHAT_PROMPT.md`: handoff updated with the new delivery
  components and the unchanged v7.48 responsiveness rules.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work. Every
`core/*.py` file remains byte-for-byte unchanged from v7.48. Also did not modify
`shared/game_engine.py`, `shared/db.py`, `shared/demo_data.py`, Activities scoring,
Ghost math, records, rolling-level math, Calendar/Progression calculations or the
correlation engine.

What changed and why:
v7.48 proved that WITNESS can feel immediate when feedback paints before expensive
refresh work. This pass adds sensory consequence without reopening architecture:
the player has a visual rank identity, a real score creates a small impact at the
battle endpoint, and rare milestones sound/enter differently from ordinary XP. Sound
is optional and deliberately low-volume. Nothing in these effects owns truth; the
backend still decides every point, record, level and battle transition.

Validation:
- Full-project AST sweep: 62 Python files, 0 syntax errors.
- Full `compileall`: clean.
- `shared/game_engine.py`, `shared/db.py`, and `shared/demo_data.py` SHA-256 match
  v7.48 exactly.
- Every `core/*.py` SHA-256 matches the pre-change v7.48 baseline exactly.
- All five packaged WAV files open as valid mono 16-bit / 22.05 kHz WAVs and are
  only ~0.10-0.45 sec long; local Sound Feedback preference round-trip tested.
- PySide6 is not installed in this Linux sandbox, so actual hover/animation/audio
  rendering must be judged on the person's Windows machine. Do not claim visual or
  sound verification until that run.

Left for next session:
Run v7.49 on Windows and judge whether the rank emblem, battle shockwave, milestone
payoff and sound feel restrained rather than gamey. Hammer +1 again to verify sound
and impact did not regress v7.48 responsiveness. If approved, major visual structure
is essentially done; the next meaningful product step is planning PySide6 full-runtime
integration so the polished shell can own the existing tracker/voice/intervention
runtime without rewriting frozen Layer 1. `core/` remains frozen unless the person
explicitly authorizes Layer 1 changes.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG
before editing; never read/share `secrets.json`; keep `core/` frozen unless the
person explicitly authorizes Layer 1; add a new DEVLOG entry (never edit old
entries) and update NEXT_CHAT_PROMPT.md after meaningful work.

## 2026-08-15 -- v7.48 responsiveness fix: stop blocking the Qt paint loop
Requested by: person tested v7.47 on Windows and reported that the app felt slow/
glitchy: clicking an Activity could be followed by a several-second delay before
its animation appeared. They liked the Alive Pass visually and wanted the same
feedback to feel immediate/smooth.

Touched:
- `ui_qt/shell.py`: removed the Activity-click connection that synchronously
  called `refresh_all()` across Arena + Calendar + Records + Insights + Settings.
  Hidden pages now refresh lazily when opened, as they already know how to do.
  The 2-second live timer uses an Arena-specific lightweight `live_refresh()` path.
- `ui_qt/arena.py`: Activity XP/undo feedback is now created immediately and the
  heavier canonical dashboard refresh is deferred with `QTimer.singleShot(0, ...)`
  so Qt gets control back and can paint the first animation frame before queries/
  layout updates. Added fast vs full refresh paths. Correlation text only recomputes
  on a full/page-entry refresh, not every 2 seconds or every +1. Activity cards are
  no longer destroyed/recreated on every timer tick or score event; a roster
  signature rebuilds only when name/XP/type/IDs actually change.
- `ui_qt/widgets.py`: `ActivityCard` now keeps stable child widgets and exposes
  `update_data()` for live TODAY count, record, button state and undo visibility.
  This removes repeated layout allocation/deletion during normal scoring.
- `ui_qt/shell.py`, `qt_main.py`, `QT_BUILD.md`, `README.md`, `ARCHITECTURE.md`,
  `NEXT_CHAT_PROMPT.md`: advanced/documented v7.48 / build `2026-08-15-a`.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work.
Also did not change `shared/game_engine.py`, `shared/db.py`, score values, Ghost
math, records, level thresholds/decay, History data, or progression calculations.

What changed and why:
The confirmed root cause was architectural UI blocking, not PySide6 animation
speed. In v7.47 an Activity button emitted `changed`, and `shell.py` immediately
rebuilt EVERY page synchronously on the GUI thread before Qt returned to its event
loop. Arena itself also recreated every Activity card and reran insight analysis
on its 2-second timer. The animation objects existed immediately, but could not
paint until that synchronous work finished. v7.48 makes feedback first, refresh
second, and only refreshes the data actually visible/needed.

Validation:
- Full-project `compileall`: clean, 0 syntax errors.
- Canonical backend benchmark on a synthetic 28-day ledger: dashboard snapshot
  ~12 ms average; behavior correlations ~14 ms; individual Activity recording
  ~2.8 ms average in this sandbox. This supports the diagnosis that multi-page Qt
  rebuild/layout work -- not score math -- caused the seconds-long Windows lag.
- Static code checks confirm Activity clicks no longer call `refresh_all()` and
  the 2-second timer uses `live_refresh()` when available.
- PySide6 is still not installed in this Linux sandbox, so perceived smoothness
  must be verified by the person's Windows render.

Left for next session:
Run v7.48 on Windows and hammer +1 10-20 times, test +15m/Undo, and switch pages.
Feedback should begin immediately and scores/bars should catch up smoothly. If any
lag remains, measure the exact interaction that lags before changing architecture;
next likely step would be moving dashboard snapshot calculation to a Qt worker,
but do NOT add threading unless the real Windows test still needs it.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG
before editing; never read/share `secrets.json`; keep `core/` frozen unless the
person explicitly authorizes Layer 1; add a new DEVLOG entry (never edit old
entries) and update NEXT_CHAT_PROMPT.md after meaningful work.

## 2026-08-14 -- PySide6 Alive Pass 1: movement, XP impact, live Ghost feedback
Requested by: person approved the v7.46 Arena/History/Progression structure and
said, "lets do it" after agreeing that the next phase should make WITNESS feel
alive: XP feedback, moving battle state, subtle win/loss energy, milestone moments
and smoother navigation. They explicitly wanted polish now, not another backend
rebuild.

Touched:
- `ui_qt/widgets.py`: added reusable delivery-only animation primitives.
  `AnimatedNumberLabel` eases integer display values; `SmoothProgressBar` eases
  progress changes; `BattleBar` now interpolates YOU/GHOST/finish/record positions
  instead of snapping and has a small pulsing live endpoint; Sparkline marks the
  latest point; ActivityCard has a brief confirmed-score border/background pulse.
- `ui_qt/arena.py`: wired the above to the existing canonical dashboard snapshot.
  Activity scoring now produces a short local `+XP` fly-up only *after*
  `game_engine.record_activity()` succeeds. Undo shows negative feedback from the
  real reversal row. Before/after canonical snapshots drive short non-modal
  milestone banners for LEVEL UP, NEW DAILY RECORD, GHOST OVERTAKEN, and WEEKLY
  LEAD TAKEN. The same-clock Ghost replay is now visibly alive: when its historical
  score increases while the app is open, a gray `GHOST +XP` fly-up appears; if the
  replay crosses into the lead, a red `GHOST TOOK THE LEAD` banner appears. Battle
  card border subtly follows ahead/tied/behind. No effect can award or alter XP.
- `ui_qt/shell.py`: page changes get a brief opacity fade instead of a hard cut.
- `ui_qt/theme.py`: added a clearer pressed state for Primary action buttons; kept
  the approved restrained palette.
- `qt_main.py`, `QT_BUILD.md`, `README.md`: advanced visual build to v7.47 /
  `2026-08-14-h` and documented the Alive Pass.
- `ARCHITECTURE.md`: documented the rule that animation/feedback is delivery only
  and must always reflect canonical `game_engine.py` values.
- `NEXT_CHAT_PROMPT.md`: CURRENT FOCUS updated to v7.47, its validation limits and
  the next real decision: test Alive Pass on Windows, then plan full Qt runtime
  migration rather than reopening score architecture.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work.
Every `core/*.py` file was compared to the v7.46 package and remains byte-for-byte
unchanged. Also did not modify `shared/game_engine.py`, `shared/db.py`, scoring
Activities, Ghost replay math, records, rolling level formula, History storage or
Progression calculations.

What changed and why:
The app had reached the point where adding more structure would dilute the product.
This pass makes already-correct state *feel consequential*: points travel visibly,
the opponent can visibly move, and rare transitions get a brief payoff without
turning the interface into a colorful arcade. The distinction remains strict: the
backend decides reality; Qt only animates the confirmed result.

Validation:
- Full-project `compileall` + AST parse sweep: 60 Python files, 0 syntax errors.
- Recursive diff against v7.46 confirms all `core/` files unchanged; the only code
  changes are Qt presentation files listed above (plus docs/version text).
- PySide6 animation classes/property usage (`QVariantAnimation`,
  `QPropertyAnimation`, `QGraphicsOpacityEffect`, parallel/sequential groups,
  `QPauseAnimation`, `QEasingCurve`) were checked against current official Qt for
  Python documentation before packaging.
- PySide6 is not installed in this Linux sandbox, so the Qt UI itself could not be
  rendered here. Do not claim visual/runtime animation verification until the
  person runs it on Windows. The existing Windows render remains authoritative.

Left for next session:
1. Person runs v7.47 on Windows; press repeatable/timed Activities several times
   and check count-up, fly-up, button/card feedback and BattleBar movement.
2. With synthetic history active, watch same-clock Ghost replay if a historical
   event lands; verify gray Ghost feedback and red takeover banner are not too loud.
3. Switch between Arena/History/Records/Insights/Settings and judge the page fade.
4. Fight concrete Windows scaling or animation bugs only. If approved, plan the
   PySide6 full-runtime migration next. `core/` remains frozen until explicit Layer
   1 authorization.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG
before editing; never read/share `secrets.json`; keep `core/` frozen unless the
person explicitly authorizes Layer 1; add a new DEVLOG entry (never edit old
entries) and update NEXT_CHAT_PROMPT.md after meaningful work.

## 2026-08-14 -- History Progression charts: Current Level territory + All-Time evolution
Requested by: person approved the v7.45 Windows Arena/History screenshots and
asked for one final structural History feature before moving on: a stock-chart-
style XP/level growth view with BOTH an all-time map and a current-level map.
Their key product insight was that once a new level is reached, that level should
become the new visual baseline so old success does not make the person
comfortable; the All-Time view remains available for pride/trend analysis.

Touched:
- `shared/db.py`: additive `level_events` table + index/storage helpers. Real
  promotion/demotion/reclaim transitions are now permanently appended from this
  build forward. A transition-dedupe index prevents duplicate history if two UI
  reads race. This is separate from and does not rewrite `xp_events`.
- `shared/game_engine.py`: added `all_daily_level_scores()`, efficient
  `rolling_rating_series()` and `progression_snapshot()`. The historical series
  uses one grouped ledger read then the EXACT existing 14-day exp(-0.10*d)
  weighting in Python, avoiding thousands of SQLite reads on long history.
  `progression_snapshot()` returns chart-ready All-Time + Current-Level data,
  current-tier entry date, entry threshold, demotion floor, next threshold,
  territory %, peak rating/day and milestones. Older threshold crossings are
  reconstructed from immutable XP history; explicit new level transitions are
  merged in. Existing battle XP, Ghost, high-score and level-state rules were
  not replaced. `level_status()` now appends a real transition row only when the
  actual current level changes: promotion, reclaim, or demotion.
- `shared/demo_data.py`: clearing synthetic demo history also clears only level
  transitions tagged `synthetic_demo`, preventing demo progression from leaking
  into real history.
- `ui_qt/progression.py` (new): PySide6 delivery-only Progression view.
  **CURRENT LEVEL** shows the current tier as territory: entry line, next-tier
  ceiling, 85% demotion floor + red danger zone, current rating, territory %,
  peak, and a stock-style rating line beginning at the tier-entry date.
  **ALL TIME** shows the complete rolling Level Rating from the first XP day,
  level threshold lines and milestone markers. Hovering any plotted date shows
  date, rolling rating, daily XP and natural tier. Milestone list shows reached,
  reclaimed and demoted tiers.
- `ui_qt/pages.py`: History now has top-level **CALENDAR | PROGRESSION** modes.
  The approved v7.45 Calendar/Day Detail remains intact; Progression is a second
  lens rather than clutter inside the calendar grid.
- `qt_main.py`, `QT_BUILD.md`, `README.md`: advanced Qt visual build to v7.46 /
  `2026-08-14-g` and documented the new History lens.
- `ARCHITECTURE.md`: documented `level_events`, progression backend contracts
  and the new Qt Progression delivery layer.
- `NEXT_CHAT_PROMPT.md`: CURRENT FOCUS updated so the next AI knows v7.46 is the
  final structural visual baseline before moving on to polish/runtime planning.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work.
Every `core/*.py` SHA-256 is compared before packaging and must remain byte-for-
byte unchanged. Also did not change the canonical configured Activity score,
Ghost replay, weekly Campaign, record or 14-day rating formula.

What changed and why:
Two views deliberately serve two different psychological jobs. All-Time says
"look how far I came" and preserves level milestones; Current Level says "this
is zero now -- conquer the next territory" while keeping the demotion floor in
view so the person cannot coast. The chart uses rolling Level Rating rather
than cumulative lifetime XP because cumulative XP can only rise and eventually
stops representing current performance. This completes the main structural
History concept without reopening scoring architecture.

Validation:
- Full project `compileall` + AST sweep: 60 Python files, 0 syntax errors.
- Isolated 28-day synthetic fixture: 1,033 canonical XP events produced a
  28-point All-Time rating series, a Current-Level segment beginning at the
  reconstructed level-entry date, correct threshold/floor/next-tier metadata and
  milestone crossing. Sampled chart points exactly matched the existing
  `rolling_rating(day)` calculation.
- Demo clear removed all tagged synthetic XP AND synthetic level-transition rows.
- Separate real-event regression: initialized at Level 1, logged one 6,000-XP
  real event, called `level_status()`, confirmed immediate Level 2 promotion and
  exactly one permanent `promotion` row (from 1 -> 2, rating 6000).
- PySide6 is still unavailable in the Linux sandbox, so Qt rendering itself was
  not claimed/tested here; the person's Windows render remains authoritative.

Left for next session:
1. Person runs v7.46 -> HISTORY -> PROGRESSION and checks both CURRENT LEVEL and
   ALL TIME on Windows, ideally with the 28-day synthetic fixture still active.
2. Fight only concrete scaling/tooltip/label issues from that render.
3. If approved, stop adding large structural features and move to polish /
   character-avatar feedback / micro-interactions, then plan the PySide6 full-
   runtime migration separately. `core/` stays frozen unless explicitly
   authorized.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG
before editing; never read/share `secrets.json`; keep `core/` frozen unless the
person explicitly authorizes Layer 1; add a new DEVLOG entry (never edit old
entries) and update NEXT_CHAT_PROMPT.md after meaningful work.

## 2026-08-14 -- PySide6 visual pass 2 + full Qt History day detail (Notes/Videos restored)
Requested by: person ran the first real Windows Qt build, said it looked much
better overall, approved the basic layout/visual direction, and asked to build
the next pass now. Their screenshot exposed specific polish issues: too many
black rectangles behind labels, Activity Forge wrapped the fifth card onto a
second row leaving a large dead area, Battle/typography/header could be stronger,
and the lower cards had too much empty space. They also reported the Qt History
calendar did not show daily Notes or Videos and the computer/day schedule was
only basic text.

Touched:
- `ui_qt/theme.py`: visual pass 2. Added explicit transparent QLabel/background
  behavior (fixes the opaque black title/label rectangles visible in the real
  Windows screenshot), more restrained surface depth, tighter component styling,
  better scrollbars/tables/tabs/text inputs, and kept the accepted narrow color
  semantics: charcoal/white base, green action/winning, red danger/losing, gold
  records only. No new category rainbow colors.
- `ui_qt/widgets.py`: refined reusable cards/badges/BattleBar/Sparkline and made
  ActivityCard more compact (minimum width 148px) so five normal Activities fit
  across at the person's wide-screen size. BattleBar hierarchy/readability is
  stronger while still showing live YOU + same-clock Ghost + historical finish
  line + optional record tick.
- `ui_qt/arena.py`: visual pass 2 only; canonical backend contracts unchanged.
  Stronger score hierarchy, cleaner player/level HUD, Daily/Weekly title follows
  selected mode, responsive Activity Forge reflows 5/4/3/2 columns based on the
  real Qt viewport width, compact lower cards, and Record Chase now translates
  remaining XP into an example path using configured Activity values (display
  guidance only -- does not alter score math). Added trailing layout stretch so
  spare vertical room no longer inflates the lower content cards.
- `ui_qt/pages.py`: replaced the placeholder Qt History detail with a real Day
  Detail panel backed by existing storage. Calendar cells now mark record day,
  record week, Notes, and Videos. Click a day -> OVERVIEW / COMPUTER / NOTES /
  VIDEOS tabs:
    * Overview: `game_engine.day_summary()` score, Ghost, final gap, record status,
      Activity breakdown and exact timestamped/running XP timeline in structured
      tables.
    * Computer: existing `shared/day_breakdown.py` data shown hour-by-hour with
      time, dominant category, summary and top apps; if real raw activity exists
      without an hourly doc, the Qt screen can build it from the existing log.
    * Notes: reads/writes `shared/db.py`'s existing notes table for the selected
      date (`log_note_for_day`); no Qt-only notes store.
    * Videos: reads/copies/opens through existing `shared/video_memories.py`,
      using a native Qt file picker. No Qt-only video store.
  Also refined Records/Insights/Settings presentation so tables/cards follow the
  same visual system.
- `ui_qt/shell.py`: removed the debug-like footer copy, tightened top/nav chrome,
  kept the existing Arena/History/Records/Insights/Settings structure.
- `qt_main.py`, `QT_BUILD.md`, `README.md`: Qt visual version advanced to v7.45 /
  build `2026-08-14-f`; documented that History now shares the old Tkinter data.
- `ARCHITECTURE.md`: documented v7.45 Qt delivery contracts and explicitly noted
  that Qt Notes/Videos/Computer history reuse `db.py`, `video_memories.py`, and
  `day_breakdown.py` rather than creating parallel state.
- `NEXT_CHAT_PROMPT.md`: CURRENT FOCUS updated with the person's first Windows
  render findings, the v7.45 state, validation limits, and exact next step.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work.
Captured SHA-256 for every `core/*.py` before edits and compared again after;
every hash is byte-for-byte unchanged. Also did not alter canonical score/Ghost/
level math in `shared/game_engine.py` or create a second history database.

What changed and why:
This is deliberately a delivery-layer refinement, not another architecture
rebuild. The first real Windows screenshot proved the Qt shell and information
hierarchy were right, so the correct move was to remove obvious visual artifacts
and fill the most important migration gap: History must feel like opening a save
file of a day, including the human context (notes/videos) and automatic computer
trail, not just a plain score string. Reusing existing storage keeps both UIs
consistent and preserves past data.

Validation:
- Full-project AST/compile sweep passes (59 Python files in this work tree, 0
  syntax errors; `python -m py_compile`/`compileall` also pass).
- Isolated backend History smoke test: created a scored Activity day, wrote an
  arbitrary-date note and confirmed month note marker, copied/listed a sample
  `.mp4` and confirmed month video marker, generated/loaded a 24-hour synthetic
  day breakdown, and confirmed day score contract -- all passed.
- Current Qt APIs newly relied on here were checked against official Qt for
  Python documentation (file picker, tabs, item-view/header enums, text editor).
- PySide6 is still not installed in this Linux sandbox, so the Qt window itself
  cannot be rendered here. The person's Windows screenshot remains the visual
  source of truth; do not claim this pass was visually run in the sandbox.
- No `secrets.json` exists in the packaged work tree; never read/include it if it
  appears in a person's real project.

Left for next session:
1. Person runs v7.45 and sends screenshots of Arena plus a selected History day,
   especially Computer/Notes/Videos, so real Windows spacing/scaling/clipping and
   file-dialog/open-video behavior can be fought from actual evidence.
2. If v7.45 visual structure is approved, continue migration of still-useful Qt
   surfaces: Weekly Closure and Integrations are the clearest next candidates.
3. Full Layer-1 tracker/voice/intervention runtime is STILL not started by
   `qt_main.py`. Plan that separately only after the Qt delivery surface is
   stable. `core/` remains frozen unless the person explicitly authorizes Layer 1.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire DEVLOG
before editing; never read/share `secrets.json`; keep `core/` frozen unless the
person explicitly authorizes Layer 1; add a new DEVLOG entry (never edit old
entries) and update NEXT_CHAT_PROMPT.md after meaningful work.

## 2026-08-14 -- PySide6 visual migration begins: polished Arena shell, backend unchanged
Requested by: person approved moving the presentation from tkinter to PySide6
and asked to start making WITNESS look good now that the pre-design systems
build feels coherent. They liked the tactical/dark direction but explicitly
said the concept image had too many colors, so the real palette should be much
more restrained.

Touched:
- `ui_qt/` (new presentation package): `theme.py`, `widgets.py`, `arena.py`,
  `pages.py`, `shell.py`. This is a PySide6-only visual layer over the existing
  canonical backend; no score math is duplicated here.
- `ui_qt/theme.py`: intentionally narrow palette -- charcoal/black neutrals,
  green as the one primary action/winning color, red only for losing/danger,
  gold only for records/major victories. Removed the multi-color-per-Activity
  approach from the earlier concept mockup.
- `ui_qt/widgets.py`: reusable Qt cards/badges, two-layer YOU/GHOST BattleBar,
  XP-vs-Ghost Sparkline, and ActivityCard controls. Activity cards all use the
  same restrained visual language rather than arbitrary category colors.
- `ui_qt/arena.py`: first polished Arena pass bound directly to
  `game_engine.dashboard_snapshot()`: header/level/rating/streaks, Daily Fight
  <-> Weekly Campaign, YOU/GHOST/gap, same-time battle bar, Activity Forge,
  14-day performance trend, strongest insight, and daily record chase. +1,
  once-daily Complete, +15m and Undo write through the existing game_engine.
- `ui_qt/pages.py`: simple Qt History Calendar, Records, Insights and Scoring/
  Demo pages so the new shell is not a dead one-screen mockup. These are first
  visual migrations, not final designs; Calendar still does not yet expose the
  old video/note/hourly subviews in Qt.
- `ui_qt/shell.py`: responsive desktop shell with Arena / History / Records /
  Insights / Settings bottom navigation and 2-second live refresh.
- `qt_main.py` (new): PySide6 entry point. Loads the exact same secrets/db/
  `game_engine` backend as the existing app. It deliberately does NOT yet start
  Layer-1 trackers/voice/intervention event handling; this is a parallel visual
  migration surface while the Qt runtime is proven.
- `start_witness_qt.bat` (new): launches `qt_main.py`. Existing
  `start_witness.bat` and `main.py` remain the known-good tkinter/runtime
  fallback.
- `install.bat`: now installs PySide6. If that install fails, the original
  tkinter app remains usable.
- `QT_BUILD.md` (new): identifies this visual build as v7.44 / 2026-08-14-e.
- `ARCHITECTURE.md`, `NEXT_CHAT_PROMPT.md`, `README.md`: updated to document the
  parallel-frontend migration and prevent a future AI from confusing Qt UI
  code with scoring or Layer-1 runtime logic.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work.
Every `core/*.py` SHA-256 hash matched before/after byte-for-byte. Also did not
replace or remove the tkinter `main.py`; it remains the safety/reference UI.

What changed and why:
The backend/pre-design build is now accepted by the person. The design phase
therefore starts by replacing the delivery layer without reopening the score
architecture. PySide6 gives the project a much better ceiling for layout,
styles, custom painting and later micro-interactions than tkinter. Doing the
migration in parallel means visual work can be aggressive without risking the
working tracker/intervention app. The Arena is the first target because it has
the clearest user loop: who am I fighting, am I winning, what action earns XP
next, and what record/level am I chasing.

Validation:
- Full Python compile sweep succeeds for the project including all new Qt files.
- Backend contract names/keys used by the Qt layer were checked directly
  against `shared/game_engine.py`, `shared/game_analytics.py`, and
  `shared/demo_data.py`.
- `core/` hash comparison passed byte-for-byte.
- PySide6 itself is NOT installed in this Linux sandbox and network installation
  is disabled here, so this session could not render/instantiate the real Qt
  widgets. Production Windows setup is handled by `install.bat`; first real UI
  validation must therefore happen on the person's machine. Do not claim this
  pass was visually executed here.

Left for next session:
1. Person runs `install.bat` once, then `start_witness_qt.bat`, preferably with
   Synthetic Demo active so every section is populated, and sends a screenshot.
2. Fight layout/spacing/font/scale issues from the real Windows render; preserve
   the restrained palette unless the person asks otherwise.
3. Once Arena visual direction is approved, migrate Calendar day detail
   (including notes/videos/hourly history), Weekly Closure and Integrations.
4. Only after the Qt surface is proven should we decide how to extract/start
   the full Layer-1 runtime under Qt. `core/` remains frozen; do not casually
   copy old `main.py` event logic or start trackers without preserving drift/
   escalation/red-line behavior.
5. Keep updating this DEVLOG and NEXT_CHAT_PROMPT after every meaningful session.

## 2026-08-14 -- Pre-design systems build: Arena, history, records, weekly closure, visible insights + safe demo data
Requested by: person said the backend was hard to use/validate while most of
it was invisible and asked to progress the app as far as practical through the
previously-described step 7 before making it pretty. They explicitly approved
synthetic data if needed and wanted a functional clean slate for later design,
accepting that real-use bugs can be fought afterward.

Touched:
- main.py: build tag -> `2026-08-14-e`. Replaced the active first-screen
  delivery with a deliberately plain PRE-DESIGN Arena driven by
  `game_engine.dashboard_snapshot()` instead of old focus/energy/goal display:
  Daily Fight <-> Weekly Campaign toggle, live YOU/GHOST/gap two-lane bar,
  same-clock/next-Ghost information, high-score distance, daily+weekly win
  streaks, rolling level state, Activity Forge, 14-day XP-vs-Ghost mini chart,
  strongest behavior association, and last-completed-week result. This is
  functional structure, not final styling.
- main.py: new live panels/menu routes for Records/High Scores, Rolling Level
  Details (exact 14-day weighted components), Weekly Closure, Behavior -> Score
  Insights, Synthetic Demo History, and Raw Backend Snapshot. The raw snapshot
  intentionally exposes `dashboard_snapshot()` + analytics JSON so the backend
  can be inspected directly instead of inferred from UI behavior.
- main.py: Performance Chart rebuilt around canonical battle XP + 7-day Ghost
  history, with 7/30/60-day views. Retired focus-percentage scores are not used
  by this chart.
- main.py: Calendar month grid now reads `game_engine.calendar_month_summary()`
  and shows each scored day's XP plus record-day / record-week markers alongside
  note/video markers. Day detail now begins with canonical final score vs Ghost,
  gap, record flags, Activity XP breakdown and the exact timestamped/running XP
  event timeline; existing hourly computer activity, notes and videos remain
  below it.
- shared/game_engine.py: added `performance_series()` for canonical chart data,
  `week_summary()` for a completed Monday-Sunday "7 players" closure battle,
  and `hall_of_fame()` for record locations. `dashboard_snapshot()` now also
  includes `hall_of_fame` + `last_completed_week`. Existing scoring/Ghost/level
  rules were not replaced.
- shared/db.py: added isolated `demo_daily_features` storage and small helpers
  (`save_demo_daily_feature`, `demo_daily_feature`, clear, tagged-XP deletion,
  game_state delete). Fake telemetry is NOT written into real activity/input/
  presence tables.
- shared/demo_data.py (new): optional ~28-day deterministic-but-varied fixture.
  It creates/uses Cold Calls, Booked Job, Workout and Focus Work Activities,
  writes timestamped canonical XP rows tagged `source='synthetic_demo'`, stores
  analytics-only fixture features in `demo_daily_features`, and creates the
  existing synthetic hourly Calendar docs. Same-time Ghost replay therefore
  uses the exact same event shape as real actions. `clear()` removes only demo
  XP/features/synthetic hourly docs and deactivates only Activities it created;
  it backs up/restores the pre-demo rolling-level state. Real XP, telemetry,
  notes and videos are left intact.
- shared/game_analytics.py: when demo mode is explicitly active and a day has no
  real telemetry, analytics can read the isolated demo feature row. Real
  telemetry wins whenever it exists. Outside demo mode behavior is unchanged.
- character/brain.py: live AI context now uses canonical Daily Fight, Weekly
  Campaign, rolling level, current scoring Activities and strongest
  game_analytics association. Legacy goal/task/energy values are no longer the
  brain's definition of "good"; `_archive/memory.py` remains for older narrative
  history. Offline fallback behavior remains unchanged.
- ARCHITECTURE.md + NEXT_CHAT_PROMPT.md: updated to make this pre-design
  functional state explicit and preserve the next-chat chain.

Did NOT touch: `core/` in any way. The person did not authorize Layer 1 work
and none was necessary. SHA-256 verification after the build matched every
`core/*.py` hash captured before the session byte-for-byte.

What changed and why:
The previous v7.42 backend already had the scoring muscle, but the person
couldn't meaningfully validate a live Ghost, weekly campaign, records, level
math or correlations from a screen that still looked like the older 0% /
energy app. This build deliberately brings steps 2-7 forward enough to SEE:
Arena competition, history, high scores, rolling progression, weekly closure
and behavior analysis. The goal is now to fight actual integration/edge bugs
from use, then redesign the presentation without reopening fundamental score
architecture.

Synthetic mode is intentionally isolated rather than a one-off mock screen:
seeded XP goes through the normal ledger/query path, so Daily Fight, Weekly
Campaign, Hall of Fame, level rating and Calendar all consume it exactly like
real history. Analytics fixtures are isolated because inserting fake rows into
real telemetry tables would make cleanup unsafe. Menu > Synthetic Demo History
is the intended first-click demonstration path; Clear is designed to remove
only the fixture.

Tested:
- Full-project AST syntax sweep: 52 Python files, 0 syntax errors.
- Isolated 28-day demo fixture: generated 1,033 canonical-format synthetic XP
  events in the test run; Daily Fight produced a real same-time matchup,
  Weekly Campaign produced current vs equivalent prior-week totals and player
  rows, Hall of Fame identified best day/week, Weekly Closure produced a full
  7-player completed-week result, rolling level produced a nonzero tier/rating,
  and game_analytics returned strong ranked associations from 28 days.
- Demo clear removed all 1,033 tagged fixture XP rows and all fixture features.
  Separate safety regression: seeded a genuine manual 77-XP event BEFORE demo,
  ran demo seed+clear, confirmed the real event and exact real daily score were
  still present afterward.
- Headless tkinter test under Xvfb (Linux with minimal stubs solely for the
  Windows-only `win32gui` import): instantiated the complete Arena against demo
  history, toggled Daily/Weekly, and opened Records, Level Details, Weekly
  Closure, Insights, Raw Backend Snapshot, Calendar, scored day detail and XP
  Performance Chart without UI exceptions. Captured a preview to visually
  inspect layout; the plain structure is readable and exposes all intended
  systems. Windows-specific tracking behavior itself was not simulated.
- `character/brain.py` offline fallback still returns normally after context
  refactor.
- Every `core/*.py` SHA-256 hash unchanged from pre-work capture.

Left for next session: person should run `2026-08-14-e` on Windows and FIRST
use Menu > Synthetic Demo History > Seed / Reset 28-Day Demo. Click through
Daily/Weekly Arena, Records, Level, Calendar/day history, Weekly Closure,
Performance and Insights. Send screenshots and any confusing math/behavior or
runtime errors. Fix genuine bugs in `game_engine`/bindings where they belong.
Once the person accepts this functional information architecture, the next
large phase is the visual redesign toward the dark Battle Pacer / avatar /
Activity Forge reference — replace delivery widgets/styles aggressively, but
keep the existing canonical engine contracts.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire
DEVLOG before editing; never read/share `secrets.json`; keep `core/` frozen
unless the person explicitly authorizes Layer 1; add a NEW entry here (never
rewrite history) and update NEXT_CHAT_PROMPT.md after meaningful work. Tell the
person directly that both handoff files were updated before ending the session.

## 2026-08-14 -- V1 game backend: XP ledger, live Ghost, campaigns, records, rolling levels, analytics
Requested by: person approved the self-competition direction and explicitly
asked to build the backend "muscle" now, with presentation/polish later. They
also asked that the project's built-in handoff system keep being updated so
future AI sessions know exactly what changed.

Touched:
- shared/db.py: additive canonical game storage. New `scoring_activities`,
  immutable `xp_events`, and `game_state` tables + indexes and storage APIs.
  XP reversals are append-only rows pointing at the original event; historical
  scoring events are never silently deleted/re-written. Added `close()` for
  isolated tests/tools. Existing telemetry/revenue/note tables were not
  changed.
- shared/game_engine.py (new): complete backend contract for the simplified
  product direction. Three Activity kinds (`repeatable`, `once_daily`,
  `timed` with XP/hour), roster create/update/deactivate/sync, exact event
  recording + undo, daily totals/timelines/activity breakdowns, live daily
  Ghost at the SAME CLOCK TIME seven days earlier, current-week vs prior-week
  Campaign at the equivalent point in the week, per-day player breakdown for
  the week/team metaphor, record/high-score calculations, historical record
  day/week flags, daily and weekly win streaks, day/calendar summaries, and
  `dashboard_snapshot()` as one future-UI read contract.
- shared/game_engine.py level engine: 14-day rolling level rating using
  `exp(-0.10*d)` decay, V1 5-tier thresholds (Recruit/Operative/Specialist/
  Commando/Sentinel), 85% demotion floor, 48h At-Risk grace, and 1.5x comeback
  credit after demotion. Important design separation: battle/high-score
  `score_xp` always stays the exact configured number; comeback only boosts
  `level_xp`, so a 500-XP booking remains 500 in every Ghost/high-score race.
  If the app was closed while a level decayed below its floor, the engine scans
  missed day boundaries so the 48h grace keeps running instead of restarting
  on reopen.
- shared/game_engine.py migration: first startup copies the transitional v7.41
  manual Activity roster once. If a v7.41 item is already checked today, that
  earned score is inserted into the new ledger without awarding legacy XP a
  second time. Automatic xp_triggers and unrelated old character bonuses are
  deliberately NOT imported into the new battle score.
- shared/game_analytics.py (new): pure-Python analysis layer that treats the
  person's canonical XP score (or a named Activity such as Booked Job) as the
  outcome and computes Spearman/rank associations against observed signals:
  arrival time, first scored action time, tracked minutes, drift %, input
  engagement, Sales/Focus/Comms/Break category minutes, and revenue. It never
  awards or changes XP; default minimum is 7 tracked days and output says
  explicitly that association is not causation. This resolves the earlier
  "how does AI know what good means?" problem by letting the person define
  value through Activity XP and letting analytics only look for predictors.
- main.py: build tag -> 2026-08-14-d; imports/initializes game_engine after
  db.init. The Activity area is still deliberately unpolished but now actually
  drives the new ledger: repeatable rows have +1, once-daily rows have Done,
  timed rows have +15m, and rows with score have an undo control. Activities
  editor accepts `R | XP | name`, `D | XP | name`, `T | XP | name`, while old
  `XP | name` stays compatible as repeatable. Deleting an Activity definition
  only deactivates it; past earned history stays intact. Current-day manual
  events are mirrored into legacy progression only so the old character UI
  continues moving during the transition; the SQLite game ledger is canonical.
- check_game_engine.py (new): no-score-write diagnostic that prints the exact
  `dashboard_snapshot()` plus analytics readiness from the local database.
- ARCHITECTURE.md + NEXT_CHAT_PROMPT.md: updated to make game_engine the
  canonical scoring backend and explain the remaining transitional/legacy UI.

Did NOT touch: core/ in any way. Verified every core/*.py SHA-256 hash before
and after this work; all are byte-for-byte unchanged. The person did not
authorize Layer 1 work and none was needed.

Tested:
- full-project AST syntax sweep: 51 Python files, 0 syntax errors.
- repeatable Activity can score multiple times and quantity >1 correctly.
- once-daily Activity rejects a second completion until its first event is
  reversed; then it can be completed again.
- timed Activity prorates XP correctly (120 XP/hour -> 60 XP for 30 minutes).
- undo appends an exact negative reversal and restores day/activity totals.
- daily Ghost fixture: at 3:00 PM current day was 710 XP vs ghost 1,000 XP,
  while the ghost's 4:00 PM +500 event remained hidden until its historical
  time; ghost final was 1,500.
- weekly fixture: equivalent-point Campaign correctly produced current 1,710
  vs prior-week ghost 1,500, gap +210, with five Mon-Fri player rows.
- roster sync preserves Activity IDs/history while editing XP/type and only
  deactivates removed definitions.
- records/calendar/day-summary contracts exercised successfully.
- rolling level crossed Level 2 from fresh XP; after a long no-score gap the
  engine inferred the missed below-floor period, demoted one tier after the
  grace had effectively elapsed, activated comeback state, then confirmed a
  100 battle-XP action remained exactly 100 score XP while receiving 150 level
  XP credit.
- game_analytics synthetic 8-day fixture produced Spearman -1.0 for the
  intentionally injected pattern "earlier first scored action -> higher output"
  and also worked with a named Activity as the target.
- no `secrets.json` exists in the packaged project/work tree.

Left for next session: person should run build 2026-08-14-d and test the crude
Activity controls with real actions. The backend muscle for the Battle Pacer
is now present; the next large body of work should be DELIVERY: replace the
legacy 0%/energy-heavy first screen with a UI that reads
`game_engine.dashboard_snapshot()` (Daily Fight <-> Weekly Campaign, live
Ghost bar, records/surge, level status, Activity Forge cards), and surface
`game_engine.day_summary()` inside Calendar. Do not duplicate battle/record/
level math in tkinter -- UI should consume the engine. Existing background
insight/character integrations can be revisited after the person validates
this scoring model on real data.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire
DEVLOG before editing; never read/share secrets.json; keep core/ frozen unless
the person explicitly authorizes Layer 1; add a new DEVLOG entry (never edit
old entries) and update NEXT_CHAT_PROMPT.md after meaningful work.

## 2026-08-14 -- Backend-first cleanup: manual Activities + unified Calendar
Requested by: person shared the battle-pacer / Activity Forge mockup as the
long-term visual target, but explicitly said to build backend first and
listed the current product cleanup: remove Daily Recap, standalone Daily
Notes, Plan Tasks, Goal Progress, Goals, XP Triggers, Today's Suggestions,
and the whole goal/projection section from the first page; rename Video
Memories to Calendar and put daily notes inside each calendar day; keep
Performance Chart and Integrations; replace Plan Tasks / XP Triggers with a
manual task + XP checkbox system so the computer does not guess completion.

Touched:
- main.py: main-page Goal/Lifestyle/Mission/money prediction and Today's
  Suggestions surface removed. TASKS became ACTIVITIES with an Edit button.
  Menu now exposes only Activities, Calendar, Performance Chart, and
  Integrations. Old Plan Tasks off-task AI guessing cadence disabled. Old
  automatic XP-trigger scheduler disabled. Calendar renamed and day-detail
  now includes daily notes beside hourly history + videos. BUILD_TAG bumped
  to 2026-08-14-c. Old removed panels/functions are retained as unreachable
  code for now rather than destructively deleting rollback paths.
- shared/data.py: historical tasks storage now behaves as a persistent manual
  Activities roster. Activities carry forward day to day, only checkmarks
  reset at midnight, and `custom_xp` is now correctly preserved by
  `set_tasks()` (it was previously stripped on every save/toggle).
- character/progression.py: added deterministic `award_activity_xp()` and
  `remove_activity_xp()`. Manual checklist XP is exact: an activity set to 50
  adds exactly 50, with exact reversal on uncheck. Existing `award_xp()` and
  its multipliers/bonus-roll behavior are unchanged for other game events.
- shared/db.py: added `log_note_for_day()` and `days_with_notes_in_month()` so
  any calendar date can hold notes and note-bearing days can be marked.
- character/energy.py, character/brain.py, shared/score.py: visible/context
  terminology aligned from old "tasks/plan" wording to manual Activities.
- ARCHITECTURE.md and NEXT_CHAT_PROMPT.md: updated to describe the active
  product path and this review checkpoint.

Did NOT touch: core/ in any way. The person did not authorize Layer 1 work,
and none was needed.

What changed and why: this deliberately removes inference from the new XP
checklist. The user defines an Activity and its XP; the user's checkbox is
the source of truth. The old automatic shared/xp_triggers.py remains in the
source tree for rollback/reference but is not visible or scheduled. The old
Goal Progress / Daily Recap / standalone Daily Notes / Goals code is likewise
left unreachable for now so cleanup is reversible while the person reviews
this intermediate build.

Tested: (1) configured Activities preserve custom XP through save/toggle and
carry to a new day with done=False; (2) 50 manual Activity XP adds exactly 50
and unchecking subtracts exactly 50; (3) a note can be written to an arbitrary
calendar date and that day is returned by the month-note marker query; (4)
full-project Python syntax sweep passed. Also tested that changing a checked
activity's configured XP does not corrupt reversal: the originally awarded
amount is stored and unchecking removes exactly that amount. A full `import
main` runtime smoke test is not possible in this Linux sandbox because the
Windows-only `win32gui` dependency is absent; this is an environment limit,
not a syntax failure.

Left for next session: person should run build 2026-08-14-c and decide what
else to remove/change before visual polish. After cleanup is accepted, the
battle-pacer / week-vs-week + day-vs-day comparison backend remains the major
next feature, followed later by styling toward the supplied mockup.

Handoff rule for future AI sessions: read ARCHITECTURE.md and this entire
DEVLOG before editing; never read/share secrets.json; keep core/ frozen unless
the person explicitly authorizes Layer 1; add a new DEVLOG entry (never edit
old entries) and update NEXT_CHAT_PROMPT.md after meaningful work.

## 2026-08-14 -- XP triggers: clarified manual vs automatic, added real automatic detection
Requested by: person correctly pushed back on two real usability
problems with the trigger system from the last session: (1) it
wasn't clear that note_keyword only detects a word if the person
physically types it -- they were picturing something that detects the
activity itself; (2) the revenue field asking for "0" to mean "any
amount" is backwards and unintuitive.

Touched:
- shared/xp_triggers.py: new `category_minutes` trigger type -- fully
  automatic, no typing required. Reads shared/day_breakdown.py's
  already-categorized hourly data (Sales/Hiring/Design/Comms/Focus
  Work) and fires when total minutes in a chosen category reach a
  threshold that day. This is the real answer to "how does it know
  I'm cold calling" -- if cold-call activity falls under an app/window
  the tracker already categorizes as Sales, this fires with zero
  manual logging. `revenue_received` now explicitly treats a blank
  field as "any amount" (was already functionally true before via a
  parsing-failure fallback, now it's intentional and documented, not
  an accident). All four TYPES help strings rewritten to say plainly
  what data source each one reads and, for note_keyword specifically,
  state outright that it requires the person to type the word --
  can't detect the activity itself.
- main.py: edit dialog now shows a category dropdown (Sales, Hiring,
  Design, Comms, Focus Work) that appears only for category_minutes,
  and the "Condition value" field's label changes per type (e.g.
  "Word/phrase to look for" vs "Minimum $ (blank = any payment)" vs
  "Minimum minutes") instead of a generic label -- so the field is
  self-explanatory without needing to read the help text first.
  Bumped BUILD_TAG to "2026-08-14-b".

Did NOT touch: core/, the three existing trigger types' actual
matching logic (note_keyword, focus_score_above, arrived_before --
only revenue_received's blank-handling and all four help strings
changed).

Tested: seeded real activity data, ran it through
day_breakdown.build_day_from_activity() (the real categorizer, not
synthetic), created a category_minutes trigger for "Sales" at a
15-minute threshold against 20 real minutes of Sales-categorized
activity -- fired correctly, exactly once, and a second call didn't
re-fire. Also tested a threshold set too high (999 minutes) against
the same data -- correctly did not fire, confirming no false
positives. Full-project syntax sweep -- clean.

Left for next session: the person should be told plainly (and was,
in chat) that note_keyword-type triggers are a logging habit, not
detection -- if they want more activities to auto-detect like cold
calling did, the path is expanding day_breakdown.py's
CATEGORY_KEYWORDS so more real apps/window-titles map to a
meaningful category, then a category_minutes trigger can watch it.
Standing priorities unchanged: the week-vs-week/day-vs-day comparison
layer is still the next major piece of the new roadmap; character/
brain.py's insight/ integration still open underneath that. See
NEXT_CHAT_PROMPT.md.

## 2026-08-14 -- Dynamic, menu-editable XP triggers
Requested by: person is pivoting away from goal-projection as the
headline feature toward a gamified score/comparison system. First
concrete piece: base XP should come from two sources -- automatic
(existing data like focus score) and custom-defined achievements --
and the custom ones must be fully editable from the menu, no code
changes ever required to add/remove/change one.

Touched:
- shared/xp_triggers.py (new): trigger definitions stored in
  xp_triggers.json (name, type, condition value, XP amount, active
  flag), edited entirely through the UI. Four trigger types, each
  reading a data source that already exists: `note_keyword` (a note
  that day contains a word/phrase), `revenue_received` (a payment of
  at least $X that day), `focus_score_above` (daily score reaches X),
  `arrived_before` (presence "arrived" event before a given time).
  `check_all(day)` evaluates every active trigger, awards XP for any
  that fire and haven't already fired that day (tracked in
  xp_triggers_fired.json so nothing double-fires), returns which
  fired. XP goes through the REAL `character/progression.py` system
  (`award_xp()`) -- same streak multipliers, variable bonus rolls, and
  daily-cashout mechanics as every other XP source in the app, not a
  parallel/separate score.
- main.py: new "XP Triggers" menu entry (SETTINGS) ->
  `xp_triggers_panel()` -- scrollable list of defined triggers (name,
  type + condition, XP value, active/inactive), Edit/Delete per
  trigger, "+ Add Trigger" opens `_xp_trigger_edit_dialog()` (name,
  type dropdown with live help text per type, condition value, XP
  amount, active checkbox). New `_schedule_xp_triggers()`, checked
  every 5 minutes (shorter than the other background jobs -- this is
  cheap local-DB-only work, and fast feedback matters more here since
  the whole point is XP landing soon after the person actually does
  the thing). Bumped BUILD_TAG to "2026-08-14-a".

Did NOT touch: core/, character/progression.py itself (reused exactly
as it already existed -- award_xp() was already a clean public API,
no changes needed to plug triggers into it).

Tested: created one trigger of each of the four types, confirmed none
fire against empty/non-matching data, seeded matching data for each
condition (a note containing the keyword, a revenue event, a daily
score above threshold, a presence "arrived" event before the target
time), confirmed all four fired correctly and exactly once. Confirmed
XP actually landed in the real progression system by checking
`daily_xp` before/after (went from 0 to 100 off a single 50-XP
trigger -- confirmed this reflects a real streak-multiplier/bonus-roll
interaction from the existing system, not a bug, by re-reading
progression.py's `award_xp()` logic). Called `check_all()` a second
time immediately after and confirmed nothing double-fired. Full-project
syntax sweep -- clean.

Left for next session: this is the "automatic base XP + custom
triggers" half of the person's new roadmap. Still to design/build:
the week-vs-week and day-vs-day comparison layer, and the delivery/UX
for it (the "beat last week's team" framing) -- see the multi-message
design discussion immediately before this entry for the shape of that.
Standing item unchanged underneath all of this: character/brain.py's
insight/ integration. See NEXT_CHAT_PROMPT.md (needs updating to
reflect this new roadmap direction).

## 2026-08-14 -- Fixed a real, confirmed contradiction: graph vs. stated projection disagreed
Requested by: person looked at their actual Goal Projection Graph and
pointed out, correctly, that the historical line was sitting AT/ABOVE
the target line near "today," while the app still said "5 years, not
enough evidence" -- a direct, visible contradiction that made the
whole feature look broken.

Root cause, confirmed with the person's own numbers before touching
code: `current_rate` (used for the "goal already met" check, and
displayed everywhere) was computed as `revenue_rate(days=30,
end_days_ago=0)` -- a FIXED 30-day-equivalent divisor, applied
regardless of how much real history exists. With only ~10 days of
actual tracked history, dividing the same total dollars by a full
30-day-equivalent factor instead of the real ~10 elapsed days made
current_rate come out roughly 3x LOWER than what
`daily_average_sequence()` (which the graph is built from, and which
divides by ACTUAL days elapsed) was showing for the exact same
underlying money. Concretely, for the person's real $1,989 total:
revenue_rate gave ~$2,019/mo, while the graph's own last point showed
~$6,055/mo -- two different numbers, both technically "correct" under
their own definitions, silently disagreeing with each other in the
same UI.

Touched: insight/projection.py -- new `_current_pace(sequence=None)`,
the single definition of "current rate" now used everywhere a rate
gets displayed or checked against the target: the last value of
`daily_average_sequence()`, exactly matching the graph. Both
`harsh_completion_projection()` and `light_completion_projection()`
now use this for their `current_rate` (display value) and their
already-met early-exit check.

Did NOT touch: `revenue_rate()` itself, or Harsh's own `rate_now`/
`rate_prior`/`growth_per_month` month-over-month comparison, which
still deliberately uses `revenue_rate(30, ...)` -- a fixed 30-day
window is the right tool specifically for a fair like-for-like
comparison between two time periods, even though (as this session
confirmed) it's the wrong tool for a single "what's my rate right
now" display number. This was a surgical fix to which metric backs
current_rate, not a rewrite of either lane's actual date math.

Tested: reconstructed the person's exact scenario (a ~$873 payment,
a ~$727 payment, ~10 days apart) and confirmed current_rate now
exactly matches the graph's last point ($4,870.58 both places) instead
of the old, silently-disagreeing lower number. Re-ran all three
previously-validated regression scenarios from earlier sessions
(clean 14-day growth, genuinely flat data, zero data) to confirm this
fix didn't disturb any of that already-tested behavior -- all three
still produce the same category of correct result as before (clean
growth now correctly triggers "already met" given the more accurate,
higher current_rate; flat data and zero data still correctly stay at
the honest cold-start placeholder). Full-project syntax sweep -- clean.
Bumped BUILD_TAG to "2026-08-13-d".

Left for next session: standing priority unchanged -- character/
brain.py's insight/ integration. See NEXT_CHAT_PROMPT.md.

## 2026-08-13 -- Clarity fix: debug view was showing $/mo-equivalent as if it were a real payment
Requested by: person saw "$26,574" in the debug output and reasonably
asked "when was there ever a $26,000 payment" -- not a math bug, but a
real display clarity problem that made a correct calculation look
alarming/wrong.

Root cause: `daily_average_sequence()`'s values (and everything
downstream of it -- fit_points, sequence_tail, the graph) are
monthly-EQUIVALENT figures: today's daily pace multiplied out to a
full month, which is the correct thing to compare against a monthly
target. But shown alone, with no raw dollar amount alongside it, a
$873 real payment on day 0 (873/day * 30.44 days-in-a-month = 26,574)
is very easy to misread as an actual $26k transaction. Confirmed the
exact arithmetic against the person's own screenshot: 26574.12 / 30.44
= 873.06.

Touched:
- insight/projection.py: new `daily_raw_amounts()` -- companion to
  `daily_average_sequence()`, returns the real, un-annualized dollar
  amount received each day. Deliberately a separate function rather
  than changing `daily_average_sequence()`'s return shape, since
  `light_completion_projection()`, the graph, and `_linear_fit()` all
  already depend on its exact (day, value) tuple shape -- safer to add
  a parallel view than risk a new bug modifying a function three other
  things already rely on. `light_debug_info()` now also returns
  `raw_amounts_tail`.
- main.py: the Debug Light Calc panel now shows both figures side by
  side, with an explicit explanation at the top of which is which
  ("$/mo equiv" = extrapolated monthly pace, NOT a real payment size;
  "raw $" = the actual amount received). Bumped `BUILD_TAG` to
  "2026-08-13-c".

Did NOT touch: core/, the actual projection math (unchanged --
purely a display/labeling fix, no change to what number gets computed
or compared against the target).

Tested: reconstructed the person's exact scenario (a ~$873 real
payment on day 0, a $500 payment on day 8) and confirmed
`raw_amounts_tail` correctly shows `(0, 873.06)` while
`sequence_tail` shows `(0, 26575.95)` for the same day -- and
cross-checked the exact division (26575.95 / 30.44 = 873.06) to
confirm the two views are showing the same underlying data through
two different, now clearly-labeled lenses. Full-project syntax
sweep -- clean.

Also worth recording: the previous entry's math (slope -983.4 on the
person's real 10-day window) was independently confirmed correct by
hand in chat before this session even started -- that result stands.
This entry only fixes how the underlying numbers are *displayed*, not
what gets calculated.

Left for next session: standing priority unchanged -- character/
brain.py's insight/ integration. See NEXT_CHAT_PROMPT.md.

## 2026-08-13 -- Debug tool: Light lane calculation, real numbers visible
Requested by: person confirmed (via the build-tag system from the
previous entry) they were genuinely on the new code, and Light still
showed 5 years on their real account data. At this point, continuing
to reconstruct guessed datasets and testing against those stopped
being useful -- reconstructed test data had already been shown
working correctly (12.0 months on a shape similar to theirs), so
either their real data has some different property my guesses
haven't captured, or there's a real remaining bug. Needed to see
their actual numbers, not another guess.

Touched:
- insight/projection.py: new `light_debug_info()` -- exposes exactly
  what `light_completion_projection()`'s calculation is looking at:
  total sequence length, how many days the 10-day window actually
  used, the exact (day, $/mo) points the trend line was fit through,
  the computed slope and intercept, and whether the slope came out
  positive. Not used by the projection itself -- purely diagnostic.
- main.py: new "Debug Light Calc" button next to "View Graph" in Goal
  Progress -> `light_debug_panel()`, plain selectable/screenshot-able
  text showing all of the above. Bumped `BUILD_TAG` to "2026-08-13-b"
  for this release.

Did NOT touch: core/, the actual Light lane math (unchanged from the
previous session's windowing fix) -- this session added visibility
into that calculation, not a new version of it. Whether the next step
is "confirm it's working, your real recent data just doesn't show
growth yet" or "there's still a real bug" depends entirely on what the
person's actual debug output shows -- deliberately did not guess
further or ship another speculative fix without seeing it.

Tested: ran `light_debug_info()` against the same reconstructed
decay-then-uptick dataset used in the previous two sessions -- output
correctly shows all 26 sequence days, correctly windows down to the
most recent 10, correctly excludes the window's first point (9 fit
points), and correctly reports a positive slope (+8.69) matching the
already-confirmed "12.0 months" result from `light_completion_projection()`
on the same data -- confirms the debug output accurately reflects the
real calculation, not a separate/inconsistent code path. Full-project
syntax sweep -- clean.

Left for next session: waiting on the person to open Goal Progress ->
Debug Light Calc on their real account and share what it shows. If
`slope_positive` is genuinely `false` or `null` on their real recent
10 days, the fix is working exactly as designed and the honest answer
really is "no detectable growth in the last 10 days yet" -- not a
bug. If the numbers look wrong in some other way once visible, that's
the next real thing to fix, informed by actual data instead of a
fourth guessed reconstruction. Standing priority otherwise unchanged:
character/brain.py's insight/ integration. See NEXT_CHAT_PROMPT.md.

## 2026-08-13 -- Added a build-tag system to stop stale-file confusion
Requested by: nothing directly requested, but prompted by a real
pattern across the last three fixes (Stripe "get" error, the first
Light-lane rebuild, and this session's window-size fix) -- each time,
the person's first report after a fix looked identical to before, and
it took a round of "did you actually replace the file and restart"
before confirming whether it was a stale build or a real remaining
bug. That back-and-forth is avoidable.

Touched: main.py -- new `BUILD_TAG` constant near the top (currently
"2026-08-13-a"), shown in the window titles of Goal Progress and the
Goal Projection Graph (the two places this exact confusion happened).
Convention going forward: bump `BUILD_TAG` any time a fix ships to
something the person needs to visually verify -- especially the
projection math, since that's what's been iterating fastest. The
person can now check "is this actually the new code?" by glancing at
a window title instead of manually diffing files or trusting a
restart happened correctly.

Did NOT touch: core/, the actual projection math (unchanged from the
previous entry -- this session was purely about the verification
problem itself, since the person reported "same exact thing" and then
"something is actually wrong" after multiple reinstalls, which needed
a way to conclusively separate "still-stale-files" from "genuine new
bug" before further debugging could be productive).

Also gave the person two direct, concrete checks in chat rather than
more guessing: (1) search insight/projection.py in a text editor for
the literal string "LIGHT_WINDOW_DAYS" -- if absent, the fix never
reached their machine, full stop; (2) delete every __pycache__ folder
in the project (core/, character/, shared/, insight/), not just the
one mentioned in the earlier Stripe troubleshooting -- Python can, in
some cases, keep running cached bytecode if a zip tool preserves
original file timestamps during extraction rather than setting them to
extraction time, which can fool Python's normal staleness check.

Left for next session: pending the person's answer on the two checks
above -- if LIGHT_WINDOW_DAYS truly is present and __pycache__ is
clean and the graph (now labeled with build 2026-08-13-a) still shows
the old numbers, that's a genuine bug in the new windowing code that
needs real investigation, not another file-replacement check. Standing
priority otherwise unchanged: character/brain.py's insight/
integration. See NEXT_CHAT_PROMPT.md.

## 2026-08-13 -- Fixed: Light lane still stuck at 5 years on real account data
Requested by: person shared an actual screenshot of their Goal
Projection Graph -- real Stripe data, visibly showing a clear recent
uptick curving back up toward the target near "today" -- but both
lanes still said "not enough evidence of a trend yet." Also asked
whether more Stripe/transaction history could be pulled in to help.

Root cause, found by reconstructing the exact shape visible in their
graph (an early payment causing a spike-then-decay, followed by a long
quiet stretch, followed by a genuine recent uptick) and reproducing
the same "stuck at cold-start" result locally: the previous fix (from
the last session -- excluding day 0 from the regression) was necessary
but not sufficient. Fitting one straight line through the ENTIRE
history since the first payment lets a long decay phase (the earlier
payment getting more diluted every quiet day) outweigh a real but
recent uptick in the least-squares fit, even with day 0 excluded --
confirmed directly by printing the actual sequence and running the
regression on paper before touching code.

Touched:
- insight/projection.py: `light_completion_projection()` now fits its
  trend through only the most recent `LIGHT_WINDOW_DAYS` (10) of the
  sequence, not the full all-time history -- still excludes that
  window's own first point when there's enough data to spare it (same
  edge-leverage problem as before, can recur locally). Chose 10 days
  by testing multiple window sizes (21/14/10/7) against three
  scenarios: the real decay-then-uptick shape (only 10 or 7 correctly
  detected the uptick; 14 and 21 still missed it), a clean growth
  case (all window sizes correctly detected it), and a genuinely flat
  case (all window sizes correctly stayed at zero slope, confirming
  the shorter window doesn't create false positives from noise).
- shared/stripe_sync.py: default `days_back` raised from 90 to 365 --
  addresses the person's direct question about pulling more Stripe
  history. 90 days may have been truncating real transaction history
  that predates when Stripe sync was first connected, starving both
  lanes (especially Harsh, which needs a genuine 60-day span to
  compare two 30-day windows) of data they should have had access to.

Did NOT touch: core/, harsh_completion_projection() (unchanged),
daily_average_sequence() itself (unchanged -- the fix is in which
slice of its output gets fit, not how the sequence is built), main.py
/ goal_graph_panel() (no changes needed -- it already just renders
whatever the projection functions return).

Tested: reconstructed a dataset matching the exact shape visible in
the person's screenshot and confirmed it reproduced "not enough
evidence" with the pre-fix code. Re-ran the same dataset after the
fix -- now correctly shows "12.0 months," a real, evidence-based
projection instead of the cold-start placeholder. Re-ran the earlier
sessions' clean-growth and flat-data test cases through the actual
fixed code (not just hand-checked math) to confirm the fix didn't
regress either of those -- clean growth still detected immediately,
flat data still correctly produces no false positive. Zero-data case
re-confirmed unchanged. Full-project syntax sweep -- clean.

Left for next session: unchanged priorities -- character/brain.py's
insight/ integration is still the standing top item. See
NEXT_CHAT_PROMPT.md. Worth knowing: `LIGHT_WINDOW_DAYS = 10` was
chosen empirically against these three test scenarios, not derived
from a formula -- if real usage over time shows it's too twitchy or
still too slow in other shapes of data, it's one constant to tune,
not a structural change.

## 2026-08-13 -- Rebuilt the Light lane (cumulative-trend regression) + goal projection graph
Requested by: person felt the goal projection "didn't feel good" --
even with real Stripe data flowing, Light was giving 5-year answers
that didn't update meaningfully for weeks. Worked through the design
together: Harsh stays exactly as-is (accurate, deliberately slow to
trust); Light gets rebuilt to react immediately, day by day, using a
different mechanism entirely -- fit a trend line through the
cumulative daily-average-so-far (which naturally gets pulled down by
zero-revenue days and smooths out over time) and extrapolate that
trend forward to the target. Also asked for a graph showing both
lanes visually.

Touched:
- insight/projection.py: new `daily_average_sequence()` -- one point
  per calendar day since the first-ever revenue event, each point
  being the cumulative average $/day up to that day (including zero-
  revenue days), converted to a monthly-equivalent figure. New
  `_linear_fit()` (plain least-squares, no dependency). Rewrote
  `light_completion_projection()` to fit a trend through that
  sequence and extend it to where it crosses the target -- updates
  every single day, even with no new payment, because the average
  itself moves. Removed the old half-window-comparison design and its
  now-unused constants (`LIGHT_FULL_TRUST_EVENT_COUNT`,
  `LIGHT_MIN_PERIOD_DAYS`) along with the evidence-count-based
  dampening that used to blend toward the 5-year placeholder even
  once real signal existed -- per the person's explicit ask for
  immediacy, once 2+ days of history exist the raw regression result
  is used directly, no artificial trust ramp.
- main.py: new `goal_graph_panel()` (Goal Progress -> "View Graph")
  -- hand-drawn Canvas chart (same style as the existing
  `show_chart()`, no charting library dependency): history as a solid
  line with dots, each lane's forward projection as a dashed ray to
  the target, a dashed horizontal target line, a "today" marker. A
  lane still sitting at the cold-start placeholder isn't drawn as a
  misleading line -- it's named in a caption underneath instead
  ("Harsh not plotted -- not enough evidence of a trend yet").

**A real bug caught mid-build, before shipping -- worth walking
through since it change how the final math works**: the first version
fit the trend through the *entire* cumulative-average sequence,
including day 0. Day 0 is always a single payment's raw, undiluted
value (averaged over just 1 day) -- and because it sits at the extreme
edge of the time range, it has outsized leverage on a least-squares
fit. Tested against a genuinely realistic 14-day growth pattern
(payments of $250, $300, $400, $450, $500, $600, clearly increasing
over time) and the fit came back with a NEGATIVE slope -- completely
wrong, and worse, silently wrong: it would have shown 5-years/"no
signal" for data that was obviously trending up. Diagnosed by printing
the actual sequence and hand-checking the regression math, found the
single-point-at-the-edge problem, fixed by excluding day 0 from the
fit whenever there are more than 2 points to spare (falls back to
using everything when there's too little data to exclude anything).
Re-tested the same 14-day dataset after the fix -- correctly detected
the upward trend and projected 4 days to the $5,000 target. Also
re-tested the person's own tiny worked example (one $250 payment,
two zero days, one $500 payment) both before and after the fix to
confirm it was really the day-0-exclusion that mattered, not
something else.

Did NOT touch: core/, harsh_completion_projection() (unchanged,
exactly as validated in earlier sessions), blended_completion_projection()
(unchanged logic, now averages the new Light output).

Tested extensively given how much this rebuild changed:
- Zero-data case still correctly returns the 5-year cold-start
  placeholder (confirmed unchanged).
- 14-day realistic growth pattern -- confirmed the pre-fix negative-
  slope bug directly (printed the actual regression numbers), then
  confirmed the post-fix positive slope and sensible 4-day projection.
- Person's own tiny 2-payment example -- confirmed it now shows real
  (if volatile) movement instead of silently falling back to 5 years;
  flagged directly to the person that small-sample volatility remains
  and is inherent to what was asked for (immediate results from very
  little data), not something further tuning should paper over.
- Simulated the graph's full data-preparation and coordinate math
  (not the actual tkinter Canvas rendering, which can't be tested in
  this environment) against real projection output -- confirmed no
  division-by-zero, sensible pixel coordinates across all 14 history
  points, correct upward-trending line, correct skip-and-caption
  behavior for the still-cold-start Harsh lane. Full-project syntax
  sweep -- clean.

Left for next session: unchanged priorities -- character/brain.py's
insight/ integration is still the standing top item. See
NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Root-caused and fixed the Stripe "get" sync error
Requested by: person reported the improved diagnostics (previous
entry) now showed "On charge ?: AttributeError: get" -- a real,
specific clue, not a guess.

Root cause, confirmed directly against the real installed `stripe`
library (v15.5.0), offline, without needing a live API call:
`stripe.StripeObject` (the base class for `Charge` and everything
else the SDK returns) does **not** implement a `.get()` method in
this library version. It has a custom `__getattr__` that, for any
unrecognized attribute name, tries to look that name up as a *data
field* and raises `AttributeError` with just that name if it isn't
one. So `charge.get("status")` doesn't call a dict-style getter at
all -- Python first has to resolve the attribute `charge.get` itself,
which fails and falls into `__getattr__("get")`, which finds no field
called "get" and raises exactly `AttributeError: get`. This is the
verbatim, fully-explained mechanism behind the original one-word
error.

**Verification approach**: constructed a real `Charge` object offline
via `stripe.Charge.construct_from({...}, "fake_key")` (no network
needed -- this builds a genuine SDK object from a plain dict) and
reproduced the exact same `AttributeError: get` locally before
touching any code. This confirms it wasn't specific to the person's
account, key, or network -- it's a property of this library version's
object model that the original code didn't account for.

Touched: shared/stripe_sync.py -- replaced every `charge.get(...)`
call with a new `_field(obj, key, default=None)` helper, which uses
bracket access (`obj[key]`, confirmed to work correctly on these
objects) wrapped in try/except for `KeyError`/`TypeError`, giving the
same safe-default behavior `.get()` was supposed to provide. Also
fixed the exception handler's own `cid = charge.get("id", "?") if
hasattr(charge, "get") else "?"` line, which had the identical bug
baked into the bug-reporting code itself (the `hasattr(charge, "get")`
check doesn't help, since `.get` failing is an `AttributeError` raised
*from inside* attribute resolution, not the absence of the attribute
in a way `hasattr` would catch cleanly here -- replaced with the same
`_field()` helper).

Did NOT touch: core/, secrets_store.py's `_verify_stripe()` (checked
-- it never inspects Balance object fields, just success/failure, so
it was never affected by this bug).

Tested: re-ran the exact offline reproduction from before the fix,
now passing -- `_field(charge, "status")`, `"paid"`, `"refunded"`,
`"description"`, nested `"billing_details"` -> `"name"` all return
correct values against the real constructed object. Tested a second
charge deliberately missing `description` and `billing_details`
entirely -- confirmed `_field()` returns `None` cleanly (falls through
to the "Stripe payment" default) rather than raising. Ran the full
per-charge processing block end-to-end against both real objects
(not the sync() function's network call, which still can't be
exercised in this sandbox, but every line of logic that touches a
charge object) -- correctly computed dollar amounts, descriptions,
and inserted both into revenue_events. Full-project syntax sweep --
clean.

Left for next session: person should click "Sync Now" again -- this
should now either succeed and report real payment counts, or surface
a genuinely new/different error if something else is also wrong
(permissions, key mode). Standing priority unchanged: character/
brain.py's insight/ integration. See NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Improved Stripe sync error diagnostics
Requested by: person clicked "Sync Now" on their real, live Stripe
connection and got "Sync error: get" -- an uninformative, unactionable
message. Could not be reproduced or fully root-caused in this
environment -- this sandbox's network egress cannot reach
api.stripe.com at all (confirmed in the original Stripe integration
session), so a real authenticated request against their actual
account was never something that could be tested end-to-end here.

Touched: shared/stripe_sync.py's sync() -- two changes, both about
making the *next* failure actually diagnosable instead of guessing at
this one blind:
1. Error messages now include the exception's class name
   (`f"{type(e).__name__}: {e}"`), not just `str(e)` -- some
   exceptions' `str()` is far less informative than knowing what kind
   of exception it was, which is likely why "get" alone was so
   useless.
2. Per-charge processing is now wrapped in its own try/except inside
   the loop, reporting exactly which Stripe charge ID triggered a
   problem if one does, rather than one malformed record producing an
   opaque whole-sync failure.

Did NOT touch: core/. Did not guess at and "fix" a specific root
cause, since none could be confirmed -- the honest move was better
diagnostics, not a speculative patch.

Tested: full-project syntax sweep -- clean. Simulated the per-charge
error-isolation path directly with a deliberately malformed charge
object (missing expected fields) -- confirmed it now reports
"On charge ?: KeyError: 'amount'" (specific and actionable) rather
than crashing uninformatively or silently. Could not test against a
real Stripe API error response (network-restricted sandbox, as noted
above) -- the exact original cause of "get" remains unconfirmed.

Left for next session: person should click "Sync Now" again with this
build and report the new, more detailed error message -- that will
almost certainly reveal the actual cause (a restricted key missing
"Charges" read permission specifically, and a live/test key mode
mismatch are the two most common real-world causes of Stripe API
errors, worth checking directly in the Stripe dashboard while
waiting). Standing items unchanged -- character/brain.py's insight/
integration is still the top priority; see NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Settings > Integrations panel (in-app API key management)
Requested by: person wanted API keys (Anthropic, Stripe, and future
ones like Whoop/Fitbit) manageable from inside the app instead of
`setx` in PowerShell -- paste, click submit, see a green connected
light -- designed so adding a new integration later doesn't need new
UI code.

Touched:
- shared/secrets_store.py (new): `INTEGRATIONS` registry (name,
  env var key, help text, optional `verify` function) -- the
  Settings panel loops over this list, so a future integration is one
  new entry here, not new UI code. `load_all()` reads secrets.json (if
  present) into `os.environ` -- called once, first thing, in
  `main()`, before anything that might need a key. `set_key()` writes
  to secrets.json AND sets `os.environ` immediately, so a saved key
  works right away, no restart. `clear_key()` removes one.
  `_verify_anthropic()` (tiny real `ai._ask()` call) and
  `_verify_stripe()` (`stripe.Balance.retrieve()`, a side-effect-free
  read) back the "Test Connection" buttons -- cheap, on-demand checks,
  not run automatically every time the panel opens.
- shared/stripe_sync.py: fixed a bug this surfaced -- `is_configured()`
  and `sync()` used to read `STRIPE_API_KEY` into a module-level
  constant once, at import time. That was fine when a key only ever
  came from a real environment variable set before the process
  started, but now that Settings can set a key live mid-session, a
  stale constant would have kept reporting "not connected" until an
  app restart, directly contradicting the "takes effect immediately"
  promise. Fixed to read `os.environ.get(...)` fresh on every call.
  Tested directly: saved a key via `secrets_store.set_key()` mid-
  session (no reimport, simulating what actually happens when someone
  uses the Settings panel) and confirmed the already-imported
  `stripe_sync` module picks it up immediately.
- main.py: new "Integrations" menu entry (SETTINGS section) ->
  `integrations_panel()` -- one card per registered integration:
  status dot (grey/green/red), name, help text, a masked paste-in
  field, Save/Test Connection/Clear buttons, scrollable so more
  integrations fit without the window growing forever. `main()` now
  calls `secrets_store.load_all()` as its very first action.

Did NOT touch: core/.

**A real bug caught and fixed before shipping, via direct testing of
the exact pattern**: the status-dot update function
(`set_dot(color)`) originally closed over the loop variables `dot`/
`dot_id` by name rather than capturing them as default arguments --
classic Python late-binding closure bug. Reproduced it directly in
the interpreter first (looping 3 fake "dots," confirming all of them
ended up reporting the LAST iteration's value), confirmed my actual
code had the same shape, then fixed it
(`def set_dot(color, dot=dot, dot_id=dot_id)`) and re-verified with a
4-integration simulation that only the card actually acted on updates
its own dot. Without this fix, every integration card's status light
would have silently controlled only the last-listed integration's
dot, no matter which card's Save or Test button was clicked --
exactly the kind of bug that looks fine on a code read and only shows
up when actually exercised.

Also removed a smaller loose end noticed while reviewing: an unused
`placeholder` variable that was computed but never displayed (masked/
dotted entry fields can't usefully show placeholder text anyway --
the status label already communicates whether a key is saved).

Tested: full-project syntax sweep -- clean. Full integrated flow test
of secrets_store.py end to end -- `load_all()` safely no-ops with no
secrets.json yet; `set_key()` takes effect immediately in the same
process; a simulated restart (env cleared, `load_all()` called again)
correctly restores the saved key from disk; `clear_key()` removes it
from both the environment and the file.

Security note carried into ARCHITECTURE.md: secrets.json contains
real API keys in plain text once any are saved -- same protection
level as a Windows environment variable, but a file that could get
swept into a zip by accident. Documented prominently for the person
and for any future AI session: never read, zip, share, or ask to see
this file's contents.

Left for next session: unchanged from before -- character/brain.py's
insight/ integration, the "Today" screen, and revenue-in-correlation-
engine wiring. See NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Stripe revenue sync (replaces note-based dollar extraction)
Requested by: person wanted "no BS" revenue data by connecting their
Stripe account directly, rather than relying on AI-guessed dollar
amounts parsed out of daily notes. Confirmed all client revenue runs
through Stripe (asked directly before building, since that fact
determines whether note-extraction needed to keep running alongside
Stripe or could be fully replaced).

Touched:
- shared/db.py: additive schema migration (`ALTER TABLE revenue_events
  ADD COLUMN source`, `... ADD COLUMN external_id`, both wrapped in
  try/except for "column already exists" so it's safe on every
  startup, old or new install). New `sync_stripe_event()` -- inserts
  a Stripe charge as a revenue event, idempotent (checks
  `external_id` first, returns False without inserting if already
  synced). `replace_revenue_events_for_day()` (the note-based path)
  changed to only ever delete/replace rows with `source='note'` (or
  NULL, for pre-migration rows) -- it can no longer touch
  Stripe-sourced rows even if both exist for the same day, closing a
  real double-delete risk before it could ever happen.
- shared/stripe_sync.py (new): `is_configured()` checks for
  `STRIPE_API_KEY` as an environment variable -- same pattern already
  used for `ANTHROPIC_API_KEY`, so the key is set once locally via
  `setx` in PowerShell and never touches a config file, this
  conversation, or anything shared. `sync(days_back=90)` pulls
  succeeded, non-refunded Stripe charges in that window and logs any
  not already synced. Degrades gracefully at every failure point (not
  configured, `stripe` package not installed, network/API error) --
  returns a plain dict with an error message rather than raising.
- insight/distiller.py: `build_daily()` now checks
  `stripe_sync.is_configured()` -- if true, note-based dollar
  extraction is skipped entirely (notes still get read for the
  written summary, just stop being a source of dollar figures).
  Stripe becomes the sole source of truth for revenue once connected,
  eliminating any double-counting risk between the two sources by
  construction rather than by reconciliation logic.
- main.py: new `_schedule_stripe_sync()`, same 15-minute recurring
  pattern as the day-breakdown refresh, started from `main()`. No-ops
  cheaply (without importing the `stripe` package at all) if not
  configured. Goal Progress panel gained a STRIPE section: connection
  status, a "Sync Now" button (runs in the background via the
  existing `run_bg()` helper, reports how many new payments got
  synced).
- install.bat: added `pip install stripe` as a soft-fail optional
  step, matching the existing pattern for `opencv` and `tkinterdnd2`.

Did NOT touch: core/.

**Verification approach for this one was more rigorous than usual**,
since it's the first integration touching a third-party financial API:
installed the real `stripe` package (v15.5.0) here and read its actual
source rather than trusting field names from memory -- confirmed
`stripe.Charge.list()`'s signature, confirmed `created={"gte": ...}`
matches the real `ChargeListParamsCreated` TypedDict exactly,
confirmed `auto_paging_iter()` exists, and confirmed every Charge
field used (`amount`, `created`, `status`, `paid`, `refunded`,
`description`, `billing_details.name`) against the actual generated
type stubs in the installed library, not assumed from general
Stripe API familiarity. Could not test an actual live API round-trip
-- this sandbox's network egress doesn't allow api.stripe.com, so a
real auth/fetch call was never exercised, only that the call
construction itself is valid Stripe SDK usage.

Also tested directly: the DB migration is idempotent (`db.init()`
called twice in a row doesn't crash); `sync_stripe_event()` correctly
dedupes on `external_id` (second call with the same ID returns False,
inserts nothing); confirmed `replace_revenue_events_for_day()` really
can no longer delete a Stripe-sourced row for the same day it's
touching (seeded one of each, ran a note-replace, confirmed the
Stripe row survived); confirmed `build_daily()` correctly extracts
from notes when `STRIPE_API_KEY` is unset and correctly produces zero
note-based revenue events when it's set, using the exact same code
path a real run would take. Full-project syntax sweep -- clean.

Left for next session: person needs to actually create a Stripe
restricted (read-only) API key and set `STRIPE_API_KEY` themselves --
instructions are in `shared/stripe_sync.py`'s module docstring and
surfaced directly in the Goal Progress panel's STRIPE section when
not yet connected. Once real Stripe data is flowing, the still-open
"wire revenue into the correlation engine" item (see earlier entries)
gets more valuable, since the evidence feeding it would now be fully
trustworthy. Still also open: character/brain.py's insight/
integration and the "Today" screen -- see NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Real hourly breakdown, continually live-updating
Requested by: person suggested tracking every hour and updating the
calendar after every hour elapses, for a full trail of everything
done -- discussed the tradeoffs first (raw table vs. pre-packaged
hourly documents; concluded the raw table stays, but a real hourly
*summary* pass makes sense), then asked to build it as continually
live.

Touched:
- shared/day_breakdown.py: replaced "deferred, synthetic only" with a
  real pipeline. `categorize()` -- flagged/drift rows (from
  core/tracker.py's already-tested drift detection) count as "Break"
  directly; everything else gets keyword-matched (`CATEGORY_KEYWORDS`,
  hand-tunable, checked in order) against process+title text into
  Sales/Hiring/Design/Comms/Focus Work/Other. Deliberately plain
  Python, not AI -- needs to run cheaply every ~15 minutes all day,
  and stays fully deterministic/testable. `build_hour_from_activity()`
  aggregates one hour's real `activity` rows into the same
  segments/label/summary/apps shape the synthetic generator already
  produced (zero UI changes needed). `build_day_from_activity()` does
  all 24 hours, idempotent -- always recomputes from the raw table
  rather than patching, so it can't drift out of sync.
  `has_real_activity()` and `refresh_today()` (convenience wrapper) new.
- main.py: new `_schedule_day_breakdown_refresh()`, called ~5s after
  startup and every 15 minutes thereafter via `root.after` (reschedules
  itself) -- runs the aggregator in a background thread each time.
  `_day_detail_panel()`'s empty-state now checks
  `day_breakdown.has_real_activity(day)`: real activity but no
  breakdown yet -> "Build from Activity Log" button; no real activity
  at all (day before the app ever ran) -> "Generate Preview Data
  (synthetic)" as before. A day currently showing synthetic preview
  data also now offers "Replace with Real Data" if real activity has
  since become available for it.

Did NOT touch: core/. `categorize()` reads `flagged` (set by
core/tracker.py) but doesn't change how or when that gets set.

**Two real bugs caught during testing, fixed before shipping:**
1. The SQL query in `build_hour_from_activity()` assumed a column
   named `proc` -- the actual `activity` table column (from
   `shared/db.py`'s schema) is `process`. Caught immediately on first
   real test run (`sqlite3.OperationalError: no such column: proc`),
   not by re-reading the schema first -- fixed and every subsequent
   test re-run from scratch to confirm.
2. Before writing that query at all, tested the underlying SQL pattern
   (`strftime('%H', ts, 'unixepoch', 'localtime')` for extracting a
   local-time hour from the stored Unix-epoch `ts`) directly against a
   throwaway in-memory SQLite database at known hours (9am, 2:30pm)
   before trusting it inside the real module -- confirmed correct
   local-time extraction rather than assuming SQLite's timezone
   handling matched what was needed.

Further tested: full pipeline against activity data seeded at
realistic polling density (one row every 5 seconds for a full hour,
matching how core/tracker.py actually logs) -- confirmed category
percentages and per-app duration-in-minutes came out exactly matching
the seeded 20/20/20-minute split (Sales/Design/Break), not just
plausible-looking. Confirmed `refresh_today()` is idempotent (repeat
calls produce identical output) and confirmed it silently replaces a
day's synthetic preview data with real data the moment real activity
exists for that day -- no manual action needed for *today*
specifically (the manual "Replace with Real Data" button is for past
days the timer doesn't touch). Full-project syntax sweep -- clean.

Left for next session: `CATEGORY_KEYWORDS` is a first-pass, hand-
written guess at useful buckets/keywords -- expect it to misclassify
some real activity at first (an app used for multiple purposes, like
Gmail for both sales and general email, can't be told apart by app
name alone) and to need tuning once the person is looking at real
data instead of synthetic. Still open: the "Today" screen and
character/brain.py's insight/ integration -- see NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Fixed: hourly history couldn't scroll, and used military time
Requested by: person could not scroll the hourly history list to see
the rest of the day, and wanted 12-hour time instead of 24-hour.

Root cause of the scroll issue: a `Scrollbar` was wired up correctly,
but nothing bound mouse-wheel events to the canvas -- in tkinter,
adding a scrollbar does not make the mouse wheel do anything by
itself, that has to be bound explicitly. Dragging the thin scrollbar
thumb directly would have worked, but that's not what anyone tries
first, so functionally this read as "can't scroll."

Touched: main.py -- `_day_detail_panel()`'s hourly-history canvas now
binds `<MouseWheel>` while the cursor is over the list
(`canvas.bind_all` on `<Enter>`, `canvas.unbind_all` on `<Leave>`, the
standard tkinter pattern for this -- scoped so it doesn't hijack
scrolling anywhere else while the window is open). Also switched every
hour label -- the row list, the popup title, and the popup's time-range
header -- from `f"{h:02d}:00"` (military) to `timeutil.to12(...)`, the
same 12-hour formatter already used elsewhere in the app for schedule
blocks, instead of writing a second one-off formatter.

Did NOT touch: core/, shared/day_breakdown.py (no data-shape changes,
purely a display fix), shared/timeutil.py (reused as-is, not modified).

Tested: full-project syntax sweep -- clean. Verified `timeutil.to12()`
against the full boundary set (00:00, noon, 23:00, etc.) directly --
confirmed midnight correctly renders "12:00 AM" and noon "12:00 PM"
(the two cases most likely to be wrong in a hand-rolled 12-hour
converter, which is exactly why this reused the existing helper
instead of writing a new one). Could not test the actual scroll
interaction or visual rendering -- no display in this environment, as
with every tkinter change this session.

Left for next session: unchanged from before -- real activity-based
categorization to replace the synthetic hourly generator, the "Today"
screen, and character/brain.py's insight/ integration. See
NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Daily hourly-history breakdown, integrated into the calendar
Requested by: person shared a screenshot of an hourly-history +
activity-breakdown UI (not asking to replicate the visual polish,
which they acknowledged is beyond tkinter -- asking for the same
*functional* shape). Wanted it integrated into the video calendar:
click a day, see hourly blocks of what was mostly done, click an hour
for an app-level breakdown, videos below. Explicitly asked for
synthetic data on a sample day first to preview before the app
generates this automatically for real days. Also clarified: the
hourly breakdown should eventually be app-generated automatically,
but videos must stay person-uploaded only, never auto-captured.

Touched:
- shared/day_breakdown.py (new): storage + synthetic generator.
  `synth_seed_day(day)` produces deterministic (seeded by the date
  string, so re-generating the same day gives the same preview)
  fake hourly data -- per-hour category segments (Focus Work / Break /
  Sales / Hiring / Design / Comms), an optional tag label when one
  category dominates an hour, and a per-app percentage/duration
  breakdown. `CATEGORY_COLORS` defines the palette. Deliberately
  synthetic-only for now -- real categorization of actual
  `shared/db.py` activity rows into these buckets is a real design
  decision (which categories, how an app/window maps to one) left for
  a future session once the person confirms they like this shape.
  Storage format is written to be identical regardless of source, so
  a real aggregator can replace `synth_seed_day()` later without any
  UI changes.
- main.py: `calendar_panel()`'s day-click now opens a new
  `_day_detail_panel()` instead of the old video-only panel --
  hourly history (scrollable, colored segment bar per hour, tag chip
  when applicable, click any hour to open `_hour_breakdown_popup()`
  showing that hour's summary and per-app proportional bars) on top,
  the existing video list/add-video section (unchanged logic, just
  moved into this same window) below. If a day has no hourly data
  yet, shows a "Generate Preview Data (synthetic)" button rather than
  auto-generating on every click -- the person controls when preview
  data gets created, since which day is "yesterday" depends on when
  they actually open the app, not on anything bakeable into this
  session's build.
  Old standalone `_video_day_panel()` removed (fully superseded).

Did NOT touch: core/.

Tested:
- Full-project syntax sweep -- clean.
- `day_breakdown.synth_seed_day()` tested directly: sensible-looking
  output across a full day, confirmed deterministic (same day seed
  gives identical data on repeat calls), confirmed `load_day()`
  round-trips exactly what was saved.
- **Bug caught and fixed before shipping**: the hour-row click
  handler originally did `(row,) + row.winfo_children()` to bind a
  click to the row and all its child widgets -- `winfo_children()`
  returns a `list`, and Python raises `TypeError` concatenating a
  `tuple` to a `list`. Caught by directly testing that exact
  expression in the interpreter (not by inspection), before it ever
  reached the person. Fixed to `[row] + row.winfo_children()`.
- Simulated every field-access pattern main.py's new code performs
  against real `synth_seed_day()` output (not just checking the
  schema on paper) -- confirmed no KeyErrors, confirmed segment bar
  widths sum correctly to the 140px bar width, confirmed every
  `label` value is a valid key in `CATEGORY_COLORS`.
- Could not test actual rendering, the scrollable-canvas behavior, or
  click interactions -- no display available in this environment (and,
  per the video-calendar session, tkinter itself isn't installed here
  at all). The bar-width deferred-draw pattern in
  `_hour_breakdown_popup` (`win.after(10, draw_bar)`, needed because a
  freshly-created canvas reports width=1 before layout runs) is a
  standard tkinter workaround but the exact timing is a best-effort
  choice, not something verifiable without a real window.

Left for next session: the real activity-based aggregator (replacing
`synth_seed_day()`) is the natural next step once the person has
clicked around the synthetic preview and confirmed they like the
shape -- that work should read `shared/db.py`'s `activity` table and
decide how to categorize window/process names into the same category
set (or a revised one). Still also open: the "Today" screen and
connecting character/brain.py to insight/ -- see NEXT_CHAT_PROMPT.md
(unchanged by this session, still the standing next focus item there).

## 2026-08-05 -- Video memory calendar
Requested by: person wanted a calendar popup (current month, today
highlighted) where they can drop/upload a video into any day, to
browse back month to month as an archive of memories.

Touched:
- shared/video_memories.py (new): plain filesystem storage under
  `video_memories/YYYY-MM-DD/` -- no database. `add_video()` copies a
  source file in, rejects non-video extensions and missing files,
  auto-renames on filename collision instead of overwriting.
  `days_with_videos_in_month()` for the dot-marker on the calendar
  grid. `open_video()` launches the OS default player
  (`os.startfile`, Windows-only, same assumption the rest of the app
  already makes).
- main.py: `calendar_panel()` -- month grid (stdlib `calendar` module,
  imported as `pycalendar` to avoid any naming collision), Monday-first
  week layout, today highlighted with a distinct background, days with
  videos marked with a dot, prev/next month navigation. Click a day to
  open `_video_day_panel()` -- lists that day's videos with an Open
  button each, plus an "Add Video..." file-picker (stdlib
  `tkinter.filedialog`, always works, no extra dependency).
  New menu entry: "Video Memories" under DAILY.
- Optional real drag-and-drop via `tkinterdnd2` (not a stdlib
  package -- plain tkinter has no drag-and-drop at all). Imported in a
  try/except (`DND_AVAILABLE` flag) so the whole app still runs fine
  without it -- the file-picker button covers the same functionality
  either way. When available, the root window is created as
  `TkinterDnD.Tk()` instead of `tk.Tk()` (required for drop targets to
  work anywhere in the app), and the day panel registers itself as a
  drop target. install.bat updated to attempt
  `pip install tkinterdnd2` as a soft-fail step, matching the existing
  pattern used for the optional opencv dependency.

Did NOT touch: core/.

Tested: full-project syntax sweep -- clean. Functionally tested
`video_memories.py` directly: adding videos, filename-collision
auto-rename (confirmed a second same-named file gets suffixed, not
overwritten), rejection of non-video extensions and missing source
files, and month-scanning for the dot markers -- all correct.
Separately tested the calendar grid math itself (stdlib `calendar`
module output, today-highlight detection, video-dot placement,
month/year navigation wraparound at both Jan->Dec and Dec->Jan
boundaries) -- all correct. Could not test actual tkinter rendering or
drag-and-drop interaction -- this sandbox has no display and, it turns
out, no `tkinter` module installed at all (confirmed while testing
this feature). To compensate, verified the `tkinterdnd2` API usage
(`DND_FILES`, `TkinterDnD.Tk`, `drop_target_register`, `dnd_bind`,
`event.data`) directly against that package's installed source code
rather than trusting it from memory -- every name and call pattern
used in main.py matches the real library exactly.

Left for next session: none critical. Still open from before: the
"Today" screen and connecting character/brain.py to insight/ -- see
NEXT_CHAT_PROMPT.md.

## 2026-08-05 -- Added NEXT_CHAT_PROMPT.md (paste-to-continue handoff)
Requested by: person wanted a message they could paste directly into a
brand new chat to onboard the next AI instantly, on top of the
DEVLOG/ARCHITECTURE system already in place.

Touched: new `NEXT_CHAT_PROMPT.md` at the project root -- a short,
reusable message the person copies and pastes as their first message
in any new chat. It tells the new AI to read ARCHITECTURE.md and
DEVLOG.md in full, restates the core/ freeze rule up front, and
carries a "CURRENT FOCUS RIGHT NOW" section that gets updated at the
end of every session (same discipline as DEVLOG entries) so it never
goes stale. Updated `DEVLOG.md`'s own instructions to tell future AI
sessions to keep this new file current too, not just the log itself.
Cross-referenced it from `ARCHITECTURE.md`.

Current focus set in NEXT_CHAT_PROMPT.md: build a "Today" screen --
this came out of the person naming the real source of their
frustration this session: not that the backend lacks data, but that
almost everything already computed (colored documents, notes,
suggestions, goal progress) has no single place in the UI where a
human can actually see it. Nothing new to compute -- this is purely
about surfacing what already exists. After that, the standing next
item is still: character/brain.py doesn't read any insight/ pipeline
data yet.

Did NOT touch: core/, or any other code this session -- this was
purely a handoff/documentation addition.

Left for next session: build the actual "Today" screen described
above (see NEXT_CHAT_PROMPT.md for the exact spec), then connect
character/brain.py to the insight pipeline.

## 2026-08-05 -- Three-lane projection (harsh/light/blended) + click-to-edit for lifestyle/mission
Requested by: person felt pure-accuracy projections were "robotic,"
wanted a second, more responsive/optimistic lane alongside the
realistic one, averaged together, switchable with buttons. Also asked
for the Lifestyle and Mission header labels to be click-to-edit the
same way the money line already is, and asked whether that poses any
problems for reaching the AI.

Touched:
- insight/projection.py: refactored the single revenue projection into
  three: `harsh_completion_projection()` (unchanged logic from last
  session -- realistic, full 30-vs-30-day-prior window comparison,
  full trust at 10 sales), `light_completion_projection()` (new --
  compares a recent time-window against the window immediately before
  it, both windows sized to half of whatever history exists, floored
  at 3 days -- responsive enough to produce a real number from just 2
  sales, full trust at 3 sales), `blended_completion_projection()`
  (new -- averages the two lanes' dates in days-out terms).
  `revenue_completion_projection()` kept as a backward-compatible
  alias for harsh.
  **Bug caught during testing, fixed before shipping**: the first
  version of the light lane split events into two equal-count halves
  and computed each half's rate independently, floored at a fixed
  window -- with exactly the person's own example (2 sales, 1 day
  apart), both halves had identical single-event amounts and identical
  floored windows, so their rates came out equal and growth computed
  to exactly zero, silently falling back to the 5-year placeholder
  instead of showing movement. Caught by testing that exact scenario
  before considering it done, not by inspection. Fixed by switching to
  a time-window comparison (current window vs. immediately-prior
  window of the same size) instead of an event-count split -- this
  correctly puts both close-together sales in the "recent" window
  against an empty "prior" window, producing a real, strongly positive
  signal. Re-tested the same scenario and four others (0 sales,
  already-exceeded target, no target set, 12 sales over 2 months) --
  all behave sensibly now.
- main.py: `goal_progress_panel()` rebuilt with a Blended/Harsh/Light
  button switcher -- click any button, the projection and its
  evidence/confidence detail update in place. Header's completion line
  (`refresh_static()`) now shows the Blended lane as the headline
  number, harsh and light stay one click away. `edit_text_field()`
  (new, generic) added -- both `self.lifestyle` and `self.mission`
  labels are now click-to-edit, same interaction pattern as the money
  line from last session. Confirmed and explained to the person that
  this poses no wiring problems: every AI prompt already reads
  `data.load()` fresh on each call (distiller's `_goal_line()`,
  shared/ai.py's context building), so an edit here reaches the AI on
  its very next call automatically.

Did NOT touch: core/.

Tested: full-project syntax sweep -- clean. Re-verified all three lane
functions exist at module level after the refactor (learned this
lesson the hard way two sessions ago with build_weekly). Ran the
person's exact scenario (2 sales, 1 day apart) before and after the
light-lane fix, confirmed the bug and the fix. Tested no-target,
goal-already-exceeded, and a realistic 12-sales-over-2-months scenario
across all three lanes -- harsh and light converge to similar
high-confidence answers once there's ample real data, as intended.
Ran an integrated simulation of the exact calls main.py's
goal_progress_panel and edit_text_field make, including confirming a
saved mission edit shows up immediately in both `data.goal_context()`
and `distiller._goal_line()`.

Left for next session: none critical.

## 2026-08-05 -- Fixed: revenue projection didn't update same-day
Requested by: person logged a $500 sale via Daily Notes and the
projected completion date didn't move, asked if it only updates after
the data has "been in the system for a while."

Root cause: revenue extraction only ran inside `distiller.build_daily()`,
which `insight_schedule.py` only calls for *yesterday* -- and only
checks once, at app startup. So a sale logged today wouldn't get
extracted into `revenue_events` until tomorrow's app launch treats
today as "yesterday." A real design gap, not intended behavior.

Touched: main.py's `notes_panel()` -- each note submission now also
triggers `distiller.build_daily(today)` in the background (via the
existing `run_bg()` helper, same pattern used elsewhere in the file),
then calls `self.refresh_static()` once it completes, so the header's
money line and completion line update right after you hit Add, not
the next day. Small status label added ("Checking for revenue /
updating projection...") so it's visible something's happening during
the few-second AI call.

Did NOT touch: core/, or any of the projection math itself -- the fix
is entirely about *when* the existing pipeline runs, not what it
computes.

Tested: simulated the exact flow (log_note -> build_daily(today) ->
revenue_completion_projection()) end to end. Confirmed evidence_count
and current_rate update immediately (0 -> 1 event, current_rate
correctly reflects the $500 logged). Also surfaced, and explained to
the person directly, a second honest limitation this exposed: the
*date* itself won't move on a single early sale, because
`revenue_completion_projection()` requires a real comparison between
the last-30-days window and the 30-60-days-ago window before it will
compute a growth-based date -- with only one recent event, that prior
window is empty, so it correctly stays at the cold-start placeholder
rather than extrapolating from a single data point. This means the
date realistically won't start moving until roughly a month of
consistent sales-logging has passed. Deliberately left as-is rather
than adding a faster-reacting fallback (e.g. total-logged /
time-since-first-sale), since that would swing to overconfident
estimates from tiny sample sizes -- flagged to the person as an option
to revisit if they'd rather trade reliability for faster movement.

Left for next session: none critical. The growth-rate-fallback
tradeoff above is a live option if the person decides they want it.

## 2026-08-04 -- Revenue-based goal completion projection
Requested by: person got stuck trying to edit the "0/mo -> 8000/mo"
line (no UI path existed after the Money panel was removed two
sessions ago) and wanted a projected completion date for the revenue
goal -- explicitly simple math, no CRM/recurring-client modeling: sell
more this month, hit the target sooner. Also wanted a deliberate
cold-start UX: show a far-out placeholder date (5 years) when there's
no data yet, and have it visibly move closer to reality as sales get
logged, formatted as "today -- duration -- completion date."

Touched:
- shared/db.py: new `revenue_events` table + `log_input` (kept from
  last session) + `replace_revenue_events_for_day()` (idempotent --
  deletes then re-inserts a day's events, so re-running the daily
  distiller never double-counts) + `revenue_events_since()` /
  `revenue_events_all()`.
- insight/distiller.py: `build_daily()` now also calls
  `_extract_revenue()` on that day's notes -- a conservative AI pass
  that only pulls dollar amounts clearly tied to money actually
  received (a sale, a payment), explicitly told to skip expenses,
  hopes, and hypothetical prices. Offline fallback (no API key) is a
  plain regex for "$123" patterns -- flagged in comments as
  approximate, since it can't tell hypothetical prices from real
  income the way the AI reading intent can.
- insight/projection.py: new `revenue_rate()` (monthly-equivalent rate
  from revenue events in a trailing window) and
  `revenue_completion_projection()` -- computes month-over-month
  growth in the rate itself (rate now vs. rate 30 days prior) and
  linearly projects to the target, matching the person's own framing
  exactly ("sell xyz more this month, you're at xyz/mo in N months").
  Blends that computed date with a fixed 5-year cold-start placeholder,
  weighted by how many sales have been logged (full trust at 10) --
  intentionally not a statistical claim of accuracy at low evidence,
  a deliberate motivational product choice the person asked for
  explicitly. New `format_countdown()` renders the requested
  "2026-08-04 -- 1.6 years -- 2028-01-30" format, switching to months
  or days when the span is short enough to make years unreadable.
- main.py: `money_line` is now click-to-edit (`edit_goal_amount()`,
  bound directly to the label -- this fixes the "I don't know how to
  change that" problem) and displays a live-computed current rate
  (from `revenue_rate()`) against the target, instead of the old
  static, unreachable `current_monthly` field. New `completion_line`
  in the header shows the projected date at a glance. `goal_progress_panel()`
  now shows the revenue-based projection (with evidence count and
  confidence) above the existing efficiency-trend section from last
  session -- both stay, since they answer related but different
  questions (behavioral pace vs. actual revenue pace).

Did NOT touch: core/. No changes to drift detection or anything else
in core/ this session.

Tested extensively given how much new math this introduces:
- Revenue extraction tested end-to-end with real example text ("Got a
  payment from that Billy client... profited $250") -- correctly
  extracted; also confirmed the offline regex fallback's known
  weakness (it also picked up a hypothetical "$300" mentioned in
  passing) -- documented as expected/flagged behavior of the no-API-
  key path only.
- Confirmed `replace_revenue_events_for_day()` is idempotent --
  re-running `build_daily()` on the same day does not duplicate
  events.
- Tested `revenue_completion_projection()` against four scenarios: (1)
  zero data -- exactly the 5-year placeholder; (2) 5 sales with a
  computable growth trend -- confirmed the blended date and "medium"
  confidence by hand-checking the arithmetic; (3) 12 sales (over the
  full-trust threshold) -- confirmed "high" confidence and near-full
  convergence to the computed date; (4) two edge cases: target already
  exceeded, and no target set -- both return clean, honest messages
  instead of broken math.
- Ran an integrated simulation of exactly what `refresh_static()` and
  `edit_goal_amount()` compute/do, using the same module aliases
  main.py uses, confirming the full chain works together.

Left for next session: nothing critical. Possible future refinement,
not requested yet: the growth-rate calculation currently compares only
two 30-day windows (now vs. 30 days prior), which is the simplest
version of "trend" and matches what was asked for -- a longer-window
regression could smooth out noisy months later if it turns out to
bounce around too much in practice.

## 2026-08-03 -- Goal-aware analysis, input-activity intake, goal-pace projection
Requested by: person wants three things working well: (1) a single
goal that every piece of advice is actually evaluated against, (2)
maximum data intake short of camera-based tracking, (3) analysis that
answers "when will I hit my goal" and "what do I need to do."

Touched:
- core/inputmon.py: now logs `input_activity` (keyboard/mouse active/
  idle, already computed live, previously thrown away every 2s) to
  db.py every poll. This is a core/ file -- flagged explicitly per the
  standing freeze rule, touched only because the person explicitly
  asked to maximize data intake. Change is additive only (one new
  logged value); the idle-detection logic itself is untouched.
- shared/db.py: new `input_activity` table + `log_input(active)`.
- insight/raw_stats.py: `day_stats()` now includes `engagement_pct`
  (% of input-activity samples that were active) -- a signal
  independent of which window is focused, catches "app open but not
  actually being used" vs. real hands-on-keyboard time.
- insight/distiller.py: every prompt (daily summary, weekly summary,
  weekly correlations, suggestions) now opens with a `GOAL:` line read
  fresh from `data.load()["mission"]` each call, and suggestions are
  now explicitly instructed to connect to that goal, not just describe
  general productivity. Fixed a real bug from an earlier session found
  while making these edits: `build_weekly()` had lost its `def` line
  in a prior str_replace and had become dead code trapped inside
  `datetime_strptime()` -- silently broken (swallowed by
  insight_schedule's try/except, never surfaced). Fixed and re-tested
  end-to-end with synthetic data before continuing.
- insight/projection.py (new): `efficiency_trend()` reads the existing
  `daily_scores` history (already computed by shared/score.py from
  task completion + drift behavior -- no new metric invented) and
  reports a 7-day vs. prior-7-day trend, pure Python. `goal_projection()`
  combines that trend with the primary goal's `target_date` (from
  `data.load()["goals"][0]`, if set) to report days of runway left and
  whether the trend is closing the gap -- deliberately does NOT invent
  a completion date from behavioral consistency alone when no real
  deadline is set; says so plainly instead.
- main.py: new `goal_progress_panel()` (menu: Goal Progress, under
  ANALYZE) displays the above, read-only.

Did NOT touch: core/ files other than the single additive line in
inputmon.py described above. No change to drift detection, escalation,
red-line handling, or anything else in core/.

An honest limitation, not solved today: `goal_projection()` measures
*behavioral efficiency* (task completion, drift, engagement) against a
*date*, not actual business outcomes (revenue, sales). The Money/
Pipeline panels that would track real outcome numbers were disabled
in an earlier session at the person's request, so `current_monthly`
in data.json is now static. A true dollar-based ETA would need that
input active again, in some form -- flagged for the person rather than
silently re-adding a panel they explicitly asked removed.

Tested: full-project syntax check across every file -- clean.
`efficiency_trend()` and `goal_projection()` tested against 20 days of
synthetic trending-upward scores (correctly detected "improving") and
against a real target_date 45 days out (correctly computed runway and
framed it honestly). Both no-history and no-target-date fallback
messages tested directly. All three new/changed insight/ imports
(`store`, `projection`) confirmed to resolve under the exact same
sys.path setup main.py uses.

Left for next session: the Money/outcome-data question above. Also,
`engagement_pct` is captured but not yet surfaced anywhere in a
summary sentence or suggestion -- it's in raw_stats output and
available to distiller's prompts, just not specifically called out
yet.

## 2026-08-03 -- Daily notes, daily suggestions, one-goal header, menu cleanup
Requested by: person wanted (1) a one-way daily notes box (no AI
response, just a record), (2) 3 evidence-based suggestions regenerated
daily, shown at the top in place of a multi-goal display, with a
single goal above them, and (3) the menu decluttered: remove Business
Metrics, Personal Metrics, Money, XP History, Wins, Block Sites, and
Reset Chat History (chat is gone, so this no longer makes sense).

Touched:
- shared/db.py: new `notes` table + `log_note(text)` / `notes_for_day(day)`.
- insight/raw_stats.py: `day_stats()` now includes a day's notes.
- insight/distiller.py: `_daily_summary()` now weighs notes heavily
  when present (the person's own account outweighs the raw numbers);
  new `build_suggestions(for_day)` -- 3 suggestions grounded in
  yesterday's colored doc + the latest weekly correlations + notes,
  every suggestion traceable to actual evidence, offline fallback
  included; new `_offline_suggestions()` for when there's no API key.
- insight/store.py: `save_suggestions()` / `load_suggestions()`, stored
  under `insight_data/suggestions/YYYY-MM-DD.json`.
- insight/insight_schedule.py: `_maybe_suggestions()` builds today's
  suggestions once per day at startup (gated so it doesn't regenerate
  on every relaunch, only once nothing exists yet for today).
- main.py: header now reads "GOAL" above the single mission line (the
  existing `d["mission"]` field -- interpreted as "the one thing we're
  focusing on" per the request), with a new "TODAY'S SUGGESTIONS"
  section below it, populated by `refresh_suggestions()` from
  `insight_data/`. New `notes_panel()` -- a plain text box + Add
  button + scrollback of today's notes, writes straight to
  `db.log_note()`, no AI call anywhere in the path. `show_menu()`
  rewritten: removed Business Metrics, Personal Metrics, Money,
  Pipeline (already off), XP History, Wins, Block Sites (menu copy
  only), Reset Chat History; added Daily Notes. `main()` schedules one
  delayed `refresh_suggestions()` call ~20s after startup so the
  background-generated suggestions appear without needing some other
  action to trigger a refresh.

Did NOT touch: core/. The XP bar and level display (`self.xp_lbl`,
top of dashboard) are untouched -- only the separate "XP History"
detail panel is gone. The Block Sites lock icon in the bottom bar
(`self.block_btn`) is untouched and still fully functional -- only the
duplicate menu entry calling the same function was removed. Automatic
win-logging (`data.add_win()`, triggered by SOS success, red-line
recovery, brain ACTION tags) is untouched -- only the manual "Wins"
viewing/adding panel is gone from the menu.

Interpretation flagged for the person to confirm: "one goal at the
top" was implemented using the existing `d["mission"]` field (already
a single string, already displayed prominently) rather than the
separate `d["goals"]` list (a different, older multi-goal structure
used only inside the still-present "Goals" menu panel and in AI
context). If the person actually meant the goals list should collapse
to one entry, or that the Goals panel itself should be simplified or
removed, that's a follow-up, not done here.

Tested: full-project syntax check across every `.py` file -- clean.
Functionally tested notes end-to-end (`db.log_note` ->
`raw_stats.day_stats` -> `distiller.build_daily`'s offline summary
correctly wove in two real example notes -- "Got a sale." and "Felt
very scared of cold calling but did it anyway." -- alongside the
numeric stats). Functionally tested `build_suggestions()` offline
against a seeded day with a redline event and a 2pm/3pm focus dip --
correctly produced grounded suggestions citing the specific hour and
event count, not generic advice. Confirmed `store` (aliased
`insight_store` in main.py) imports cleanly under the same sys.path
setup main.py uses.

Left for next session: the flagged interpretation question above.
Also, suggestions currently only regenerate once per calendar day
(at first startup that day) -- if the person wants them to refresh
mid-day as new notes come in, that would need a small change to
`_maybe_suggestions()`'s gating condition.

## 2026-08-03 -- Removed the chat box from the UI entirely
Requested by: person wanted the typed chat box physically gone from
the dashboard ("delete the whole chat thing at the bottom"), not just
disabled -- while keeping SOS and everything else exactly as-is.

Touched: main.py -- removed the conversation Text widget (`convo_log`),
the reply row (entry box, send button, mic button), and the on-startup
restore-history-into-the-log loop. Removed `convo_send` and `_do_chat`
(the functions that drove typed replies) entirely. Rewrote `convo_add`
to no longer touch a Text widget -- it still records conversation
history and calls `voice.speak_voice_only()`, which is what actually
produces the floating bubbles. Fixed `reset_chat`, which previously
manipulated `convo_log` directly. Removed the now-unused `import chat`
at the top of the file.

Did NOT touch: core/, SOS, the bubble system (`voice.bubble_q` ->
`tick()` -> `show_bubble()`), or any other panel. Confirmed the bubble
system is a separate, independent mechanism from the removed log --
every place that used to call `convo_add()` (drift escalation, SOS,
greetings, check-ins) still calls it exactly the same way, and still
gets spoken + bubbled. Visually, nothing about the character changed;
only the persistent scrollback box and typed-input row at the bottom
are gone. `_direct_add_task` and `chat_window` (a second, unrelated,
already-unreferenced embedded chat toggle) were left in place as
harmless dead code -- neither was reachable from any button before or
after this change.

Tested: full-project syntax check (`ast.parse` on every `.py` file) --
clean. Grepped for every remaining reference to `convo_log`,
`reply_entry`, `convo_send`, and `_do_chat` after the edit -- zero
matches outside of explanatory comments, confirming nothing dangling.

Left for next session: none from this change specifically. The
standing next task is still: wire `character/brain.py` to read
`insight_data/` instead of `_archive/memory.py`.

## 2026-08-03 — Disabled everything except core, character, and the insight pipeline
Requested by: person wanted the app stripped down to "its core, which
is the back end data collection and analysis," plus the character —
everything else disabled for now, chat specifically called out as
something they don't want.

Touched: `main.py` — disabled the free-form chat input (entry box,
send button, mic button all set to `state="disabled"`, layout
untouched); commented out `show_menu()` entries for Habits, Voice
Journal, Pipeline, Insights + Correlations, Strategy, Financial
Projection, Weekly Review; unscheduled the auto-export startup call.
`character/brain.py` — removed imports and context-building for
`lifedata`, `strategist`, `finance`, `pipeline`, `stats_engine`,
`journal` (all now-unreachable via UI, was dead weight in every AI
call). Every underlying function these buttons called still exists in
`main.py` as dead code — nothing was deleted, only disconnected.
Reversal instructions are inline as comments at each disabled site.

Did NOT touch: nothing in `core/`. The reactive speech log
(`convo_log`/`convo_add`, used by drift/escalation/SOS/greeting lines
via `_brain_respond`) was deliberately left untouched and fully
functional — only the manual typed-reply path was disabled. Also
untouched: Plan Tasks, Daily Recap, Business/Personal Metrics, Money,
Performance Chart, XP History, Goals, Wins, Block Sites, Reset Chat
History — none of these depend on `_archive/`, so they were left live.

What changed and why: the person's stated target shape is core (layer
1) + character (progression/energy/voice/brain reactions) + the
insight pipeline (layer 2/3), with everything else off until it's
wanted back. Disabling was chosen over deleting so every one of these
features can be restored by uncommenting a single line, in case any of
it turns out to be wanted later, once it can be rebuilt cleanly on top
of the simplified base.

Tested: full-project syntax check (`ast.parse` on every `.py` file) —
clean. Ran `brain.respond()` end-to-end in an isolated copy after the
trim (offline fallback path, no API key in this environment) — returned
a normal response, confirming the trimmed context-building didn't break
anything.

Left for next session: the person wants to integrate XP/character with
the insight pipeline next. That means wiring `character/brain.py` to
read `insight_data/daily/*.json` and `insight_data/weekly/*.json`
(currently it still reads the old `_archive/memory.py`-based context —
that's the one archived import brain.py still has, kept because nothing
replaces it yet). The UI menu still has commented-out lines for
Habits/Journal/Pipeline/Finance/Insights/Strategy/Weekly Review if any
of those turn out to be wanted back later — uncomment the specific
`mbtn(...)` line in `main.py`'s `show_menu()`.

## 2026-08-03 — Built the insight pipeline (white/colored documents)
Requested by: person chose to build the data pipeline first, out of
the two options (character layer vs. data pipeline), from the
"layer system" discussed across earlier sessions — raw logs distilled
daily/weekly into short readable summaries that will eventually feed
the character.

Touched: new `insight/` folder — `raw_stats.py` (pure-Python stats,
no AI), `store.py` (JSON file storage for colored docs), `distiller.py`
(daily/weekly summaries + grounded correlations, AI with offline
fallback), `insight_schedule.py` (startup trigger, idempotent). Added
one generic read-only `query()` helper to `shared/db.py` (append-only,
nothing existing changed). Added `insight` to the `sys.path` bootstrap
list in `main.py`, and added a 5-line background-thread call in
`main()` right after `db.init()` — wrapped in try/except, cannot block
or crash startup.

Did NOT touch: nothing in `core/` was changed. The `main.py` edit was
additive only (one new thread start call) — no existing GUI/tkinter
code was touched, so the "don't edit UI blind" caution from the reorg
session doesn't apply here; this was verified safe to reason about
without a live display.

What changed and why: this is the pipeline half of the two-tier system
from the original planning conversations — "white documents" (raw
per-second logs, already existed in `witness.db`) now get distilled
into "colored documents" (short JSON summaries in `insight_data/`).
Kept deliberately simple per the person's explicit request: numbers
always come from pure Python, the AI only explains them, and every
weekly "correlation" must cite the specific days that support it —
`evidence_count` is counted in Python from those citations, not
self-reported by the AI, and confidence is categorical (low/medium/
high), not a fabricated decimal. Tested end-to-end with 10 days of
synthetic activity data before inclusion: confirmed `raw_stats.py`
correctly detects an injected pattern (an afternoon focus slump), and
confirmed `insight_schedule.run_if_due()` is idempotent and safe to
call on every app startup.

Left for next session: `character/brain.py` does not read
`insight_data/` yet — it still only reads `memory.build_context()`
(the `_archive/memory.py` version, mostly recaps/check-ins/scores).
Once the person has watched the colored documents accumulate for real
days and is happy with what they say, wire `brain.py` to read the
latest `insight_data/daily/*.json` and `insight_data/weekly/*.json`
instead of (or alongside) the old memory module. Also: no UI yet to
browse colored documents (the "brain tab" from the original idea) —
right now they're just JSON files on disk, readable in a text editor.
The person indicated character-layer work is the other major piece
still to come, once the pipeline has run for a while.

## 2026-08-03 — Added check_insight.py (manual verification)
Requested by: person had no way to confirm the insight pipeline was
actually working, since `insight_schedule.py` only checks for
*yesterday's* data at startup — nothing visible until a full day had
passed.

Touched: added `check_insight.py` at the project root — standalone,
run with `python check_insight.py` from the project root any time.
Builds today's colored document immediately from whatever's already
logged, using the real `raw_stats`/`distiller` code (not a separate
test path), and prints both the Layer 2 numbers and the Layer 3
summary to the console. Safe to run repeatedly; only touches
`insight_data/`.

Did NOT touch: core/, main.py, or anything else. Fully standalone.

Tested by seeding a throwaway copy of the pipeline with synthetic
"today" activity and running the script exactly as a user would —
confirmed it correctly reports low-sample-count days as "not enough
data yet" and produces a real colored document once enough samples
exist.

## 2026-08-03 — Reorganized into sections (core / character / shared / archive)
Requested by: person wanted the codebase, which had grown "very
complicated," sectioned off so Layer 1 (drift protection) stays
untouched while everything else gets simplified over time, and wanted
a way for future AI chat sessions to pick up work without losing
context.

Touched: physically moved files into `core/`, `character/`, `shared/`,
`_archive/` folders (see `ARCHITECTURE.md` for exactly which file went
where and why). Added a small `sys.path` bootstrap to the top of
`main.py` (and to `_archive/camtest.py`, `_archive/chattest.py` since
they can be run standalone) so every existing `import` statement in
every file keeps working unchanged — no import lines were rewritten
anywhere. Created `ARCHITECTURE.md` and this file.

Did NOT touch: no logic was changed in any file. `core/` (layer 1 —
camera, presence, inputmon, tracker, vision, blocker, nuclear, trail,
phone, patterns, difficulty) was moved as a folder but its contents are
byte-for-byte identical to before. Verified every file still parses
correctly after the move.

What changed and why: the person wanted the codebase organized so it's
easy to reason about across future sessions, with the working
drift-protection system protected from accidental edits while the
messier "layer 2/3" features (chat, weekly review, finance/pipeline
tracking, habits, journal, correlations, stats engine, export) get
pulled out of the way without being deleted outright, in case parts are
wanted back later.

Left for next session: `main.py` still contains the UI panels/buttons
that call into `_archive/` modules (chat reply, strategist button,
habits panel, finance panel, pipeline panel, journal button,
correlations button, weekly review, export) — see the exact line
numbers and function list in `ARCHITECTURE.md` under "Known loose
ends." These weren't removed in this pass because they live inside a
95KB tkinter file that can't be safely edited and tested without a live
display and webcam — better to strip them out live, on the person's own
machine, one panel at a time, confirming layer 1 still behaves
identically after each removal. `character/brain.py` also still pulls
context from several archived modules (`strategist`, `finance`,
`pipeline`, `journal`, `stats_engine`, `memory`, `lifedata`) — once the
UI hooks above are gone, trim `brain.py`'s context-building to match.
The "gamified character" itself (`progression.py`, `energy.py`,
`voice.py`, `brain.py`'s reactive lines) is the part the person actually
wants developed further — it currently "needs a lot of work" per the
person, specifics not yet defined.

---
*(Next entry goes above this line, at the top of the Entries section —
most recent first.)*
