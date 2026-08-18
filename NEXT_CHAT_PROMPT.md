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
**v7.58.2 / Qt build `2026-08-18-c` — Webcam A/V Sync** is the current source.
Windows testing of v7.58.1 isolated the recorder sync issue very cleanly: **Webcam + Mic has noticeable audio-behind-video lip sync; Screen + Mic and Screen + Camera + Mic are good.** Daily Calendar recording itself works great. Rapid Screen Guard is working well and stays frozen.

WHAT v7.58.2 CHANGES:
- Only the direct camera recorder path is tuned. Camera-only no longer forces exactly 30.0 fps; Qt is allowed to choose the optimal cadence from the camera source/codec.
- Webcam + Mic now starts the camera, shows `SYNCING CAMERA + MICROPHONE…`, waits 500 ms, then calls recorder.record(). The recording timer starts only at record(), so the settle period is not part of the saved clip.
- Screen + Mic and Screen + Camera + Mic remain on the already-good screen path and keep their existing behavior.
- History → Calendar → Videos still has Record Video + Add File; Settings → Protection still has the SOS recorder.
- **No `core/` file changed. No XP/Ghost/Level/scoring backend changed.**

ACTUAL NEXT STEP ON WINDOWS/GITHUB:
1. Publish/tag exactly `v7.58.2`; wait for GitHub Actions green and Update & Restart.
2. History → Calendar → today → Videos → Record Video → Webcam + Mic. Record 8–10 seconds while counting and clap once. Check whether the audio now lands with the mouth/clap.
3. Regression-check one Screen + Mic clip and one Screen + Camera + Mic clip; those should remain synchronized.
4. If webcam-only still has a stable constant offset, measure it approximately (for example ~0.2s / ~0.5s / ~1s). The next technical step should be explicit camera-frame timestamp compensation/custom QVideoFrameInput, not changes to screen capture or Layer 1.

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
