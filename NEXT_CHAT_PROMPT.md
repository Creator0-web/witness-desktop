Paste this whole message into a new chat to continue work on WITNESS.

---

I'm continuing work on WITNESS, a Python desktop app (Windows; legacy Tkinter full runtime +
PySide6 installed-app shell) built across many prior chats. Before doing or suggesting anything:
read ARCHITECTURE.md and DEVLOG.md in the project root, in full — not just skim them.

⚠️ If `secrets.json` exists in this project, never read, open, or ask to see its contents — it
holds real API keys in plain text. Skip it entirely.

ARCHITECTURE.md explains the folder structure and the hard rule: `core/` is frozen. Don't touch
anything in it unless I explicitly say so in this conversation. DEVLOG.md is the running history;
read every entry because older decisions still apply.

CURRENT FOCUS RIGHT NOW:
**v7.57.0 / Qt build `2026-08-17-a` — Modern Drift Protection + Safe Factory Reset** is the
current source. The person approved the slow/natural 3D controls in v7.56.1, then deliberately paused
production-quality 3D because that asset pipeline felt too complicated for now. They asked to restore
the valuable old backend behavior instead: drift protection, automatic red-line browser shutdown and
the SOS video intervention, but without reviving the old Tkinter visual feel. They also asked for a
Settings factory-reset-style action that returns scoring/progress to zero.

WHAT v7.57.0 CHANGES:
- `core/` remains byte-for-byte frozen. Qt now starts its existing `WindowTracker` through the new
  `ui_qt/protection_runtime.py` bridge. Real foreground-process/title telemetry is therefore written
  while the installed modern app is open.
- Ordinary distracting windows keep the existing thresholds: lightweight modern notices at about
  0.5 / 2.5 / 4.5 minutes and a redesigned intervention at about 6.5 minutes. No XP penalty is added;
  the scoring system remains manual.
- Red-line detection preserves the old hard-safe whitelist, then immediately reuses `nuclear.kill_browsers()`
  and attempts `blocker.block_sites(120)`. Browser termination runs even if the modern UI is on another page.
  Site locking still depends on Windows admin permission; the intervention reports whether it succeeded.
- The old Tkinter intervention/video popup is retired in the Qt path. New `ProtectionDialog` is dark,
  top-most, current-product styling and embeds local SOS videos with QtMultimedia. Settings can open the
  SOS folder and preview the intervention without closing anything.
- A top-bar PROTECTION ACTIVE badge makes runtime state visible. Smoke-test builds do not start protection.
- Settings → Factory Reset Progress requires both a warning and typing RESET. It creates a forced safety
  backup, stages reset for next launch, and restarts. XP/Ghost/Levels/records/Character/Core/Shield,
  activity/drift history, notes/demo/derived data return to zero. Profile identity, integrations/secrets,
  SOS videos, Backups and active block state are preserved.
- Windows release requirements now include `psutil` + `pywin32`; PyInstaller explicitly includes QtMultimedia.
- `shared/game_engine.py` and `shared/db.py` are unchanged.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.57.0`; wait for the Windows Action to go fully green, then Update & Restart.
2. Confirm the top bar reads **PROTECTION · ACTIVE**.
3. Settings → Protection → **Preview Intervention** first. Add/test a local MP4 through **Open SOS Video Folder**.
4. Test normal drift thresholds using a safe distracting window. Do not test red-line shutdown while valuable
   browser tabs are open: by design it force-closes supported browsers. Verify the intervention accurately
   reports browser-close + whether the 120-minute hosts lock succeeded.
5. Only after confirming a pre-reset backup exists, test Factory Reset Progress. Expected result after restart:
   all score/progression/history is fresh/zero while integrations, SOS videos and backups remain.
6. Production-quality rigged 3D remains a later project; preserve the approved v7.56.1 slow interaction feel.

KNOWN LIMITATIONS / DO NOT HIDE:
- PySide6 is unavailable in the Linux build sandbox, so v7.56's final visual/performance acceptance
  depends on the real Windows build. Static compile/AST/source-tree validation passes.
- The 3D Lab mesh is a procedural interaction prototype; it does not yet reproduce the approved face
  or cinematic clothing at production quality, and it has no skeletal animation.
- Qt now starts the focused active-window drift/red-line subset of Layer 1. Camera/presence, phone, legacy
  voice/chat, PatternWatcher and ScreenVision are still not started; do not claim full old-runtime parity.
- `secrets.json` remains plaintext in the isolated local profile; never read/open/share it. DPAPI and
  Windows code signing are still future distribution hardening.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
