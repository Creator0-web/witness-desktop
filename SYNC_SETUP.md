# WITNESS Sync V1 — one-time hosted setup

WITNESS remains local-first. Every device keeps its own SQLite profile and works without internet.
The hosted backend only exchanges small Activity / XP / Note / selected Character-state JSON records.
Daily/SOS video files stay local in V1.

## One-time cloud setup

1. Create a Supabase project.
2. Open **SQL Editor** in that project.
3. Paste and run the complete `cloud/supabase_witness_sync.sql` file.
4. In Supabase, copy the **Project URL** and the **Publishable key** (never the secret/service-role key).
5. In WITNESS on the computer that already has your real history: **Settings → WITNESS SYNC → Create Sync Profile**.
6. Paste the Project URL and Publishable key. WITNESS uploads the existing scoring profile.
7. Click **Copy Link Code**.
8. Install WITNESS on the second computer → **Settings → WITNESS SYNC → Link Existing Profile** → paste that Link Code.

The Link Code is effectively the recovery password for this WITNESS profile. Keep it private.

## V1 sync scope

Synced: Activity definitions, immutable XP ledger (including Undo/reversals), daily notes, player name/mission,
Character environment selection and Core clock. Level, Ghost, records and Character form are re-derived from the
synced XP ledger on each device.

Local-only for V1: daily/SOS video files, raw computer tracking, Rapid Screen Guard telemetry, device settings,
API integration secrets and local backups.

## Factory Reset

Factory Reset removes the sync credential from that Windows device so old cloud progress cannot silently repopulate
a freshly reset local profile. The cloud profile itself is not deleted in V1. If another linked device still exists,
you can copy its Link Code again later.
