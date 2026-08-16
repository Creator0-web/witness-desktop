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
**v7.55.0 / Qt build `2026-08-16-d` — Completion Pass: Core, Safety + Onboarding** is the
current source. The GitHub Windows installer + Update & Restart pipeline is already proven
end-to-end. This build deliberately finishes the main V1 product/safety layer around the existing
Arena/Character loop without reopening canonical scoring.

WHAT v7.55 ADDS:
- Canonical scoring is still the v7.54 eight-stage ladder: Wanderer 0 → Seeker 5k → Apprentice
  12.8k → Builder 24.1k → Disciplined Man 39.2k → Operator 55k → Elite 75k → Sovereign 100k.
  `shared/game_engine.py` and `shared/db.py` were intentionally not changed in v7.55.
- Character has four distinct concepts: **Level/form** = long-term evolution; **Daily Charge** =
  today's canonical XP and drives an outer aura; **Core Reserve** = explicit user Start/Reset
  14-day personal timer and drives inner chest glow; **Protection Shield** = observed clean
  drift/SOS streak. Reserve never changes XP/Level/Charge/Shield and is a behavioral metaphor,
  not a medical measurement.
- Character full-page entry sorts evidence-backed Attributes strongest-first and surfaces one
  `SIGNATURE`. Real canonical form changes get a restrained dark/gold evolution reveal. Passive
  timers remain silent; the new Core sound occurs only after explicit Start/Reset.
- `ui_qt/onboarding.py` is a local-only 3-step first-run guide: optional name/mission, user-edited
  starter Activities + XP, then Ghost/Level explanation. Existing accounts with any configured
  Activity are not forced through it; Settings can rerun it manually.
- `profile_runtime.py` now owns DATA SAFETY: up to 7 rotating compact backups, 12h startup
  rate-limit, forced crash-recovery backup after an unclean session, full Profile Export, safe
  staged next-launch Restore, session marker and local crash reports. API secrets are excluded
  from backup/export/restore.
- Settings → DATA SAFETY exposes Create Backup, Export Profile, Restore Backup and Open Backups.
- `packaging/clean_repository.ps1` now quarantines known stale runtime leftovers from a Windows
  folder merge into `%LOCALAPPDATA%\WITNESS\release-quarantine\<timestamp>` before validation.
  It identifies by filename only and never reads `secrets.json`. Manual Remove-Item should no
  longer be part of the normal release process. `validate_source_tree.py` still hard-fails if
  anything unsafe remains.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag `v7.55.0` through the already-proven release flow. Run
   `powershell -ExecutionPolicy Bypass -File packaging\clean_repository.ps1`; it should now
   quarantine stale runtime leftovers automatically and finish with `WITNESS release source
   validation OK` / `Repository cleanup complete.` Do NOT manually open/read `secrets.json`.
2. Commit/push, create/push tag exactly `v7.55.0`, wait for Release Windows Desktop to turn green,
   then let the installed app use **Update & Restart**.
3. Windows acceptance test: Character Core Start/Reset + elapsed clock; confirm Daily Charge changes
   outer aura while Reserve changes inner glow; check Signature + evolution reveal; verify no random
   idle sounds.
4. Data Safety test: Create Backup Now, open Backups, make an Export ZIP, then stage Restore on a
   disposable/test profile if possible and confirm it applies only after restart. Existing real
   profile/history must remain intact.
5. If practical, test first-run onboarding with an isolated/fresh Windows profile/data directory.
6. On the NEXT release, intentionally leave the known checkout leftovers in place once and confirm
   cleanup quarantines them automatically — no manual Remove-Item.

KNOWN LIMITATIONS / DO NOT HIDE:
- PySide6 installed app still does NOT start the complete Layer-1 tracker/voice/intervention runtime.
  Shield progress therefore only advances when real telemetry exists from the full runtime. Do not
  fake clean days.
- Composite Character art still couples body + environment; true 360° / independent environments
  require layered or 3D assets later.
- `secrets.json` is profile-isolated but remains plaintext; DPAPI/Windows-protected secrets and code
  signing are still needed before broad public distribution.

After v7.55 passes the real Windows acceptance test, **freeze major feature scope and use WITNESS**.
Only fix concrete bugs/friction found through real use. Do not jump into 3D, fitness, cloud accounts
or Layer-1 rewrites simply because they are possible.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
