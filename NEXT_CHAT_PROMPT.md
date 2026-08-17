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
**v7.57.1 / Qt build `2026-08-17-b` — Full Screen Guard Restore + Auto SOS** is the current source.
The person liked the modern v7.57 intervention UI but immediately noticed protection felt slower than the
old app. Audit confirmed v7.57.0 had restored only `WindowTracker` (process/title detection) and had NOT
started the separate legacy `ScreenVision` thread that actively classified browser screenshots.

WHAT v7.57.1 CHANGES:
- `core/` remains byte-for-byte frozen. Qt now starts both the unchanged `WindowTracker` and unchanged
  `ScreenVision` through `ui_qt/protection_runtime.py`.
- WindowTracker behavior is unchanged: foreground titles are sampled every 5s; `RED_LINE_KEYWORDS`
  trigger red-line immediately (subject to its 120s duplicate cooldown); ordinary distracting titles use
  the 0.5 / 2.5 / 4.5 / 6.5 minute drift ladder.
- ScreenVision behavior is unchanged from the legacy full runtime: 45s startup delay; browser-only scan;
  SAFE 300s / CAUTIOUS 90s / DANGER 30s adaptive cadence; incognito/private and browsers with >=3
  incidents are DANGER; two consecutive FLAG classifications required; after the first FLAG, confirmation
  is accelerated to about 10s. It captures the screen and sends it to Claude Vision using the configured
  Anthropic key.
- Confirmed vision red-lines use the same modern Qt browser-kill + 120-minute site-lock intervention.
  The legacy hard-safe whitelist is preserved.
- SOS intervention video now starts automatically once the dialog's video surface is visible, including
  Settings preview. The button is `NEXT RESET VIDEO`, not an initial Play button.
- Windows packaging now includes `anthropic`, Pillow/ImageGrab and `mss` for ScreenVision in addition to
  psutil/pywin32/QtMultimedia.
- Factory Reset from v7.57.0 is unchanged.
- Camera/presence, phone detection, legacy voice/chat and PatternWatcher remain intentionally retired.
- `shared/game_engine.py` and `shared/db.py` are unchanged.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.57.1`; let GitHub Actions finish green and Update & Restart.
2. Top bar should say **PROTECTION · ACTIVE · SCREEN GUARD**. If it says **TITLE ONLY**, first diagnose
   missing Anthropic key/runtime rather than changing detection logic.
3. Settings → Protection → Preview Intervention: first SOS video should auto-play without a click.
4. Leave WITNESS open at least 45 seconds before judging ScreenVision because that startup delay is part of
   the unchanged old implementation. Test with disposable browser tabs; confirmed red-lines intentionally
   kill supported browsers.
5. If the person still remembers reliably faster behavior than this v2 adaptive-trust code provides, inspect
   prior historical source before changing `core/vision.py`; their remembered version may predate ScreenVision v2.

KNOWN LIMITATIONS / DO NOT HIDE:
- Final Windows screenshot capture, Anthropic classification, QtMultimedia autoplay and browser taskkill
  cannot be proven in the Linux sandbox; static compile/AST/package validation is the local check.
- ScreenVision sends captured browser-screen imagery to Anthropic for FLAG/SAFE classification; this is the
  legacy design and requires the configured Anthropic integration.
- The 3D Lab remains a procedural interaction prototype; production rigged 3D is paused.
- `secrets.json` remains plaintext in the isolated local profile; never read/open/share it. DPAPI and Windows
  code signing remain future distribution hardening.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
