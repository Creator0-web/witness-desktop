Paste this whole message into a new chat to continue work on WITNESS.

---

I'm continuing work on WITNESS, a Python desktop app (Windows; legacy Tkinter full runtime +
PySide6 visual shell) built across many prior chats with Claude. Before doing or suggesting
anything: read ARCHITECTURE.md and DEVLOG.md in the project root, in
full — not just skim them.

⚠️ If `secrets.json` exists in this project, never read, open, or ask
to see its contents — it holds real API keys in plain text (Settings
> Integrations, see shared/secrets_store.py). Skip it entirely.

ARCHITECTURE.md explains the folder structure (core/ = Layer 1 drift
protection, character/ = the persona, shared/ = utilities, insight/ =
the data pipeline, _archive/ = disabled features kept for reference)
and the one hard rule: core/ is frozen. Don't touch anything in it
unless I explicitly say so in this conversation — a request to work on
anything else is not permission to touch core/.

DEVLOG.md is a running log, most recent entry first. Read the whole
thing, not just the latest entry — earlier entries explain decisions
and known limitations that still apply. Pay attention to any "Left for
next session" notes at the end of entries.


CURRENT FOCUS RIGHT NOW:
The first real Windows/GitHub installer pipeline was successfully created and GitHub Actions
published `v7.52.0`, but the installed EXE immediately crashed at startup with:
`AttributeError: module 'db' has no attribute 'game_state_get'` from
`game_engine.initialize()`. The GitHub repository screenshot showed stale pre-reorg root modules
(e.g. root `db.py`, `data.py`, `config.py`, tracker/core duplicates) mixed into the otherwise
new sectioned source. The old root DB predates the game-state API. The v7.52.0 Action also used
a weak windowed-EXE smoke command that could turn green without proving the backend/shell was
actually reached.

v7.52.1 / Qt build **2026-08-15-f** is now the current source baseline: **Desktop Packaging
Hotfix**. It is intentionally delivery-only; game/backend behavior is unchanged.

What v7.52.1 adds/fixes:
- `app_version.VERSION = 7.52.1`; next release tag is exactly `v7.52.1`.
- `.gitignore` blocks Python caches/build outputs and known WITNESS personal/runtime data.
- `packaging/validate_source_tree.py` makes stale root module shadows, caches, or personal
  artifacts a HARD release failure and verifies canonical `shared/db.py` exposes required APIs.
- `packaging/clean_repository.ps1` safely removes known obsolete root CODE duplicates and
  caches from an old Git checkout, then runs validation. It does not delete personal data.
- `packaging/witness.spec` puts canonical section folders before repository root during
  PyInstaller analysis so a legacy root file cannot outrank `shared/db.py`.
- `qt_main.py` checks the required canonical DB API and writes a smoke marker only after DB/game
  initialization + the real `WitnessMainWindow` construction succeed.
- GitHub/local Windows build scripts now run a real frozen test: `Start-Process`, timeout,
  wait, exit code, AND required marker. Do not revert to a plain GUI launch + `$LASTEXITCODE`.
- Inno Setup clears only the old program directory (`%LOCALAPPDATA%\Programs\WITNESS`) before
  copying the new onedir build. Personal `%LOCALAPPDATA%\WITNESS` profile data is separate and
  is never deleted by this cleanup.
- `core/`, `shared/game_engine.py`, and `shared/db.py` were not changed.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Copy the contents of this v7.52.1 source into the existing local `witness-desktop` Git repo.
2. In that repo run:
   `powershell -ExecutionPolicy Bypass -File packaging\clean_repository.ps1`
3. GitHub Desktop should show deletions of stale root duplicates plus the new/changed hotfix
   files. Review that `core/` itself is NOT deleted/modified and no personal data is present.
4. Commit/push to `main`.
5. Create/push tag exactly `v7.52.1`.
6. GitHub Action must pass the new source validation AND hardened frozen marker smoke test.
7. Because installed v7.52.0 cannot start its updater, manually download/install the new
   `WITNESS-Setup.exe` once. Verify WITNESS opens and the Local Profile/history is preserved.
8. After that, future good releases should be tested through WITNESS's own **Update & Restart**
   flow rather than manually reinstalling.

Do not work around this by adding `game_state_get` to the old root DB, weakening validation,
or touching `core/`. Remove the obsolete duplicate and keep canonical module ownership clear.
Once v7.52.1 is proven on the person's Windows machine, return to product completion: full Qt
runtime integration, DPAPI secret hardening, and final Character/runtime polish. Do not reopen
scoring architecture.

Security/distribution items still pending before broad public release:
- Windows code signing / reputation,
- DPAPI or equivalent protection for local API secrets,
- full Layer-1 runtime integration into the Qt installed app.

Before your context runs out, or once you've made real progress: add a
new entry to DEVLOG.md (template is in that file, most recent entry
goes on top) and update the "CURRENT FOCUS RIGHT NOW" section of this
file (NEXT_CHAT_PROMPT.md) so the next chat starts exactly where you
left off — don't let this section go stale the way it did between
sessions before this one. Tell me directly, in your last message, that
you've updated both files, so I know to re-download the project before
opening a new chat.
