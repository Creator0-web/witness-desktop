Paste this whole message into a new chat to continue work on WITNESS.

---

I'm continuing work on WITNESS, a Python desktop app (Windows; legacy Tkinter full runtime +
PySide6 installed-app shell) built across many prior chats. Before doing or suggesting anything:
read ARCHITECTURE.md and DEVLOG.md in the project root, in full — not just skim them.

⚠️ If `secrets.json` exists in this project, never read, open, or ask to see its contents — it
holds real API keys in plain text. Also never expose/read `sync_profile.json`; it contains the
private WITNESS cross-device profile secret. Skip both entirely.

ARCHITECTURE.md explains the folder structure and the hard rule: `core/` is frozen. Don't touch
anything in it unless I explicitly say so in this conversation. DEVLOG.md is the running history;
read every entry because older decisions still apply.

CURRENT FOCUS RIGHT NOW:
**v7.59.1 / Qt build `2026-09-16-a` — Activity Delete + Sync Patch** is the current source. WITNESS Sync V1 remains the active cross-device architecture. The immediate patch exposes the existing safe backend Activity-deactivation path in the modern Settings UI. Rapid Screen Guard is working well and remains frozen; recorder A/V sync remains Windows-approved.

WHAT v7.59.1 CHANGES:
- Settings -> ACTIVITIES now shows **Edit** and **Delete** on every active Activity.
- Delete is confirmed and deactivates the Activity; it does **not** erase historical XP, Ghost/record history, or old Calendar entries.
- Linked WITNESS Sync devices receive the Activity `active=false` change through the existing sync model; a background sync is nudged immediately and the normal ~15-second cycle remains the fallback.
- No `core/`, `shared/game_engine.py`, `shared/db.py`, cloud RPC, XP/Level math, recorder, Character/3D or Factory Reset behavior changed.

WITNESS SYNC V1 STILL IN PLACE:
- Every device still keeps a normal local `%LOCALAPPDATA%\WITNESS\witness.db` and works offline. Sync is additive, not a cloud-only rewrite.
- Settings -> WITNESS SYNC can Create Sync Profile, Link Existing Profile, Sync Now, Copy Link Code, Unlink This Device and Copy Cloud Setup SQL.
- A compact top-bar SYNC badge shows local / linked / syncing / synced / offline state.
- Sync runs at startup, about every 15 seconds, on app reactivation and shortly after Arena scoring. Network work stays off the GUI thread.
- V1 syncs Activity definitions, immutable XP events including Undo/reversals, daily notes, player name/mission, Character environment and Core Reserve clock.
- Ghost, records, Level and Character form are recomputed locally from the merged XP ledger; synthetic demo XP is not synced.
- Daily/SOS video files, raw Screen Guard/computer telemetry, integration secrets and backups stay device-local in V1.
- `sync_profile.json` contains the private local sync credential and is excluded from release cleanup/validation, backups and profile exports. Treat a copied Link Code like a password.
- Factory Reset unlinks the device locally so old cloud XP cannot immediately repopulate a fresh run; it does not delete the remote cloud profile.
- **No `core/` file changed. `shared/game_engine.py` did not change. Drift protection, recorder sync and scoring semantics remain frozen.**

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.59.1`; wait for GitHub Actions green and Update & Restart on the desktop.
2. Create/open a Supabase project. In WITNESS Settings -> WITNESS SYNC click **Copy Cloud Setup SQL**, paste it into Supabase SQL Editor and run it once.
3. From Supabase copy only the Project URL and **Publishable** key into WITNESS. Never use/paste a secret/service-role key into the app.
4. Desktop: click **Create Sync Profile**, then **Copy Link Code** and store that code privately.
5. Laptop: install/update the same v7.59.1 release -> Settings -> WITNESS SYNC -> **Link Existing Profile** -> paste the Link Code. Linking first creates a local safety backup, then replaces that laptop's sync/scoring domain with the cloud profile.
6. Test both directions: on one device add one +1,000 Booked Job; after ~15 seconds or app reactivation, confirm the other device shows it. Then Undo that booking on the other device and confirm the reversal propagates back.
7. If the Supabase SQL Editor or Windows network path errors, capture the exact error/status text. The local fake-provider two-device merge tests pass, but a real hosted Supabase project is the authoritative acceptance test.

KNOWN LIMITATIONS / DO NOT HIDE:
- Actual cloud/Supabase RPC behavior and Windows two-device operation cannot be fully proven in the Linux sandbox; local compile + fake-provider cross-device tests are the pre-release check.
- V1 does not cloud-sync daily/SOS video files or raw drift telemetry.
- The Link Code is base64url encoded, not encryption; anyone who has it can link to that WITNESS profile. Keep it private.
- `sync_profile.json` stores the WITNESS profile secret locally in plain text for V1; Windows credential protection/DPAPI is future hardening. Never read/open/share it.
- ScreenVision sends captured browser-screen imagery to Anthropic for FLAG/SAFE classification; this legacy design requires the configured Anthropic integration.
- The 3D Lab remains a procedural interaction prototype; production rigged 3D is paused.
- `secrets.json` remains plaintext in the isolated local profile; never read/open/share it. DPAPI and Windows code signing remain future distribution hardening.

Before ending meaningful work: add a NEW entry at the top of DEVLOG.md (never rewrite/delete old
entries) and update this CURRENT FOCUS section. Tell me directly that both files were updated.
