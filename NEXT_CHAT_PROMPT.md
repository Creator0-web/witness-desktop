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
**v7.56.1 / Qt build `2026-08-16-g` — 3D Control Feel + Live Update Checks** is the current
source. v7.56.0 was successfully installed/tested on Windows. The person said the 3D character
interaction "honestly feels nice," which is the key acceptance signal for continuing toward real 3D.
Two concrete usability issues were found and are fixed in v7.56.1: drag felt inverted on both axes,
and rotation was too sensitive/fast for the desired powerful feel. They also noted new releases only
showed after restarting the app because the prior periodic updater check was six hours.

WHAT v7.56.1 CHANGES:
- `ui_qt/character_3d.py`: manual drag now changes target yaw/pitch in the opposite direction from
  v7.56.0 on both axes, with lower sensitivity (`0.0045` yaw / `0.0035` pitch per pixel). Actual
  orientation eases toward the target each 33ms frame, making turns slower, smoother and weightier.
  Auto Rotate is slowed as well.
- `update_manager.py` + `release_channel.json`: stable release polling now supports minute cadence;
  packaged channel defaults to a 10-minute check interval while retaining old `check_hours` fallback.
- `ui_qt/shell.py`: startup check remains, periodic check uses `check_minutes`, and returning focus
  to the WITNESS window triggers a quiet throttled background check when at least 60 seconds have
  elapsed since the prior request. Update download/install semantics are unchanged and still explicit.
- WILD/FORGED/NOIR theme evolution, eight-stage progression, Core/Charge/Shield, approved Portrait
  artwork, XP/Ghost/records and release self-cleaning remain unchanged.
- `core/`, `shared/game_engine.py`, and `shared/db.py` remain frozen/unchanged.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.56.1`; let installed WITNESS Update & Restart.
2. In 3D LAB, verify dragging right/left/up/down now feels natural and that a long mouse drag produces
   a slow, powerful rotation rather than a twitchy spin. Test Auto Rotate and wheel zoom too.
3. To verify live updater discovery later, leave WITNESS open before publishing another tiny release;
   either wait up to ~10 minutes or switch away/back after >60 seconds. The UPDATE button should appear
   without restarting the app.
4. Because the 3D interaction concept is now positively validated, the next major Character step is
   a production-quality rigged avatar/renderer, not more procedural-mesh ornamentation. Preserve the
   approved Portrait art and the accepted slow control feel while that production asset is developed.

KNOWN LIMITATIONS / DO NOT HIDE:
- PySide6 is unavailable in the Linux build sandbox, so v7.56's final visual/performance acceptance
  depends on the real Windows build. Static compile/AST/source-tree validation passes.
- The 3D Lab mesh is a procedural interaction prototype; it does not yet reproduce the approved face
  or cinematic clothing at production quality, and it has no skeletal animation.
- Qt still does NOT start the complete Layer-1 tracker/voice/intervention runtime. Shield progress only
  advances when real monitoring telemetry exists; never fake clean days.
- `secrets.json` remains plaintext in the isolated local profile; never read/open/share it. DPAPI and
  Windows code signing are still future distribution hardening.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
