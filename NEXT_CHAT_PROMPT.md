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
v7.52.2 / Qt build **2026-08-16-a** is the current source: **Updater End-to-End Test**.
v7.52.1 has already been installed successfully on the person's Windows PC after the packaging
hotfix. The immediate next task is NOT more feature work: prove the installed updater.

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Copy the contents of this v7.52.2 source over the clean local GitHub checkout.
2. Run `powershell -ExecutionPolicy Bypass -File packaging\clean_repository.ps1`; it must pass.
3. Commit/push to `main`, then create/push tag exactly `v7.52.2`.
4. Wait for the hardened Windows Release Action to turn green and verify the Release contains
   `WITNESS-Setup.exe` plus `WITNESS-Setup.exe.sha256`.
5. Do NOT manually download/install v7.52.2. Leave installed v7.52.1 in place. Restart/open it,
   wait a few seconds for the startup release check, then click `UPDATE v7.52.2` -> Update &
   Restart.
6. Success = WITNESS closes, updates program files, reopens with the same profile, and briefly
   shows a green `UPDATED TO v7.52.2` badge in the top bar.

If the update button does not appear, first verify GitHub's latest stable Release is v7.52.2 and
both assets exist. If download/install/restart errors, capture the exact WITNESS error instead of
changing updater architecture speculatively. Once this succeeds, the manual ZIP/installer loop is
considered solved and focus can return to Character/runtime/UI completion. Do not touch `core/`,
reopen scoring architecture, or weaken source validation/frozen smoke testing.

Security/distribution items still pending before broad public release:
- Windows code signing / reputation,
- DPAPI or equivalent protection for local API secrets,
- full Layer-1 runtime integration into the Qt installed app.

Before your context runs out, or once you've made real progress: add a
new entry to DEVLOG.md (template is in that file, most recent entry
goes on top) and update the "CURRENT FOCUS RIGHT NOW" section of this
file (NEXT_CHAT_PROMPT.md) so the next chat starts exactly where you
left off — don't let this section go stale the way it did between
sessions before this one. Tell me directly, in your last message, that
you've updated both files, so I know to re-download the project before
opening a new chat.
