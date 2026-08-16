# WITNESS Qt build

Current Qt visual build: **2026-08-15-e / v7.52 Desktop Distribution Foundation**

## Desktop distribution / updater (v7.52)

The Qt shell can now be packaged as a per-user Windows desktop application. Release builds
use PyInstaller `onedir` + Inno Setup and install program files under
`%LOCALAPPDATA%\Programs\WITNESS`; personal state remains under `%LOCALAPPDATA%\WITNESS`.
A packaged build checks its configured public GitHub Releases channel shortly after launch
and every six hours. New stable versions surface as **UPDATE vX.Y.Z** in the top bar.
Update & Restart downloads off-thread, verifies the release SHA-256, exits, runs the installer,
and reopens WITNESS. Source/dev builds ship with a blank release repository and do not make
update-network requests.

Actual Windows binaries must be built on Windows. `.github/workflows/release-windows.yml`
provides the automated Windows build/publish path; `packaging/build_windows.ps1` is the local
Windows equivalent. Code signing is still pending before broad public distribution.

## Local profile boundary (v7.51)

Both `qt_main.py` and the legacy `main.py` now activate `profile_runtime.py` before
loading WITNESS data modules. On Windows all runtime history lives under
`%LOCALAPPDATA%\WITNESS`, not beside the application code. The Settings page shows
the local profile ID/data path, can open the data folder, and can stage an import from
an older WITNESS project folder for the next restart. Clean packages ship without
user databases/demo history. This is the prerequisite for a later installer/updater
that can replace program files without touching user progress.

Launch with `start_witness_qt.bat`. The original `start_witness.bat` remains the
known-good Tkinter fallback while full runtime migration is still pending.

v7.50 adds the first dedicated Character surface without changing canonical scoring:
- new **CHARACTER** page in the Qt navigation; the Arena rank emblem opens it too,
- interactive full-frame 2.5D/vector avatar: drag to rotate, wheel to zoom,
- level changes the avatar's visible armor/form while today's canonical XP charges
  its aura separately,
- selectable Training / Winter / Tropical / Desert / City Night environments;
  unlocks are based on peak level so a later demotion never takes an earned scene away,
- Winter includes snow/breath/shiver, Tropical has palms/ocean motion, Desert dust,
  City Night rain, and Training stays deliberately neutral,
- behavior-derived Attributes (Persistence, Discipline, Momentum, Production, Focus)
  are presentation-only evidence from existing WITNESS data and never award XP,
- Protection Shield progress requires monitored days without flagged drift, red-line
  or SOS breaches; first shield unlocks at 14 clean monitored days and strengthens
  at longer streaks,
- the unsolicited periodic sound reported in v7.49 is fixed: passive Ghost replay can
  still move/show a warning, but timer-driven Ghost lead changes are now silent.

The v7.48 performance rules remain mandatory: feedback first, no hidden-page rebuilds
on Activity clicks, stable Activity widgets, cheap live refreshes. The Character page
also has a cheap `live_refresh()` and only recalculates slower traits/shield when the
page is entered/refreshed.

`shared/character_engine.py` is a character **projection** over canonical game/telemetry
state, not a second scoring engine. `shared/game_engine.py` remains the source of truth
for XP, Ghost, records and levels. `core/` remains frozen.

The color rule remains strict: charcoal/white base, green for action/winning, red
for danger/losing, gold only for records/major milestones. Environment art may use
muted scene colors inside the avatar stage only.
