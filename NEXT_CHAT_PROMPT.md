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
**v7.57.3 / Qt build `2026-08-17-d` — Factory Reset Reliability + Triangle Branding** is the current source.
The person reports that v7.57.2 drift detection is now working well, so **do not retune Layer 1 unless they
explicitly ask again**. Their remaining Windows issues were: Factory Reset claimed success but the app still
showed Lv.6 Operator, and the installed Windows app still looked like a generic Python application/icon.

WHAT v7.57.3 CHANGES:
- `profile_runtime.py`: fixes the Factory Reset race. The restart helper now waits for the current WITNESS PID
  to fully exit before relaunching. `_apply_pending_factory_reset()` retries locked files, verifies all reset
  targets are truly gone, and **keeps the reset marker** if anything remains instead of silently claiming success.
- `qt_main.py`: after an applied factory reset, canonical game initialization is verified to be exactly Level 1
  / 0 rolling rating. A failed reset can no longer quietly reopen as Operator.
- `ui_qt/assets/branding/witness.ico` + `witness_icon.png`: new dark rounded-square WITNESS icon built around
  a white ascent triangle with a restrained green inner Core mark.
- `packaging/witness.spec` embeds the ICO into `WITNESS.exe` and bundles branding assets.
- `packaging/WITNESS.iss` uses the same ICO for the installer; Qt sets the application/window icon and a Windows
  AppUserModelID so taskbar/shortcut branding no longer falls back to generic Python.
- `ui_qt/shell.py` + `theme.py`: top chrome gains a small triangle mark whose accent follows WILD/FORGED/NOIR.
- `core/vision.py` and `core/nuclear.py` are **unchanged from v7.57.2**. Scoring/game semantics are unchanged.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.57.3`; wait for GitHub Actions green and use Update & Restart.
2. Confirm desktop/Start/taskbar/title-bar branding uses the new triangle icon rather than generic Python.
3. In Settings, run Factory Reset Progress again only after the automatic safety backup is created. The restart
   should wait until the old process is gone; on reopen WITNESS must say **Lv.1 Wanderer** with **0 rolling XP**.
4. Confirm Rapid Screen Guard still behaves exactly like v7.57.2. Do not change protection simply because this
   release touched startup/reset/branding.
5. If reset still does not produce Lv.1 / 0, capture the exact startup/reset error. v7.57.3 intentionally keeps
   the pending reset marker on deletion failure, so there should now be an observable failure instead of a false
   success.

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
