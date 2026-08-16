# v7.55.0 Completion Pass: Core, Safety + Onboarding

Current Qt build: **v7.55.0 / `2026-08-16-d`**. This pass finishes the main V1
quality-of-life systems around the already-proven Arena/Character loop without changing
canonical XP, Ghost, records or level math.

- **Core Reserve:** explicit 14-day Start/Reset clock independent of XP/Level/Shield. Reserve
  drives the inner chest glow; Daily Charge now drives a separate outer aura.
- **Character payoff:** canonical form changes get a restrained evolution reveal; strongest
  evidence-backed Attribute is surfaced as the current Signature.
- **Data Safety:** rotating transaction-consistent local backups, manual backup, full Profile
  Export, staged next-launch Restore, crash/session marker and local crash report folder. API
  secrets are excluded from backup/export/restore.
- **First run:** local-only 3-step onboarding for identity/mission, user-selected starter
  Activities and a short Ghost/Level explanation. Existing accounts are not forced through it.
- **Release hygiene:** `clean_repository.ps1` now quarantines known stale runtime leftovers out
  of a merged Git checkout before hard validation, so future releases should no longer require
  manual `Remove-Item` cleanup.
- **Sound:** a quiet Core cue is explicit-action-only. Passive timers still never make sound.

The Qt app still does **not** start the complete Layer-1 tracker/voice/intervention runtime.
That limitation is unchanged and must not be hidden by the completion/polish work.

# v7.54.0 Eight-Stage Progression + Character Alive V2

Current Qt build: **v7.54.0 / `2026-08-16-c`**. Canonical rolling levels now align one-for-one
with the approved Character journey: Wanderer, Seeker, Apprentice, Builder, Disciplined Man,
Operator, Elite and Sovereign at 0 / 5,000 / 12,800 / 24,100 / 39,200 / 55,000 / 75,000 /
100,000 Level Rating. The first five thresholds are unchanged.

Manual Undo is now treated as an explicit ledger correction: after a reversal, current and peak
level state are reconciled immediately from corrected XP history, so accidental/test promotions do
not linger through the normal 48-hour demotion grace. Ordinary performance decay keeps the existing
85% floor + 48-hour grace and comeback behavior.

Character Alive V2 remains intentionally 2.5D: approved composite art gets subtle pointer parallax,
breathing/camera drift, jungle fog/fireflies, city haze/rain, charge-responsive Core pulse, Shield
field, and smooth cross-fades between forms. No animation owns or invents XP.

# v7.53.0 Character Art Progression V1

Current Qt build: **v7.53.0 / `2026-08-16-b`**. The dedicated Character page now uses the
eight person-approved original character artworks: Wanderer → Seeker → Apprentice → Builder →
Disciplined Man → Operator → Elite → Sovereign. Evolution is projected from the permanent peak
of the existing rolling Level Rating and never changes XP/Ghost/records/game-level math.

The page is image-led rather than placeholder-vector-led: large full-frame art, subtle pan/zoom,
early-form fireflies, city rain, today's Charge pulsing the existing chest Core, Shield overlay,
and an eight-form journey strip. Earlier earned forms can be revisited as memories. Because the
current art is a composite of body + environment, these are stage chapters for V1 rather than
independent swappable environments. See `CHARACTER_ART.md`.

# v7.52.2 updater verification

Current Qt build: **v7.52.2 / `2026-08-16-a`**. This release intentionally changes almost
nothing in the product. When the installed updater relaunches WITNESS with `/updated`, the top
bar shows a green `UPDATED TO v7.52.2` badge for 12 seconds. Backend/game/runtime rules are
unchanged.

# WITNESS Qt build

Current Qt visual build: **2026-08-16-d / v7.55.0 Completion Pass: Core, Safety + Onboarding**

## Desktop distribution / updater (v7.52.1)

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


v7.52.1 hardens the first installer pipeline after the first real Windows release exposed
a stale-module collision. Release validation now rejects old root-level module duplicates,
PyInstaller resolves canonical section folders before the repository root, the frozen smoke
test waits for the GUI process and requires a post-shell marker, and Inno clears the old
program directory before installing a new build. Personal `%LOCALAPPDATA%\WITNESS` data is
not part of that cleanup.

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
