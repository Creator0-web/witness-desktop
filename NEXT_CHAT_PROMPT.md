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
**v7.58.1 / Qt build `2026-08-18-b` — Daily Video Recorder** is the current source.
The person clarified that the recorder is most valuable for repeated **daily calendar videos**, not just long-lived SOS videos. v7.58.0 SOS recording remains available, but the same capture engine is now reused in History. Rapid Screen Guard is working well and must stay frozen unless explicitly requested.

WHAT v7.58.1 CHANGES:
- History → Calendar → selected day → **VIDEOS** now shows **● Record Video** plus **+ Add File**.
- Record Video opens the existing native Qt recorder with Webcam + Mic, Screen + Mic, and Screen + Camera + Mic (Square/Triangle corner overlay).
- The calendar date is frozen when the recorder opens. After Stop, **Submit to Day** routes the clip through `video_memories.add_video(day, path)` so existing day folders, duplicate handling, video list and V marker remain canonical.
- Existing Add File behavior remains; only its button label is clearer.
- Settings → Protection keeps **Record SOS Video** and still submits to `sos_videos/`. Both destinations share one recorder implementation.
- **No `core/` file changed. No XP/Ghost/Level/scoring backend changed.**

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.58.1`; wait for GitHub Actions green and use Update & Restart.
2. History → Calendar → choose today → Videos → Record Video. Test a short **Webcam + Mic** clip, Stop, Submit to Day. Confirm it appears immediately in the selected day and the calendar shows V.
3. Test one short Screen + Mic recording and, if useful, Screen + Camera + Mic.
4. Confirm **+ Add File** still imports an existing clip into the same day.
5. Settings → Protection → confirm the existing SOS recorder still submits to SOS and Rapid Screen Guard remains unchanged.
6. If recording hardware fails, capture the exact recorder/camera/screen error. Do not modify Layer 1 for a multimedia problem.

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
