Paste this whole message into a new chat to continue work on WITNESS.

---

I'm continuing work on WITNESS, a Python desktop app (Windows; legacy Tkinter full runtime +
PySide6 visual shell) built across many prior chats. Before doing or suggesting anything: read
ARCHITECTURE.md and DEVLOG.md in the project root, in full — not just skim them.

⚠️ If `secrets.json` exists in this project, never read, open, or ask to see its contents — it
holds real API keys in plain text. Skip it entirely.

ARCHITECTURE.md explains the folder structure and the hard rule: `core/` is frozen. Don't touch
anything in it unless I explicitly say so in this conversation. DEVLOG.md is the running history;
read every entry because older decisions still apply.

CURRENT FOCUS RIGHT NOW:
**v7.53.0 / Qt build `2026-08-16-b` — Character Art Progression V1** is the current source.
The GitHub Windows installer + Update & Restart pipeline has already been proven end-to-end on the
person's computer; normal future releases should use that path instead of manual reinstalling.

CHARACTER STATUS:
- The person designed and approved eight original character stages and explicitly preferred these
  originals over later regenerated versions that made the character look skinny/wirey/boney.
- Canonical V1 art is bundled in `ui_qt/assets/character/` and documented in `CHARACTER_ART.md`:
  Wanderer → Seeker → Apprentice → Builder → Disciplined Man → Operator → Elite → Sovereign.
- `shared/character_engine.py` now projects permanent visual form from **peak canonical rolling
  Level Rating** at 0 / 5,000 / 12,800 / 24,100 / 39,200 / 55,000 / 75,000 / 100,000. This is a
  visual projection only, not a second scoring system. Do not change canonical XP/Ghost/levels to
  support the art unless the person explicitly decides to revisit game architecture.
- `ui_qt/character_page.py` now uses the approved image-led 2.5D scene: full-frame art, restrained
  pan/zoom, subtle fireflies/rain, current Charge Core pulse, Shield field, and an 8-form Journey
  strip. Earned earlier forms can be revisited as memories. Demo mode may preview all forms for
  visual testing.
- The current art is composite body + environment. V1 therefore treats each image as a **chapter**.
  Do not pretend a Sovereign is standing in the jungle by displaying the old Wanderer composite.
  True independent environments should wait for layered assets or a real 3D character pipeline.
- Fitness/watch/body-shape integration remains deferred. The future Reserve/Inner Core timer idea
  is also not built yet.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Copy v7.53.0 source over the clean `witness-desktop-local` GitHub checkout.
2. Run `powershell -ExecutionPolicy Bypass -File packaging\clean_repository.ps1`; validation must
   pass before committing.
3. Commit/push to `main`, create/push tag exactly `v7.53.0`, and wait for the Windows Release
   Action to turn green.
4. Do NOT manually install if current WITNESS is healthy. Let installed v7.52.2 detect
   `UPDATE v7.53.0` and use Update & Restart.
5. Test CHARACTER on the real Windows screen: image crop/quality, Journey-strip layout, drag/zoom,
   subtle Core pulse, Shield overlay, fireflies/rain, and demo preview of all forms.
6. If something is visually wrong, adjust the exact observed issue before changing architecture.

Security/runtime items still pending before broad public release:
- Windows code signing / reputation,
- DPAPI or equivalent protection for local API secrets,
- full Layer-1 tracker/voice/intervention integration into the Qt installed app.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
