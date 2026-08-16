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
**v7.56.0 / Qt build `2026-08-16-f` — Theme Evolution + Interactive 3D Lab** is the current
source. The v7.55.2 self-cleaning GitHub release pipeline was proven green on Windows and the app
updated successfully before this work began. The person then explicitly chose to keep polishing
before Monday: make the whole app visually mature with the Character and try real 3D interaction.

WHAT v7.56 CHANGES:
- `ui_qt/theme.py` now has three presentation-only eras chosen from canonical current Level:
  **WILD** for Levels 1-2, **FORGED** for 3-4, **NOIR** for 5-8. Surfaces/radii/chrome/decorative
  accent evolve; green/red/gold semantic meanings remain stable.
- `ui_qt/shell.py` displays the current era and switches QSS only when the broad era changes.
  It reads `game_engine.level_status()` but never writes progression state. Hidden pages are not
  rebuilt, preserving the v7.48 responsiveness rule.
- Character now has **PORTRAIT | 3D LAB**. Portrait is still the approved/canonical original art.
- `ui_qt/character_3d.py` is a dependency-free procedural true-geometry 3D prototype: drag rotates,
  wheel zooms, double-click resets, Auto Rotate is optional, Reserve drives chest Core glow, Charge
  drives an outer field, and stage clothing progresses toward tight tactical/tailored/Sovereign form.
  This is intentionally a prototype mesh, not final face/art quality.
- The future production asset contract is in `ui_qt/assets/3d/README.md`: one identity-consistent
  rigged GLB/glTF character with outfit variants and separate environments if the prototype earns it.
- `core/`, `shared/game_engine.py`, and `shared/db.py` are unchanged from v7.55.2.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.56.0` using the already-proven self-cleaning release workflow.
2. Let installed WITNESS use Update & Restart.
3. Test Arena/History/Character at or previewed across Levels 1-8 and judge whether WILD/FORGED/NOIR
   feels like one world evolving rather than three gimmicky skins.
4. On Character, switch to 3D LAB and test rapid drag rotation, full 360-degree inspection, zoom,
   Auto Rotate, stage switching/memories, Core pulse and Charge field. Watch for lag or paint glitches.
5. If the interaction feels compelling but the procedural person looks too crude, **do not abandon 3D**
   and do not replace approved Portrait art. The next step is a production rigged avatar asset/renderer.
   If the interaction itself is not useful, keep 2.5D Portrait and remove/leave the lab experimental.

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
