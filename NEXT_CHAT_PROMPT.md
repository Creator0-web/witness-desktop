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
The person approved v7.51 local-profile isolation and immediately asked to stop the manual
ZIP/re-download workflow. v7.52 / Qt build **2026-08-15-e** is now the current source
baseline: Desktop Distribution Foundation.

What v7.52 adds:
- `app_version.py` is the release-version source of truth (`7.52.0` / display v7.52),
- the v7.51 local profile remains unchanged: program files are separate from
  `%LOCALAPPDATA%\WITNESS`, so updates do not own/delete XP, notes, videos, Character,
  telemetry, settings, or profile identity,
- `update_manager.py` + `ui_qt/update_service.py` add a non-blocking stable-release updater;
  packaged builds check shortly after launch and every 6h, show **UPDATE vX.Y.Z** only when
  a newer complete release exists, download the installer in a worker thread, require and
  verify `WITNESS-Setup.exe.sha256`, then schedule the installer after WITNESS exits,
- the update action is explicit **Update & Restart**; there is no surprise silent install,
- source/dev `release_channel.json` deliberately has a blank repository, so ZIP/dev copies
  make no release-network request. The release workflow injects the real repo only into a
  packaged build,
- `packaging/witness.spec` builds the Qt app using PyInstaller onedir;
  `packaging/WITNESS.iss` creates a no-admin per-user installer under
  `%LOCALAPPDATA%\Programs\WITNESS` and creates Start-menu/desktop shortcuts,
- `.github/workflows/release-windows.yml` is the automated release path: push a tag matching
  `app_version.VERSION` (e.g. `v7.52.0`) -> Windows runner embeds the repo -> PyInstaller ->
  offscreen frozen smoke test -> Inno Setup -> SHA-256 -> GitHub Release assets,
- `packaging/build_windows.ps1` is an optional local-Windows equivalent; `DISTRIBUTION.md`
  documents the release/update contract.

Important limitation: this Linux chat environment cannot generate/validate the actual
Windows EXE because PyInstaller is not a cross-compiler. The release automation is built,
but an actual `WITNESS-Setup.exe` first appears after the clean source is placed in a GitHub
repository (or another Windows build machine is used) and the v7.52.0 tag is published.
For no-login automatic updates with the provided GitHub flow, the release endpoint must be
publicly readable; source can later remain private by publishing binaries to a separate
public release repository/host. Do not embed GitHub credentials in the app.

Security/distribution items still pending before broad public release:
- installer/executable are not code-signed yet, so Windows may show unknown-publisher/
  reputation warnings; add trusted Windows code signing later,
- `secrets.json` is profile-isolated but still plain text; move secrets to DPAPI/Windows
  protected storage before broad distribution,
- the Qt app still does NOT start the complete Layer-1 tracker/voice/intervention runtime.
  Packaging did not change that; legacy `main.py` remains the full-runtime reference.

Validation state for v7.52 source:
- full Python compile/AST sweep passes after adding distribution code,
- updater version comparison, fake GitHub latest-release parsing, streamed installer download,
  and SHA-256 verification were exercised end-to-end with a mocked release,
- release-preparation script was tested against a matching v7.52.0 tag and restores the
  source channel to blank afterward,
- packaging spec/installer files received static syntax/contract checks,
- every `core/*.py` file remains frozen and must match the v7.51 hashes after final packaging.

ACTUAL NEXT STEP:
Do not send the person back to ZIP-by-ZIP usage as the long-term workflow. The next practical
step is to establish the one public release endpoint (most simply a GitHub repository or
public binaries-only release repo), run the supplied Windows release workflow once, and give
the person the resulting `WITNESS-Setup.exe`. After that installation, future tagged releases
are discovered by the app and the person uses **Update & Restart** instead of downloading
project ZIPs. Then return to product completion: Qt full-runtime integration, secret hardening,
and Character/runtime polish. Do not rebuild scoring or modify `core/` unless explicitly
authorized.

Before your context runs out, or once you've made real progress: add a
new entry to DEVLOG.md (template is in that file, most recent entry
goes on top) and update the "CURRENT FOCUS RIGHT NOW" section of this
file (NEXT_CHAT_PROMPT.md) so the next chat starts exactly where you
left off — don't let this section go stale the way it did between
sessions before this one. Tell me directly, in your last message, that
you've updated both files, so I know to re-download the project before
opening a new chat.
