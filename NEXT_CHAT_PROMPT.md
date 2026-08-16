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
**v7.55.2 / Qt build `2026-08-16-e` — Completion Pass + Self-Cleaning Release Build** is the
current source. v7.55.0/v7.55.1 failed GitHub Actions at the pre-build clean-source validator even
though the tagged SHA shown by Actions (`5b3270e`) matched the GitHub Desktop commit containing the
expected root-module deletions. Rather than keep relying on perfect local cleanup ordering, v7.55.2
makes the ephemeral GitHub Actions checkout clean itself before packaging.

WHAT v7.55.2 CHANGES:
- Product behavior remains the v7.55 Completion Pass: eight-stage progression, Character Charge/Core/
  Shield separation, Signature, evolution reveal, local onboarding, backup/export/restore/crash safety.
- `.github/workflows/release-windows.yml` now runs `packaging/clean_repository.ps1` immediately after
  checkout/setup Python instead of running `validate_source_tree.py` first. The cleanup removes only
  documented obsolete root-module shadows, moves only known runtime/personal artifact names out of the
  ephemeral checkout, clears caches/build outputs, and then validates. PyInstaller never starts until
  validation passes.
- Local PowerShell cleanup before committing is still recommended for clean Git history, but release
  correctness no longer depends on whether the user accidentally committed before running cleanup.
- `shared/game_engine.py`, `shared/db.py` and every `core/*.py` file are intentionally unchanged from
  v7.55.0.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Copy the fresh v7.55.2 source over `C:\Users\morea\GitHub\witness-desktop-local`.
2. Optional but recommended: run `powershell -ExecutionPolicy Bypass -File packaging\clean_repository.ps1`
   locally, then review changes. The CI job now repeats this safety step itself.
3. Commit/push the fresh source, then create/push tag exactly `v7.55.2`. Do not reuse failed v7.55.0 or
   v7.55.1 tags.
4. Confirm GitHub Actions passes **Clean and validate release source** and continues into dependency
   install/PyInstaller. If it fails, capture that exact step log before making another tag.
5. Once green, use the installed WITNESS **Update & Restart** path. Then test Core Start/Reset, Charge vs
   Core visuals, Signature/evolution reveal, Data Safety backup/export, and unexplained idle sound.

KNOWN LIMITATIONS / DO NOT HIDE:
- PySide6 installed app still does NOT start the complete Layer-1 tracker/voice/intervention runtime.
  Shield progress therefore only advances when real telemetry exists from the full runtime. Do not
  fake clean days.
- Composite Character art still couples body + environment; true 360° / independent environments
  require layered or 3D assets later.
- `secrets.json` is profile-isolated but remains plaintext; DPAPI/Windows-protected secrets and code
  signing are still needed before broad public distribution.

After v7.55.2 passes the real Windows acceptance test, **freeze major feature scope and use WITNESS**.
Only fix concrete bugs/friction found through real use. Do not jump into 3D, fitness, cloud accounts
or Layer-1 rewrites simply because they are possible.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
