# WITNESS v2 — AI accountability coach

> **v7.56.0 Theme Evolution + Interactive 3D Lab:** the whole Qt shell now matures through
> three visual eras tied only to the canonical current Level: WILD (1-2), FORGED (3-4), NOIR
> (5-8). Character keeps the approved portrait art as default and adds an experimental true-geometry
> **3D LAB** with drag rotation, zoom, idle motion, stage styling, Core glow and Charge field. The
> procedural mesh is a performance/interaction prototype, not replacement final art. XP/Ghost/levels
> and Layer 1 are unchanged.

> **v7.55.2 Release Reliability Fix:** GitHub Actions now self-cleans the release checkout before validation/build, so stale root shadows from Windows folder merges cannot fail the release before cleanup runs. Product behavior is otherwise the v7.55 Completion Pass.
>
> **v7.55.0 Completion Pass:** Character now separates Daily Charge (outer aura) from an
> explicit user-controlled Core Reserve (inner chest glow), surfaces a strongest behavior
> Signature, and gives real form changes a restrained evolution reveal. Settings adds rotating
> local backups, full profile Export/next-launch Restore, crash recovery visibility, and a
> rerunnable first-run setup guide. Release cleanup now quarantines stale runtime leftovers
> automatically before validation. Canonical XP/Ghost/records/levels are unchanged from v7.54.

> **v7.54.0 Eight-Stage Progression + Character Alive V2:** canonical rolling levels now map
> one-for-one to Wanderer → Seeker → Apprentice → Builder → Disciplined Man → Operator → Elite →
> Sovereign. Manual Undo immediately reconciles false/test promotions, while ordinary decay still
> keeps the existing 85% floor + 48-hour grace. Character scenes add gentle parallax, breathing,
> fog/haze and cross-fades on top of the approved art.

> **v7.53.0 Character Art Progression V1:** the Character page now uses the eight approved
> original evolution artworks and a peak-Level-Rating journey from Wanderer to Sovereign.
> Existing installed users should receive this through the proven Update & Restart pipeline.

> **v7.52.2 updater verification:** publish this patch while v7.52.1 remains installed, then
> use WITNESS's own `UPDATE v7.52.2` -> Update & Restart flow. A short green
> `UPDATED TO v7.52.2` badge confirms the automatic restart reached the new build.


New in v2: voice + speech bubbles (mutable), goal/wins/money panels, focus
score + streaks, morning check-in, escalation ladder, deep work mode, SOS
button with your own videos, nightly recap that rewrites tomorrow's schedule.

## Upgrading from an older project-folder build
1. Extract the new WITNESS code and run `install.bat` if dependencies changed.
2. Launch `start_witness_qt.bat`. WITNESS now stores personal data in the Windows
   local profile folder instead of beside the code.
3. If you extracted the update into a separate folder, use **Settings → Local Profile
   → Import Existing WITNESS Folder**, choose the old WITNESS folder, then restart.
   If the new code was placed directly over an old folder and the local profile is
   still empty, recognized legacy data is migrated automatically.

## First 10 minutes in the app

On a genuinely new local profile, the Qt app opens a short setup guide:

1. Add a local name/callsign and a short mission (optional; no online account is created).
2. Choose/edit starter **Activities + XP**. WITNESS never guesses what deserves points.
3. Read the short Daily Fight / Weekly Campaign / Level explanation and enter the Arena.
4. Score real actions in Arena. After one week, the same weekday becomes the same-time Ghost.
5. Open **Character** to see Level/form, Daily Charge, Core Reserve, Shield and evidence-backed
   Attributes. Start Core Reserve only if you want that personal timer.
6. Open **Settings → Data Safety** any time to create a backup, export your profile, or stage a
   backup restore for the next launch.

Existing profiles with configured Activities are never forced through onboarding; Settings can
reopen the guide manually.

## Voice quality
Uses the free built-in Windows voice. To pick a less robotic one:
Windows Settings -> Time & Language -> Speech -> add voices.

## API key (strongly recommended for v2)
PowerShell:  setx ANTHROPIC_API_KEY "sk-ant-your-key"
Then reopen the app. Without it, WITNESS uses built-in lines and cannot
rewrite schedules or chat. With it: everything personalizes to your goals.
Typical cost: a few cents per day.

## Local profile / personal data (v7.51+)
WITNESS no longer stores personal history beside the program files. On Windows,
each Windows account automatically gets one anonymous local profile under:

`%LOCALAPPDATA%\WITNESS`

That folder owns `witness.db`, notes, videos, XP history, character state, settings,
insight files and other runtime data. A random local profile ID is generated on first
launch; there is no WITNESS username/password in V1. Different Windows accounts get
different databases.

This means future updates can replace WITNESS application files without replacing the
user's history. New distribution packages intentionally contain **no** database, demo
history, videos, notes, or API-key file. A brand-new user starts empty.

If upgrading from an older project-folder build, open **Settings → Local Profile →
Import Existing WITNESS Folder**, choose the old folder, then restart WITNESS. The
import runs before SQLite opens and copies the recognized legacy data into the isolated
profile. The old folder is not deleted.

API calls can still leave the machine when integrations are enabled. `secrets.json` is
currently stored locally in the profile and remains plain text; stronger Windows secret
protection is a later hardening step.

## Installed Windows app / updates (v7.52.1+)

v7.52 added the release machinery needed to stop replacing project ZIPs by hand; v7.52.1 hardens the first real installer build. The target
installed experience is: download `WITNESS-Setup.exe` once, install per-user under
`%LOCALAPPDATA%\Programs\WITNESS`, then let WITNESS check the published stable release
channel in the background. When a newer release exists, a compact **UPDATE vX.Y.Z** button
appears in the top bar. **Update & Restart** downloads the installer off the GUI thread,
checks its published SHA-256, exits WITNESS, replaces program files, and reopens the app.
The `%LOCALAPPDATA%\WITNESS` personal profile is outside the install directory and is not
part of the updater.

The source ZIP deliberately has no live update repository configured. The Windows release
workflow (`.github/workflows/release-windows.yml`) injects the repository into the packaged
build, builds the executable with PyInstaller on Windows, wraps it with Inno Setup, and
publishes `WITNESS-Setup.exe` plus its SHA-256 file to GitHub Releases when a matching
version tag is pushed. See `DISTRIBUTION.md`.

Before tagging a release, run `packaging\clean_repository.ps1` and then
`python packaging/validate_source_tree.py`. v7.55.2+ also runs the same cleanup automatically inside GitHub Actions before validation/build. v7.55+ quarantines known stale runtime leftovers
from a Windows folder merge to `%LOCALAPPDATA%\WITNESS\release-quarantine` automatically,
then hard-validates the source tree. It never reads `secrets.json` and never targets the real
active profile. The existing frozen smoke test and installed-program cleanup remain in force.

The installer is not code-signed yet; broad distribution should add a trusted Windows
code-signing certificate. Qt still does not start the complete Layer-1 runtime; packaging
does not change that architectural limitation.


## PySide6 visual frontend (v7.44+)

The new visual frontend is being migrated in parallel with the original
Tkinter runtime.

1. Run `install.bat` once to install dependencies including PySide6.
2. Double-click `start_witness_qt.bat` to open the new Arena UI.
3. `start_witness.bat` still launches the original Tkinter app and remains the
   full-runtime fallback while the migration is in progress.

Both frontends use the same WITNESS database/game backend. Do not run synthetic
demo seeding/clearing simultaneously from both windows.


### Current Qt state — v7.55.2

The approved responsive Arena/History/Progression/Character structure remains intact. v7.55.2 adds a self-cleaning GitHub Actions release checkout; the v7.55
keeps the eight-stage ladder and approved composite artwork, but makes the character-state model
clearer: **Level/form** is long-term evolution, **Daily Charge** is today's output and now drives a
restrained outer aura, **Core Reserve** is an explicit user-controlled 14-day timer driving the
inner chest glow, and **Protection Shield** remains the monitored clean-streak projection. Real
canonical form changes get a short evolution reveal; the strongest current evidence-backed trait
is shown as the Signature. Composite art still couples body + world per form, so independent
environments/360° remain a later layered/3D asset step.

Settings now includes **Data Safety**: seven rotating compact backups (startup rate-limited),
manual backup, full profile Export including media, staged next-launch Restore, crash/session
recovery notice and local crash reports. API secrets are intentionally excluded. A local-only
first-run guide helps a new profile define identity/mission and starter Activities without making
a cloud account or inventing XP.

The character layer does **not** change scoring. `shared/character_engine.py` only
projects canonical game/telemetry history into visual state; `shared/game_engine.py`
continues to own XP, Ghost, records and the eight-stage rolling level ladder. Fitness/body integration is
explicitly deferred.

The v7.49 random passive sound issue remains fixed: Ghost replay can advance visually
on the 2-second live timer, but passive Ghost lead changes no longer play a sound.
Sounds remain reserved for confirmed user actions and rare action-triggered milestones.

The v7.48 responsiveness rules remain in force: feedback paints first, hidden pages
refresh lazily, Activity cards update in place, and slow work does not run on the
+1/timer path. The original Tkinter app remains the full-runtime fallback while
Layer-1 tracking/voice/intervention migration is still pending.
