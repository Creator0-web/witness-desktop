# WITNESS v2 — AI accountability coach

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
- Goals button -> "Edit lifestyle / mission" -> write YOUR words.
- Add 3-5 goals (format: title | why | target date | stakes).
- Money button -> put in your real numbers. The dashboard gap line and the
  voice both use them.
- Drop 1-3 short videos into the sos_videos folder (mp4). Best one you can
  make: film yourself for 60 seconds telling future-you why this matters.
- Mute button before calls. Voice off, bubbles stay.

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

Before tagging a release, run `packaging\clean_repository.ps1` (for any checkout that ever
contained the old flat project) and `python packaging/validate_source_tree.py`. v7.52.1 also
uses a real wait/marker frozen smoke test and clears only the old installed program directory
on upgrade so stale Python modules cannot survive. Personal profile data is not deleted.

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


### Current Qt state — v7.52.1

The approved responsive Arena/History/Progression/Character structure remains intact. v7.52.1
keeps v7.51 per-Windows-user profile isolation and the desktop distribution/update foundation while preserving the v7.50 **Character** page: a full-frame interactive 2.5D avatar
(drag to rotate, wheel to zoom), level-driven visual evolution, daily-XP charge aura,
behavior-derived attributes, Protection Shield progress, and level-unlocked Training /
Winter / Tropical / Desert / City Night environments. The small Arena rank emblem
opens the Character page.

The character layer does **not** change scoring. `shared/character_engine.py` only
projects canonical game/telemetry history into visual state; `shared/game_engine.py`
continues to own XP, Ghost, records and rolling levels. Fitness/body integration is
explicitly deferred.

The v7.49 random passive sound issue remains fixed: Ghost replay can advance visually
on the 2-second live timer, but passive Ghost lead changes no longer play a sound.
Sounds remain reserved for confirmed user actions and rare action-triggered milestones.

The v7.48 responsiveness rules remain in force: feedback paints first, hidden pages
refresh lazily, Activity cards update in place, and slow work does not run on the
+1/timer path. The original Tkinter app remains the full-runtime fallback while
Layer-1 tracking/voice/intervention migration is still pending.
