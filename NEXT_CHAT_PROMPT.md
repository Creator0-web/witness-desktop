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
**v7.54.0 / Qt build `2026-08-16-c` — Eight-Stage Progression + Character Alive V2** is the
current source. The GitHub Windows installer + Update & Restart pipeline is already proven
end-to-end; normal releases should use that path instead of manual reinstalling.

PROGRESSION / CHARACTER STATUS:
- The canonical rolling ladder in `shared/game_engine.py` is now eight levels and maps exactly to
  the approved art journey: Wanderer (0) → Seeker (5,000) → Apprentice (12,800) → Builder
  (24,100) → Disciplined Man (39,200) → Operator (55,000) → Elite (75,000) → Sovereign
  (100,000). The original first-five thresholds are unchanged; names were aligned and 6–8 added.
- Current Character form follows the **current canonical level**. Historically earned peak forms
  remain unlocked in the Journey strip as memories. `shared/character_engine.py` remains a
  presentation/read layer and never awards XP.
- Manual Undo is now explicitly a correction, not ordinary weak performance. After reversing an XP
  event, `game_engine` immediately recomputes current + historical peak level from the corrected
  immutable ledger, clears false At-Risk state, and asks Character to reconcile its derived peak
  cache. This fixes the reported case where test XP was undone but the app stayed at Level 5.
  Ordinary decay still uses the 85% demotion floor + 48-hour grace and 1.5x comeback rules.
- A one-time ladder migration rebuilds derived level state from the ledger when upgrading from the
  old five-name ladder, so a stale v7.53 Level 5 caused by already-undone test XP should self-heal
  on first v7.54 launch.
- `ui_qt/character_page.py` now has Character Alive V2: approved full-frame art, subtle idle
  breathing/camera drift, smooth pointer parallax, drag pan/wheel zoom, jungle fog + fireflies,
  city haze + restrained rain, charge-responsive Core pulse, Shield field, and cross-fades when
  changing/evolving forms. These effects are delivery only and must remain cheap.
- The eight approved original images remain canonical. Do not replace them with the later skinny/
  wirey/boney regenerations. See `CHARACTER_ART.md`.
- Composite art still couples body + environment. True independent environments / 360° spin need
  layered or 3D assets later. Fitness/watch/body-shape integration and the future Reserve/Core
  timer remain deferred.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Copy the contents of v7.54.0's inner `witness` folder over the clean
   `C:\Users\morea\GitHub\witness-desktop-local` checkout.
2. Run `powershell -ExecutionPolicy Bypass -File packaging\clean_repository.ps1`; validation must
   pass before committing. If the five personal runtime leftovers reappear in the checkout,
   remove only those checkout copies (`conversation.json`, `progression.json`, `secrets.json`,
   `witness.db`, `witness_data.json`) and rerun validation.
3. Commit/push, create/push tag exactly `v7.54.0`, and wait for Release Windows Desktop to turn green.
4. Let the installed app discover **UPDATE v7.54.0** and use Update & Restart.
5. Verify on Windows: the user's previously stuck test level drops to the ledger-supported level;
   levels/names align with the eight Character forms; spam a test Activity through higher levels and
   undo it back down; inspect Character parallax/breathing/fog/rain/Core/cross-fade smoothness.
6. Fight only concrete Windows visual/performance bugs before adding more feature scope.

Security/runtime items still pending before broad public release:
- Windows code signing / reputation,
- DPAPI or equivalent protection for local API secrets,
- full Layer-1 tracker/voice/intervention integration into the Qt installed app.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
