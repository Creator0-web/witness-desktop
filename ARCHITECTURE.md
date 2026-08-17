# WITNESS — Architecture

Read this before touching any code. It tells you what's safe to change
and what isn't. If you are an AI assistant picking this project up in a
new chat: read this file and DEVLOG.md in full before writing anything.
(In practice, the person will usually paste the contents of
`NEXT_CHAT_PROMPT.md` as their first message, which already tells you
to do this — but read it in full regardless, don't skim.)

## The four sections

```
witness/
  main.py              entry point — run this. Stays at project root.
  core/                LAYER 1 — real-time protection. FROZEN. See below.
  character/           the persona/gamification layer. Active work area.
  shared/               utilities used by everything else.
  _archive/             quarantined layer 2/3 features. Not deleted, not wired
                        into the active UI conceptually — but see "Known
                        loose ends" below, they are not fully unplugged yet.
```

Nothing about Python's import system changed. `main.py` adds all four
folders to `sys.path` at startup (see the block right under the file's
docstring), so every `import x` line in every file still works exactly
as it did when everything was flat in one folder. You will never need to
rewrite an import statement because a file moved between these folders.


## PySide6 visual migration (v7.44+)

The project now has **two presentation entry points during migration**:

- `main.py` / `start_witness.bat` — original tkinter UI plus the proven full
  Windows runtime (tracking, voice, event handling). Keep this as the fallback
  until Qt reaches feature/runtime parity.
- `qt_main.py` / `start_witness_qt.bat` — new PySide6 presentation shell.
  `ui_qt/` contains visual components/pages only. It reads/writes the same
  `shared/game_engine.py` + SQLite contracts and must not invent a second score
  system.

Do not interpret "new frontend" as permission to rewrite `core/`. The Qt app
currently focuses on the game/delivery surface; full Layer-1 runtime migration
must be planned explicitly after the visual shell is proven.

Visual tokens live in `ui_qt/theme.py`. Current product direction intentionally
uses a restrained palette: charcoal neutrals, green primary, red only for
losing/danger, gold only for records/major victories.

**v7.56 visual-era contract:** the app may now visually mature with the canonical current Level,
but this is strictly presentation state. `theme.era_for_level()` maps Levels 1-2 to WILD, 3-4 to
FORGED, and 5-8 to NOIR. `ui_qt/shell.py` may read `game_engine.level_status()` to choose the QSS,
but theme code must never write progression state or calculate its own Level. Reapplying a theme
must not rebuild hidden pages or regress the v7.48 responsiveness rule. Semantic green/red/gold
meaning remains stable even when surfaces, border radius and decorative accent evolve.

**v7.56 3D-lab contract:** `ui_qt/character_3d.py` is an interactive software-rendered 3D
prototype (real mesh geometry + perspective + depth sorting) embedded behind a PORTRAIT / 3D LAB
toggle. It reads the same `shared/character_engine.py` state as the portrait and owns no gameplay
data. The approved composite art remains the default canonical visual. The procedural mesh is not
the production Character identity; if interaction proves valuable, replace only the rendering
asset/layer with one rigged identity-consistent GLB/glTF character and outfit variants. Keep
environments separate in that future asset pipeline so evolved forms can revisit earlier worlds.

As of **v7.55.0 / build 2026-08-16-d**, the Qt delivery layer has moved beyond a
one-screen preview into the character/emotional-reward phase:

- `ui_qt/arena.py` is the approved visual-structure path: stronger Battle Pacer,
  responsive Activity Forge (up to five cards across on wide screens), level/
  streak HUD, performance trend, insight and record chase. Styling should be
  refined here without moving score logic out of `game_engine.py`.
- `ui_qt/pages.py` History now reuses the existing canonical/local history
  sources instead of a Qt-specific database: `game_engine.day_summary()` for
  score/Ghost/XP timeline, `shared/day_breakdown.py` for hourly computer
  history, `shared/db.py` notes, and `shared/video_memories.py` videos. Calendar
  cells mark record days/weeks plus note/video presence. Day Detail has
  Overview / Computer / Notes / Videos tabs, and Notes/Video additions write to
  the same storage the old Tkinter Calendar uses.
- History now also has a second top-level lens, **Progression**
  (`ui_qt/progression.py`). It consumes `game_engine.progression_snapshot()` and
  offers **Current Level** (entry threshold becomes the visual baseline, next
  tier is the ceiling, 85% demotion floor remains visible as the danger zone)
  and **All Time** (complete rolling Level Rating with tier thresholds and
  milestones). The chart is delivery only; it does not recalculate or own the
  scoring rules.
- v7.47 deliberately adds *delivery feedback only*: `ui_qt/widgets.py` owns
  eased number/progress animations and the animated BattleBar; `ui_qt/arena.py`
  owns XP fly-ups, Ghost replay feedback and short transition banners;
  `ui_qt/shell.py` owns the brief page fade. These effects must always reflect
  values already confirmed by `game_engine.py`; animation is never a second
  scoring state and must not invent XP.
- v7.49 adds a second restrained delivery layer without changing that rule:
  `RankAvatar` is a painted level emblem (not a new character state), BattleBar
  score impacts are visual only, and `ui_qt/audio.py` plays tiny async Windows WAV
  cues after confirmed events. `ui_qt/prefs.py` stores only the Sound Feedback
  toggle in `ui_settings.json`. Audio/hover/avatar state must never influence XP,
  Ghost, records, levels or runtime decisions.
- v7.50 adds a dedicated **Character** surface (`ui_qt/character_page.py`) and
  a read/projection layer (`shared/character_engine.py`). The page has an interactive
  asset-free 2.5D avatar (drag rotate / wheel zoom), level-driven armor evolution,
  a daily-XP charge aura, behavior-derived Attributes, Protection Shield progress,
  and peak-level-unlocked environments (Training, Winter, Tropical, Desert, City).
  This is deliberately not a second game engine: character state is projected from
  canonical XP/level/telemetry and may not award XP or alter Ghost/records/levels.
  The first renderer is replaceable later by true 3D without changing this contract.
- v7.50 also fixes the unsolicited periodic sound reported on Windows: passive Ghost
  replay may still advance and show visual feedback on the live timer, but it never
  plays sound. Audio is reserved for confirmed user actions/action-triggered milestones.
- v7.53 replaces the placeholder vector avatar with the eight **person-approved composite
  character artworks** documented in `CHARACTER_ART.md`: Wanderer, Seeker, Apprentice,
  Builder, Disciplined Man, Operator, Elite and Sovereign. `shared/character_engine.py`
  projects these forms from the same canonical rolling Level Rating using permanent peak
  milestones (0 / 5,000 / 12,800 / 24,100 / 39,200 / 55,000 / 75,000 / 100,000). This is
  visual evolution only: no new XP currency, no score awards and no changes to Ghost/records/
  canonical levels. The first five form thresholds align with current game-level entries;
  the last three extend the same rating curve beyond today's top V1 level. Character art is
  stored under `ui_qt/assets/character/` and explicitly bundled by `packaging/witness.spec`.
  The composite scenes are treated as **chapters/forms**, not swappable independent worlds;
  unlocked earlier chapters can be revisited as memories. A later layered/3D asset pass can
  separate body from environment. The image-led renderer supports restrained pan/zoom,
  firefly/rain motion, daily Charge Core pulse and earned Shield field without pretending a
  static illustration is true 3D.
- v7.54 aligns the canonical `shared/game_engine.py` ladder to those same eight stages and
  thresholds: **Wanderer / Seeker / Apprentice / Builder / Disciplined Man / Operator / Elite /
  Sovereign** at 0 / 5,000 / 12,800 / 24,100 / 39,200 / 55,000 / 75,000 / 100,000 rolling
  Level Rating. The first five thresholds are unchanged; only names plus stages 6-8 are added.
  Character `current` form now follows the live canonical level, while historically earned peak
  forms remain available as memories. Manual Undo is explicitly a ledger correction: after a
  reversal, derived current/peak level state is reconciled immediately from corrected XP history
  instead of waiting through the normal 48-hour performance-demotion grace. Ordinary decay still
  keeps the 85% floor + 48h grace. The Character renderer adds gentle pointer parallax, stronger
  but restrained breathing/camera drift, fog/haze, charge-responsive Core pulse and form
  cross-fades; all remain presentation-only and run on the existing light timer.
- v7.55 is a completion/safety pass around that proven loop. `shared/character_engine.py` now
  exposes a user-controlled **Core Reserve** clock that is independent of XP/Level/Shield;
  `ui_qt/character_page.py` maps Daily Charge to an outer aura and Reserve to the inner chest
  glow, surfaces the strongest evidence-backed Attribute as a Signature, and gives actual
  canonical form changes a restrained evolution reveal. `ui_qt/onboarding.py` provides a local
  first-run setup guide without creating an online account or guessing XP. `profile_runtime.py`
  adds rotating transaction-consistent backups, full export, staged next-launch restore, session
  crash detection and crash reports. `packaging/clean_repository.ps1` quarantines known runtime
  leftovers outside the Git checkout before hard validation so folder merges do not repeatedly
  require manual deletion. These are downstream/product-safety features; Layer 1 remains frozen.
- The v7.45 stylesheet explicitly makes QLabel backgrounds transparent. This
  fixed the black-rectangle/old-table look visible in the first Windows Qt
  screenshot; do not reintroduce per-label opaque backgrounds unless a specific
  component needs one.
- **v7.57.1 protection parity correction:** Qt starts both the unchanged `core/tracker.py`
  active-window tracker and the unchanged `core/vision.py` ScreenVision guard through
  `ui_qt/protection_runtime.py`. This restores the legacy full-runtime distinction between title-based
  red-line detection and actual screenshot/vision detection of sexual or suggestive screen content.
  ScreenVision keeps its original adaptive trust cadence, two-consecutive-FLAG confirmation, incident
  history and prompt; Qt only supplies the callback. Confirmed red-lines reuse unchanged
  `core/nuclear.py` browser termination and `core/blocker.py` timed hosts lock, while the intervention
  stays modern Qt and now auto-starts the first SOS video after the dialog is visible. Camera/presence,
  phone detection, legacy AI voice/chat and PatternWatcher remain retired. `trail.record_incident()`
  is still called on a confirmed red-line. The runtime bridge may call `core/`; it must not rewrite Layer 1.

### Local profile / data isolation (v7.51+)

`profile_runtime.py` is imported by **both** `main.py` and `qt_main.py` before
WITNESS data/config/core modules load. On Windows it creates one anonymous local
profile for the current Windows account under `%LOCALAPPDATA%\WITNESS`, generates
a stable random `profile_id`, sets `WITNESS_DATA_DIR`, and changes the process
working directory to that profile folder. This is the intentional compatibility
boundary: historical modules may keep using relative paths such as `witness.db`,
`progression.json`, `video_memories/`, `vision_history.json`, etc., while the actual
files live outside the application/program folder. **Do not "fix" those paths back
to the source directory.** The cwd switch is what isolates even frozen `core/`
without modifying Layer 1.

V1 has no WITNESS username/password. The Windows account is the local privacy
boundary: two different Windows users naturally receive different `%LOCALAPPDATA%`
profiles and different SQLite databases. Two people sharing the same Windows login
would share one WITNESS profile; true multi-profile/login support is deferred.

Distribution builds must be **clean code only**: do not ship `witness.db`,
`witness_data.json`, `progression.json`, `secrets.json`, `ui_settings.json`,
`day_breakdown_data/`, `video_memories/`, `insight_data/`, or other runtime history.
A new install therefore creates empty tables and starts from that person's brand-new
data. `profile_runtime.py` can automatically migrate recognized legacy data if a new
build is placed over an old project-folder install. The Qt Settings page also has
**Import Existing WITNESS Folder**; that stages a migration and applies it on next
launch *before* `db.init()` opens SQLite, so the database is never replaced while
open. Legacy source data is copied, not deleted.

This separation is also the prerequisite for the later installer/updater: program
files can be replaced while `%LOCALAPPDATA%\WITNESS` remains untouched. Secrets are
still stored in local `secrets.json` for now (plain text, same-user protection only);
Windows-protected secret storage is a later hardening step.

**v7.55 profile safety:** `profile_runtime.py` creates up to seven compact rotating backups under
`Backups/` using SQLite's backup API where possible; startup backups are rate-limited to 12 hours,
while an unclean previous session forces a recovery snapshot before `db.init()` opens SQLite.
Settings can create a manual backup, export a full portable ZIP (including media), or safely stage
a backup restore for the next launch. Restore never replaces an open SQLite connection and never
imports `secrets.json`. `.session_active.json` is removed on clean exit; if it survives a crash or
process kill, the next launch reports recovery and writes/checks a backup. `crash_reports/` stores
uncaught Python tracebacks locally. None of these folders belong in release source.

**v7.57 factory-reset contract:** Settings may stage a progress reset only for the next launch.
`profile_runtime.stage_factory_reset()` first creates a forced rotating safety backup, then writes a
marker. `activate()` applies that marker before `db.init()` can open SQLite. The reset removes scoring,
progression, character/game state, telemetry/history, notes/demo/local delivery prefs and derived
insight history. It deliberately preserves `profile.json`, `secrets.json`, `sos_videos/`, `Backups/`
and any active `block_lock.txt`. This is a progress/history reset, not deletion of the person's rescue
media, integrations or rollback path. Never implement factory reset by deleting an open database.


### Interactive 3D control feel (v7.56.1+)

`ui_qt/character_3d.py` remains an experimental procedural renderer, but Windows use confirmed the
interaction itself is worth continuing. Manual drag is intentionally slow and weighty: cursor deltas
change target yaw/pitch, the rendered orientation eases toward those targets on the animation timer,
and both drag axes use the natural object-inspection direction (the v7.56.0 signs were perceived as
inverted). Do not make rotation highly sensitive again merely to feel more responsive; responsiveness
here means immediate smooth motion, not large angular travel per pixel. Portrait art remains the
canonical high-fidelity look until a production rigged model exists.

### Windows desktop distribution / update contract (v7.52+)

The source tree and the installed product now have an explicit distribution boundary.
`app_version.py` is the release-version source of truth. `release_channel.json` contains
the stable update-channel metadata; in source/dev packages its `repository` is intentionally
blank, so a development copy never self-updates from an arbitrary remote. The Windows
release workflow writes the actual public release repository immediately before packaging.

`packaging/witness.spec` builds the current Qt entry point as a PyInstaller **onedir**
application on a Windows runner. `packaging/WITNESS.iss` installs those files per-user under
`%LOCALAPPDATA%\Programs\WITNESS` with no administrator requirement. This program location
must remain separate from the v7.51 local profile under `%LOCALAPPDATA%\WITNESS`; installers
and updater cleanup must never delete or replace the personal profile directory.

`update_manager.py` is dependency-free update logic: query the configured GitHub Releases
latest stable release, compare numeric versions, require both `WITNESS-Setup.exe` and
`WITNESS-Setup.exe.sha256`, download to a temporary update directory, verify SHA-256, then
schedule the Inno installer after the current app exits. `ui_qt/update_service.py` performs
network/download work in daemon threads and reports back by Qt signals; update I/O must not
block the GUI thread or regress the v7.48 responsiveness contract. The shell checks shortly after launch, every 10 minutes while open, and on a throttled
window-reactivation check (minimum 60 seconds between activation requests). It never auto-installs
silently without the person's
**Update & Restart** action. v7.52.2 is the first deliberate end-to-end updater proof release:
the updater already relaunches WITNESS with `/updated`, and the Qt shell now uses that argument
only to show a short green `UPDATED TO vX.Y.Z` confirmation badge. The flag/badge is presentation
state only and must never be used as migration or scoring state.

`.github/workflows/release-windows.yml` is the canonical release builder: a `v*` tag must
exactly match `app_version.VERSION`; GitHub's Windows runner embeds the repository, builds
with PyInstaller, smoke-tests the frozen Qt executable offscreen in an isolated profile,
compiles the per-user Inno installer, writes its SHA-256 sidecar, and publishes both release
assets. Because PyInstaller is platform-specific, do not claim a Linux sandbox build proves
the Windows executable.

**v7.52.1 packaging invariant:** the repository root must not contain old flat duplicates
like `db.py`, `data.py`, `config.py`, `tracker.py`, etc. Canonical modules live in the
section folders. `packaging/validate_source_tree.py` fails a release when root shadows, Python caches, or personal
runtime artifacts are present. v7.55 `packaging/clean_repository.ps1` first removes known obsolete
root code shadows/caches and **moves known runtime/personal leftovers** from a merged checkout to
`%LOCALAPPDATA%\WITNESS\release-quarantine\<timestamp>` (temp fallback off Windows), without
reading contents. The validator still hard-fails if anything unsafe remains. The PyInstaller search
path also keeps canonical section folders ahead of the project root. This exists because the first v7.52.0
GitHub repository accidentally retained an old root `db.py`, which could be packaged instead
of `shared/db.py` and crash at `game_engine.initialize()`.

The frozen smoke test must be a real process/contract test, not just a launch command. The
release workflow waits for the GUI-subsystem EXE, requires a zero exit code, imposes a timeout,
and requires `qt_main.py` to write `WITNESS_SMOKE_MARKER` only after the canonical DB/game
backend and real Qt shell are constructed. The v7.52.0 smoke command could report green even
when a GUI startup exception occurred, so do not weaken this marker check.

Installed program files are disposable because personal history is in the v7.51 profile.
`packaging/WITNESS.iss` clears the old `{app}` program directory before copying a new onedir
build, preventing stale modules from surviving an upgrade. This cleanup must remain scoped
only to `%LOCALAPPDATA%\Programs\WITNESS`; it must never target `%LOCALAPPDATA%\WITNESS`.

For no-login consumer updating, the release endpoint must be publicly readable. A private
source repository may later publish binaries to a separate public release host instead; do
not solve private-release access by embedding GitHub credentials in the client. Windows code
signing is still pending and should be completed before broad public distribution.

### Qt responsiveness rule (v7.48+)

Qt's GUI/event thread must never rebuild hidden pages on an Activity click. Local
XP feedback should be created immediately, then canonical Arena state may refresh
on the next event-loop turn. Hidden Calendar/Records/Insights/Settings pages refresh
when opened. Arena's timer uses `live_refresh()`; slow correlation text belongs to
full refreshes. Activity cards are persistent widgets and should update in place
unless the configured roster itself changed. This is a delivery/performance rule,
not a scoring rule.

## core/ — Layer 1. FROZEN. Read this twice.

Files: `camera.py`, `presence.py`, `inputmon.py`, `tracker.py`,
`vision.py`, `blocker.py`, `nuclear.py`, `trail.py`, `phone.py`,
`patterns.py`, `difficulty.py`.

This is the drift-detection, tab-closing, escalation-ladder, red-line
protection system. It works better than expected. **Do not modify
anything in this folder unless the user explicitly says something like
"let's work on layer 1" or "let's touch core."** A request to work on
the character, the UI, stats, or anything else is not permission to
touch core/. If a change elsewhere seems to require a core/ edit, stop
and ask first.

## character/ — the persona. Active work area, needs love.

Files: `progression.py` (XP/decay), `energy.py` (energy jar),
`voice.py` (TTS), `brain.py` (the AI personality that reacts to events
and speaks lines).

This is what the user actually likes and wants developed further: "the
gamified character that regenerates as time goes on." It is currently
tangled with archived features (see below) — `brain.py` still imports
`strategist`, `finance`, `pipeline`, `journal`, `stats_engine` from
`_archive/` to build its context. That's next on the list to untangle,
not done yet.

## shared/ — low-risk utilities

`config.py`, `ai.py`, `data.py`, `db.py`, `timeutil.py`, `score.py`,
`game_engine.py`, `game_analytics.py`, `character_engine.py`, `demo_data.py`, `video_memories.py`,
`day_breakdown.py`, `stripe_sync.py`, `secrets_store.py`. Used by both
core/ and character/. Edit with normal care; nothing here is layer-specific.

### Canonical V1 scoring / self-competition backend

`shared/game_engine.py` is now the canonical backend for the new product
direction. Both the Tkinter fallback and the PySide6 frontend are delivery
clients on top of it. Do not rebuild this logic inside either UI. It owns:

- persistent scoring Activity definitions (`repeatable`, `once_daily`,
  `timed`; timed XP is interpreted per hour),
- an immutable timestamped `xp_events` ledger in SQLite,
- exact daily battle XP and per-Activity breakdowns,
- a live same-clock Ghost against the same weekday seven days earlier,
- current-week vs prior-week Campaign totals plus per-day "team players",
- daily / same-weekday / weekly / per-Activity high-score calculations,
- completed day-win and week-win streak calculations,
- 14-day rolling level rating with exponential `exp(-0.10*d)` weighting,
- an eight-tier ladder aligned to Character: Wanderer (0), Seeker (5,000), Apprentice
  (12,800), Builder (24,100), Disciplined Man (39,200), Operator (55,000), Elite
  (75,000), Sovereign (100,000),
- 85% demotion floors, a 48-hour At-Risk grace period that continues while
  the app is closed, and a 1.5x comeback credit after an actual demotion,
- immediate level-state reconciliation after explicit Undo/correction so reversed mistake/test
  XP cannot keep a false tier or peak alive; this exception does not weaken ordinary demotion grace,
- chart-ready `rolling_rating_series()` / `progression_snapshot()` for the
  Current-Level and All-Time progression views,
- permanent `level_events` rows for real promotion/demotion/reclaim transitions
  going forward (older tier crossings are reconstructable from the immutable
  XP ledger),
- calendar history summaries + record-day/record-week flags, and
- `dashboard_snapshot()` -- the single clean read contract intended for the
  eventual polished Battle Pacer / Activity Forge UI.

The key scoring separation is deliberate: `score_xp` is the exact manual
score used for Ghost fights and high scores (a configured 500-XP booking is
always 500 battle XP). `level_xp` may receive the comeback multiplier, so
recovery mechanics cannot corrupt the fairness of the comparison score.
Undo never deletes history: it appends a negative reversal event pointing to
the original event. This is what makes time-of-day Ghost replay trustworthy.

`shared/db.py` owns the additive SQLite tables `scoring_activities`,
`xp_events`, `game_state`, and `level_events` plus their storage helpers. The
`level_events` table is append-only for real level transitions and is separate
from the immutable XP ledger. Existing raw telemetry tables remain unchanged.
On first startup,
`game_engine.initialize()` conservatively migrates the transitional v7.41
Activities roster once; old automatic XP triggers and unrelated legacy
progression bonuses are intentionally not imported into the new battle score.

`shared/game_analytics.py` is the pure-Python analysis bridge. It never
changes XP. It treats the person's manual score (or a named Activity such as
"Booked Job") as the outcome and rank-correlates it with background signals
like arrival time, first scored action, tracked minutes, drift %, keyboard/
mouse engagement, and Sales/Focus/Comms/Break category minutes. Minimum
default sample is 7 tracked days; results report sample counts and explicitly
stay descriptive association, not causation. This gives the future AI a
clean answer to "what behavior predicts what I said matters?" without letting
AI invent what "good" means.

`shared/demo_data.py` is optional development/demo support. `seed(28)`
creates about four weeks of timestamped XP events tagged
`source='synthetic_demo'` plus analytics fixtures in the separate
`demo_daily_features` table. It also uses `day_breakdown.synth_seed_day()` so
Calendar demo days have hourly history. `clear()` removes only the tagged XP,
demo feature rows, synthetic hourly docs and Activity definitions created by
the fixture; real XP/telemetry/notes/videos remain untouched, and the
pre-demo rolling-level state is restored. Real telemetry tables are never
filled with fake rows. Menu > Synthetic Demo History is the intended way to
exercise Ghost/records/levels/weekly/Insights before enough real history
exists.

The active main window is now a **functional pre-design Arena** whose only
job is to expose the backend before visual polish. It reads
`game_engine.dashboard_snapshot()` and shows: Daily Fight <-> Weekly Campaign,
live YOU/GHOST/gap bars, record/high-score distance, daily/weekly win streaks,
rolling level status, Activity Forge controls, a canonical XP-vs-Ghost score
timeline, a top behavior association, and last-week closure status. Dedicated
plain panels expose Records, Rolling Level components, Weekly Closure,
Behavior -> Score Insights, Calendar/History, Synthetic Demo History, and a
raw backend JSON snapshot. This is deliberately not the final design; future
visual work should replace widgets/styles, not recreate game math.

Activity Forge remains intentionally plain: repeatables get `+1`, once-daily
items get `Done`, timed items get `+15m`, and every row can undo its latest
event. Settings accepts `R | XP | name`, `D | XP | name`, `T | XP | name`;
old `XP | name` remains repeatable shorthand. These controls write through
`game_engine`, not `data.get_tasks()`. Old `data.get_tasks()`,
`character/progression.py`, energy/focus-score methods and old goal panels
still exist as disconnected/dead transitional code for rollback; do not use
them as the new product's source of truth.

The old automatic `xp_triggers.py` system is retained in source for rollback/
reference but is no longer shown in the menu or scheduled at runtime.

`secrets_store.py` backs the Settings > Integrations panel in
main.py — API keys pasted there get saved to **`secrets.json`** inside the active local profile folder and loaded into `os.environ` at startup
(`secrets_store.load_all()`, called first thing in `main()`), so
`ai.py`, `stripe_sync.py`, and any future integration keep reading
`os.environ.get(...)` exactly as before regardless of whether a key
came from a real environment variable or was pasted into the app.

**⚠️ `secrets.json` contains real API keys in plain text once any are
saved.** Same protection level as a Windows environment variable
(also plaintext, readable to anything running as the person's user
account) — not a new weakness, but a new *file* that could get swept
into a zip or shared by accident. **Never read, open, zip, share, or
ask to see this file's contents** — this applies to any AI session
working on this project, not just a caution for the person. Clean application packages do not contain `secrets.json`; if exporting or
sharing a *profile* for support, exclude `secrets.json` first.

To add a future integration (Whoop, Fitbit, etc.): add one entry to
`secrets_store.INTEGRATIONS` (name, env var key, help text, optional
`verify` function returning `(bool, str)`) — the Settings panel builds
its UI from that list automatically, no new UI code needed.

`video_memories.py` is the video storage layer for the unified Calendar
(main.py's `calendar_panel()` / `_day_detail_panel()`, menu: Calendar) —
plain files under the active profile's `video_memories/YYYY-MM-DD/`, no database. The same
calendar day-detail now also contains daily notes from `shared/db.py`.
Real drag-and-drop into it requires the optional
`tkinterdnd2` package (see install.bat); without it, the feature still
works fully via the "Add Video..." file-picker button. `DND_AVAILABLE`
in main.py gates all of this — check that flag before assuming
drag-and-drop code paths are live.

`day_breakdown.py` is the hourly-history data behind the same day
panel's "HOURLY HISTORY" section (click an hour to open
`_hour_breakdown_popup()`). Two sources: `synth_seed_day()` (fake,
deterministic preview data, for days the app never tracked) and
`build_day_from_activity()` / `refresh_today()` (real data, read from
`shared/db.py`'s `activity` table and categorized via plain keyword
matching -- `CATEGORY_KEYWORDS` in that module, hand-tunable, not AI).
`refresh_today()` runs on a timer from `main.py`
(`_schedule_day_breakdown_refresh()`, every 15 minutes) so today's
calendar entry updates continually while the app runs, and silently
replaces synthetic preview data with real data the moment real
activity exists for that day. Check the `synthetic` key in a loaded
doc to tell which source produced it — `has_real_activity(day)` tells
you whether real data is even possible for a given day.

`stripe_sync.py` pulls real payments from Stripe into `revenue_events`
(the same table the three-lane goal projection reads). Reads
`STRIPE_API_KEY` fresh from `os.environ` on every call (not cached at
import time — see the DEVLOG entry on why that matters now that
Settings > Integrations can set a key live, mid-session). Set via
Settings > Integrations in the app, or manually via `setx`, either
way ends up in `os.environ` the same way. When configured, it's
authoritative: `insight/distiller.py` stops extracting dollar amounts
from notes entirely (see `build_daily()`), so there's no
double-counting between the two sources. `main.py`'s
`_schedule_stripe_sync()` runs it every 15 minutes; the Goal Progress
panel and the Integrations panel both show connection status. If not
configured, `sync()` returns a clean error dict rather than raising —
safe to call unconditionally.


### Character projection / avatar state (v7.50+)

`shared/character_engine.py` translates existing canonical state into visual character
state. It owns no XP rules. Current contracts:

- **Current form** = current canonical rolling level (1–8); **unlocked memories** = historical
  peak level. Peak-rating cache is derived, not an irreversible currency, so an explicit Undo may
  lower it when corrected ledger history no longer supports the old peak.
- **Daily Charge** = today's exact battle XP relative to the stronger of the prior daily
  record, Ghost's final score, or a small cold-start floor. It changes a restrained outer
  aura only; permanent evolution still comes from rolling Level.
- **Core Reserve** = explicit 14-day Start/Reset clock in `game_state`. It is independent of
  XP, Level, Charge, unlocked forms and Shield, and controls the inner chest light. Treat it as
  a user-defined behavioral/visual state, not a physiological measurement.
- **Environment unlocks** use `peak_level`, so once an environment is earned it stays
  earned after demotion. Only the selected environment ID is stored in `game_state`.
- **Attributes** are descriptive evidence (Persistence, Discipline, Momentum, Production,
  Focus). They never award XP and must remain explainable from recorded behavior rather than AI
  guesses. The Character page sorts them strongest-first and may surface one as the Signature.
- **Protection Shield** requires consecutive monitored days with no flagged drift,
  red-line or SOS breach. Unobserved days are never silently counted as clean. The
  first shield appears at 14 clean monitored days; longer streaks strengthen it.
- As of v7.57.1, the Qt app writes real active-window/flagged/red-line telemetry and also runs the
  legacy browser ScreenVision guard while it is open, so Shield progress can advance from genuine
  monitored days. Do not infer webcam/presence or phone coverage: those old subsystems remain retired.

## _archive/ — quarantined, not deleted

`chat.py`, `strategist.py`, `habits.py`, `finance.py`, `pipeline.py`,
`journal.py`, `correlations.py`, `weekly.py`, `stats_engine.py`,
`export.py`, `lifedata.py`, `memory.py`, `mic.py`, `chattest.py`,
`camtest.py`.

This is everything the user said can go: the open-ended chat, the
weekly review, the correlation/stats engine, finance/pipeline tracking,
habits, journaling, email export. It's moved out of the way but **not
disconnected from main.py yet** — see the next section. Nothing here
was deleted on purpose, in case any of it is wanted back later, built
cleanly on top of the simplified base instead of tangled into it.

## insight/ — the white/colored document pipeline

Files: `raw_stats.py`, `store.py`, `distiller.py`, `insight_schedule.py`,
`projection.py`.

This is the data pipeline discussed before the reorg: raw logs ("white
documents," already sitting in `witness.db` via `shared/db.py`, written
by `core/` plus the new `notes` table below) get distilled daily and
weekly into short, readable "colored documents" — plain JSON files
under `insight_data/daily/`, `insight_data/weekly/`, and
`insight_data/suggestions/` inside the active local profile folder.

- `raw_stats.py` — pure Python, no AI. Computes numbers only (focus
  score, minutes tracked/flagged, peak/worst hour, SOS/red-line counts,
  and now the day's notes) for a given day or 7-day window, straight
  from `witness.db`. This is the ground truth; nothing downstream is
  allowed to override it.
- `distiller.py` — turns those numbers (and notes, when present) into
  1-2 plain sentences (daily) or 2-3 sentences plus up to 3
  correlations (weekly), using the AI. Also has `build_suggestions()`
  — 3 evidence-based suggestions for a given day (normally today),
  grounded in yesterday's colored doc plus the latest weekly
  correlations, each one traceable to an actual number or note, not
  generic advice. If no API key is set, or a call fails, everything
  falls back to a plain template built directly from the numbers — the
  pipeline never breaks or goes silent for lack of a key.
- Weekly correlations are deliberately grounded: the AI must cite the
  specific days that support a pattern, `evidence_count` is *counted in
  Python* from those cited days (not asserted by the AI), and
  confidence is one of low/medium/high — never a made-up decimal.
- `insight_schedule.py` — called once at startup from `main.py` in a
  background thread. Builds yesterday's daily doc if missing, last
  week's weekly doc if it's Monday and missing, and today's 3
  suggestions if missing (once per day). Fully wrapped in try/except;
  it can never block or crash app startup. `main()` also schedules one
  delayed UI refresh ~20s after launch so suggestions generated in the
  background actually show up without another action triggering it.
- `store.py` — plain JSON read/write. Nothing fancy on purpose — you
  can open any file in `insight_data/` in a text editor and read
  exactly what the system concluded.

**Daily notes**: `shared/db.py` has a `notes` table (`log_note(text)`,
`log_note_for_day(day, text)`, `notes_for_day(day)`) — one-way input,
no AI response. Notes are now entered inside the selected day in the
Calendar beside hourly history and videos; the separate "Daily Notes"
menu item is retired. These feed `raw_stats.day_stats()` and
get woven into the daily summary and suggestions, weighted heavily
when present since they're the person's own account of the day, not
just inferred from window/activity data.

**Revenue tracking**: `shared/db.py` also has a `revenue_events` table.
`distiller._extract_revenue()` scans each day's notes for dollar
amounts tied to actual income (conservative — skips expenses, hopes,
hypotheticals) and logs them, idempotently, during the normal daily
distillation pass. No separate sales log or CRM — just notes, read
twice (once for the summary, once for revenue extraction).
`insight/projection.py` turns that into `revenue_rate()` (a monthly-
equivalent rate from a trailing window) and
`revenue_completion_projection()` — a linear projection of the target
monthly-revenue goal (`data.load()["money"]["target_monthly"]`,
editable by clicking the money line in the dashboard header), blended
with a 5-year cold-start placeholder that moves closer to the real
computed date as more sales get logged (full trust at 10 logged
sales). This is a deliberate motivational design choice, not a
statistical accuracy claim at low evidence — documented clearly in
the module itself.

The old colored-document pipeline still runs in the background for historical
compatibility, but it is no longer the active definition of performance.
`character/brain.py` now reads the canonical `game_engine.dashboard_snapshot()`
and the strongest `game_analytics` association (when ready), alongside the
older `memory.build_context()` history. It no longer uses legacy goal/task/
energy fields as the definition of success. A future cleanup can decide
whether the old `insight/` colored-document path is still worth retaining.

Tested end-to-end against synthetic activity data (offline mode, no
API key) before being included in this build — confirmed the daily
stats correctly detect an injected afternoon slump pattern, confirmed
notes correctly flow into the daily summary and suggestions, and
confirmed `insight_schedule.run_if_due()` is idempotent (safe to call
every startup, only ever fills in what's actually missing).

## Known loose ends — status

As of the most recent update, the archived-feature UI entry points
listed below have been **disabled** (menu buttons commented out) or,
in the chat box's case, **fully removed from the layout** — not
deleted from the project, just disconnected. The underlying panel
functions (`habits_panel`, `pipeline_panel`, etc.) still exist in
`main.py` as dead code, reachable again by uncommenting one line each
in `show_menu()`.

The conversation box (the text log + typed-reply row that used to sit
at the bottom of the dashboard) has been removed from the layout
entirely, not just disabled — `convo_log`, `reply_entry`, the send
button, and the mic button no longer exist as widgets. `convo_send`
and `_do_chat` (the functions that drove typed replies) were deleted.
This does **not** affect the character's visibility: Witness's spoken
lines (drift nudges, escalation, SOS, greetings, all routed through
`convo_add`) already show up as floating bubbles independently
(`voice.bubble_q` -> `tick()` -> `show_bubble()`), which was true even
before this change and is untouched. `convo_add` still records
history and speaks the line; it just no longer writes to a Text
widget that isn't there anymore. `reset_chat` was updated to match.
`_direct_add_task` and `chat_window` (a second, separate embedded-chat
toggle) are left in place as unreferenced dead code — neither is
reachable from any button.

| Module | main.py (original line refs) | What it is | Status |
|---|---|---|---|
| chat | 777 | open-ended chat reply | box + functions fully removed |
| strategist | 1713 | "deep analysis" button | menu entry commented out |
| habits | 1278, 1294-1295 | habit stack panel | menu entry commented out |
| finance | 1354 | finance projection panel | menu entry commented out |
| pipeline | 1309, 1333, 1344 | revenue pipeline panel | menu entry commented out |
| journal | 1384-1385 | voice journal button | menu entry commented out |
| correlations | 1650 | correlation analysis button | menu entry commented out |
| weekly | 1721, 1749 | weekly review generation | menu entry commented out |
| stats_engine | 1643 | stats engine button | menu entry commented out |
| export | 1458, 1743-1744, 2198-2199 | email export | unscheduled at startup |

`character/brain.py` no longer imports/builds context from `lifedata`,
`strategist`, `finance`, `pipeline`, `stats_engine`, or `journal`. It now uses
canonical game state + behavior correlations for live performance context and
keeps `_archive/memory.py` only as older narrative/history context.

What's live and intentionally reachable in the current pre-design UI:
Activity Forge/Scoring Setup, Calendar/History (score + Ghost + XP timeline +
hourly computer activity + notes + videos), Records/High Scores, Rolling
Level Details, Weekly Closure, canonical XP Performance Chart, Behavior ->
Score Insights, Integrations, Synthetic Demo History, Raw Backend Snapshot,
Focus/Block controls, bubbles and SOS. Old Goal Progress, Goals, Daily Recap,
XP Triggers, old focus-percentage/energy presentation and archived business/
finance/strategy panels remain disconnected/dead and should not be resurfaced
without an explicit product decision.

## The rule, restated simply

- Working on the character, stats, or anything not explicitly layer 1?
  → core/ does not get touched.
- Want to change drift detection, escalation timing, red-line handling,
  the blocker, or anything else in core/? → say so explicitly first.

## Release checkout hygiene (v7.55.2+)

GitHub Actions does not trust a tagged checkout to already be clean. The Windows release job runs `packaging/clean_repository.ps1` immediately after checkout. That script removes only the documented obsolete root-module shadows, moves only known runtime/personal artifact names out of the ephemeral checkout, clears generated caches/build outputs, and then runs `packaging/validate_source_tree.py`. PyInstaller is allowed to start only after that cleaned tree validates. Local pre-commit cleanup remains preferred for repository hygiene, but build correctness no longer depends on the human running PowerShell before committing/tagging. This release layer must never inspect `secrets.json`; it may only recognize that filename and move/exclude it.
