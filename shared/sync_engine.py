"""WITNESS Sync V1.

Cross-device sync is deliberately separated from the canonical game engine.
Each Windows device keeps its own SQLite database and continues working fully
offline.  The sync layer assigns stable UUIDs to the local Activity / XP / Note
rows and exchanges small JSON snapshots with a hosted provider.

V1 provider: Supabase Postgres RPC (see cloud/supabase_witness_sync.sql).
The public Supabase publishable key is only a project identifier; access to a
WITNESS profile additionally requires a high-entropy profile secret.  The
server stores only a SHA-256 hash of that secret.  There is no service-role key
or other elevated credential in the desktop application.

A future self-hosted provider can implement the same create/link/push/pull
contract without changing scoring or the Qt UI.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import secrets
import socket
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import db

CONFIG_FILE = "sync_profile.json"
CONFIG_VERSION = 1
PROVIDER = "supabase_rpc_v1"
LINK_PREFIX = "W1."
SYNC_INTERVAL_SECONDS = 15
MAX_PUSH_ITEMS = 250
MAX_PULL_ITEMS = 500


class SyncError(RuntimeError):
    pass


class SyncNotConfigured(SyncError):
    pass


def _now() -> float:
    return time.time()


def _config_path() -> Path:
    return Path(CONFIG_FILE)


def _read_json(path: Path, default=None):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def _write_json_atomic(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _normalize_url(value: str) -> str:
    value = str(value or "").strip().rstrip("/")
    if not value:
        raise ValueError("Cloud Project URL is required.")
    if not value.lower().startswith("https://"):
        raise ValueError("Cloud Project URL must start with https://")
    return value


def _normalize_key(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError("Supabase publishable key is required.")
    return value


def _new_secret() -> str:
    # 160 bits of entropy, encoded in human-safe Base32 groups. This secret is
    # effectively the WITNESS account recovery/link key; it must remain private.
    raw = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    return "WTN-" + "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def _new_device_id() -> str:
    return str(uuid.uuid4())


def default_device_name() -> str:
    host = socket.gethostname().strip() or platform.node().strip() or "Windows PC"
    return host[:80]


def load_config() -> dict:
    cfg = _read_json(_config_path(), {})
    return cfg if isinstance(cfg, dict) else {}


def is_linked() -> bool:
    cfg = load_config()
    return bool(cfg.get("enabled") and cfg.get("profile_id") and cfg.get("secret") and cfg.get("url") and cfg.get("publishable_key"))


def public_status() -> dict:
    cfg = load_config()
    linked = is_linked()
    return {
        "linked": linked,
        "provider": cfg.get("provider", ""),
        "profile_id": cfg.get("profile_id", ""),
        "device_id": cfg.get("device_id", ""),
        "device_name": cfg.get("device_name", default_device_name()),
        "last_revision": int(cfg.get("last_revision", 0) or 0),
        "last_sync_at": float(cfg.get("last_sync_at", 0) or 0),
        "last_error": str(cfg.get("last_error", "") or ""),
        "last_push_count": int(cfg.get("last_push_count", 0) or 0),
        "last_pull_count": int(cfg.get("last_pull_count", 0) or 0),
    }


def _save_config(cfg: dict) -> dict:
    cfg = dict(cfg)
    cfg["schema"] = CONFIG_VERSION
    cfg["provider"] = PROVIDER
    _write_json_atomic(_config_path(), cfg)
    return cfg


def unlink_local() -> None:
    try:
        _config_path().unlink(missing_ok=True)
    except Exception as ex:
        raise SyncError(f"Could not unlink this device: {ex}") from ex


def encode_link_code(cfg: dict | None = None) -> str:
    cfg = dict(cfg or load_config())
    if not (cfg.get("url") and cfg.get("publishable_key") and cfg.get("secret")):
        raise SyncNotConfigured("WITNESS Sync is not linked yet.")
    payload = {
        "v": 1,
        "p": PROVIDER,
        "u": str(cfg["url"]),
        "k": str(cfg["publishable_key"]),
        "s": str(cfg["secret"]),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return LINK_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_link_code(code: str) -> dict:
    code = str(code or "").strip()
    if not code.startswith(LINK_PREFIX):
        raise ValueError("That does not look like a WITNESS Link Code.")
    raw = code[len(LINK_PREFIX):]
    raw += "=" * ((4 - len(raw) % 4) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
    except Exception as ex:
        raise ValueError("That WITNESS Link Code is damaged or incomplete.") from ex
    if payload.get("v") != 1 or payload.get("p") != PROVIDER:
        raise ValueError("That Link Code uses an unsupported sync version.")
    return {
        "url": _normalize_url(payload.get("u", "")),
        "publishable_key": _normalize_key(payload.get("k", "")),
        "secret": str(payload.get("s", "")).strip(),
    }


class SupabaseProvider:
    def __init__(self, url: str, publishable_key: str):
        self.url = _normalize_url(url)
        self.key = _normalize_key(publishable_key)

    def _rpc(self, name: str, payload: dict, timeout=10):
        endpoint = f"{self.url}/rest/v1/rpc/{name}"
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=body, method="POST",
            headers={
                "apikey": self.key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "WITNESS-Sync/1",
            })
        try:
            with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
                raw = resp.read().decode("utf-8", errors="replace").strip()
        except urllib.error.HTTPError as ex:
            try:
                detail = ex.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            raise SyncError(f"Cloud returned HTTP {ex.code}: {detail or ex.reason}") from ex
        except urllib.error.URLError as ex:
            raise SyncError(f"Cloud is unreachable: {getattr(ex, 'reason', ex)}") from ex
        except TimeoutError as ex:
            raise SyncError("Cloud sync timed out.") from ex
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip('"')

    def create_profile(self, secret: str, device_id: str, device_name: str) -> str:
        out = self._rpc("witness_create_profile", {
            "p_secret": secret,
            "p_device_id": device_id,
            "p_device_name": device_name,
        })
        if not out:
            raise SyncError("Cloud profile was not created.")
        return str(out)

    def link_profile(self, secret: str, device_id: str, device_name: str) -> str:
        out = self._rpc("witness_link_profile", {
            "p_secret": secret,
            "p_device_id": device_id,
            "p_device_name": device_name,
        })
        if not out:
            raise SyncError("That Link Code did not match a cloud WITNESS profile.")
        return str(out)

    def push(self, cfg: dict, items: list[dict]) -> dict:
        out = self._rpc("witness_sync_push", {
            "p_profile_id": cfg["profile_id"],
            "p_secret": cfg["secret"],
            "p_device_id": cfg["device_id"],
            "p_device_name": cfg.get("device_name", default_device_name()),
            "p_items": items,
        }, timeout=15)
        return dict(out or {}) if isinstance(out, dict) else {}

    def pull(self, cfg: dict, after_revision: int, limit: int = MAX_PULL_ITEMS) -> dict:
        out = self._rpc("witness_sync_pull", {
            "p_profile_id": cfg["profile_id"],
            "p_secret": cfg["secret"],
            "p_device_id": cfg["device_id"],
            "p_device_name": cfg.get("device_name", default_device_name()),
            "p_after_revision": int(after_revision),
            "p_limit": int(limit),
        }, timeout=15)
        return dict(out or {}) if isinstance(out, dict) else {}


def _provider(cfg: dict) -> SupabaseProvider:
    if cfg.get("provider", PROVIDER) != PROVIDER:
        raise SyncError("Unsupported WITNESS Sync provider.")
    return SupabaseProvider(cfg["url"], cfg["publishable_key"])


def create_profile(url: str, publishable_key: str, device_name: str | None = None) -> dict:
    url = _normalize_url(url); publishable_key = _normalize_key(publishable_key)
    secret = _new_secret(); device_id = _new_device_id(); device_name = (device_name or default_device_name()).strip()[:80]
    provider = SupabaseProvider(url, publishable_key)
    profile_id = provider.create_profile(secret, device_id, device_name)
    cfg = _save_config({
        "enabled": True,
        "url": url,
        "publishable_key": publishable_key,
        "profile_id": profile_id,
        "secret": secret,
        "device_id": device_id,
        "device_name": device_name,
        "created_at": _now(),
        "last_revision": 0,
        "last_sync_at": 0,
        "last_error": "",
    })
    return {**public_status(), "link_code": encode_link_code(cfg)}


def link_profile(code: str, device_name: str | None = None, *, replace_local=True) -> dict:
    bundle = decode_link_code(code)
    device_id = _new_device_id(); device_name = (device_name or default_device_name()).strip()[:80]
    provider = SupabaseProvider(bundle["url"], bundle["publishable_key"])
    profile_id = provider.link_profile(bundle["secret"], device_id, device_name)
    if replace_local:
        db.sync_clear_profile_domain()
    cfg = _save_config({
        "enabled": True,
        "url": bundle["url"],
        "publishable_key": bundle["publishable_key"],
        "profile_id": profile_id,
        "secret": bundle["secret"],
        "device_id": device_id,
        "device_name": device_name,
        "created_at": _now(),
        "last_revision": 0,
        "last_sync_at": 0,
        "last_error": "",
    })
    return {**public_status(), "link_code": encode_link_code(cfg)}


def _stable_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _signature(payload: dict) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _activity_payload(row: dict) -> dict:
    return {
        "name": str(row.get("name", "")),
        "xp_value": int(row.get("xp_value", 0) or 0),
        "kind": str(row.get("kind", "repeatable")),
        "active": bool(row.get("active", True)),
        "sort_order": int(row.get("sort_order", 0) or 0),
        "created_ts": float(row.get("created_ts", 0) or 0),
        "updated_ts": float(row.get("updated_ts", 0) or 0),
    }


def _collect_local_items() -> tuple[list[dict], list[tuple[str, str, str]]]:
    """Return cloud items plus map markers to mark only after a successful push."""
    items: list[dict] = []
    markers: list[tuple[str, str, str]] = []

    activity_sync_by_local: dict[int, str] = {}
    for row in db.sync_activity_rows():
        local_id = int(row["id"])
        mapping = db.sync_map_ensure("activity", local_id)
        sync_id = mapping["sync_id"]; activity_sync_by_local[local_id] = sync_id
        payload = _activity_payload(row); sig = _signature(payload)
        if mapping.get("last_uploaded_sig") != sig:
            items.append({
                "entity_type": "activity", "entity_id": sync_id,
                "modified_ts": float(payload["updated_ts"] or _now()), "payload": payload,
            })
            markers.append(("activity", str(local_id), sig))

    xp_rows = db.sync_xp_rows()
    xp_sync_by_local: dict[int, str] = {}
    # Establish all IDs first so reversals can reference an event that has not
    # yet been serialized in this pass.
    for row in xp_rows:
        lid = int(row["id"])
        xp_sync_by_local[lid] = db.sync_map_ensure("xp_event", lid)["sync_id"]
    for row in xp_rows:
        local_id = int(row["id"])
        mapping = db.sync_map_get_by_local("xp_event", local_id) or db.sync_map_ensure("xp_event", local_id)
        aid = row.get("activity_id")
        rid = row.get("reverses_event_id")
        payload = {
            "ts": float(row.get("ts", 0) or 0),
            "day": str(row.get("day", "")),
            "activity_sync_id": activity_sync_by_local.get(int(aid)) if aid is not None else None,
            "activity_name": str(row.get("activity_name", "")),
            "event_type": str(row.get("event_type", "activity")),
            "quantity": float(row.get("quantity", 1) or 0),
            "base_xp": int(row.get("base_xp", 0) or 0),
            "score_xp": int(row.get("score_xp", 0) or 0),
            "level_xp": int(row.get("level_xp", 0) or 0),
            "level_multiplier": float(row.get("level_multiplier", 1.0) or 1.0),
            "reverses_sync_id": xp_sync_by_local.get(int(rid)) if rid is not None else None,
            "source": str(row.get("source", "manual")),
            "metadata": row.get("metadata"),
        }
        sig = _signature(payload)
        if mapping.get("last_uploaded_sig") != sig:
            items.append({
                "entity_type": "xp_event", "entity_id": mapping["sync_id"],
                "modified_ts": float(payload["ts"] or _now()), "payload": payload,
            })
            markers.append(("xp_event", str(local_id), sig))

    for row in db.sync_note_rows():
        local_id = int(row["id"])
        mapping = db.sync_map_ensure("note", local_id)
        payload = {"ts": float(row.get("ts", 0) or 0), "day": str(row.get("day", "")), "text": str(row.get("text", ""))}
        sig = _signature(payload)
        if mapping.get("last_uploaded_sig") != sig:
            items.append({
                "entity_type": "note", "entity_id": mapping["sync_id"],
                "modified_ts": float(payload["ts"] or _now()), "payload": payload,
            })
            markers.append(("note", str(local_id), sig))

    for row in db.syncable_game_state_rows():
        key = str(row["key"])
        payload = {"key": key, "value": str(row.get("value", ""))}
        sig = _signature(payload)
        marker_key = "state_sig:" + key
        if db.sync_runtime_get(marker_key, "") != sig:
            items.append({
                "entity_type": "state", "entity_id": key,
                "modified_ts": float(row.get("updated_ts", 0) or _now()), "payload": payload,
            })
            markers.append(("state", key, sig))

    return items, markers


def _mark_uploaded(markers: list[tuple[str, str, str]]) -> None:
    for entity_type, local_id, sig in markers:
        if entity_type == "state":
            db.sync_runtime_set("state_sig:" + local_id, sig)
        else:
            db.sync_map_mark_uploaded(entity_type, local_id, sig)


def _apply_remote_items(items: list[dict]) -> dict:
    changed = 0; xp_changed = False
    activities = [x for x in items if x.get("entity_type") == "activity"]
    xp = [x for x in items if x.get("entity_type") == "xp_event"]
    notes = [x for x in items if x.get("entity_type") == "note"]
    states = [x for x in items if x.get("entity_type") == "state"]

    for item in activities:
        sid = str(item.get("entity_id", "")); payload = dict(item.get("payload") or {})
        if not sid:
            continue
        local_id = db.sync_upsert_activity(sid, payload)
        sig = _signature(_activity_payload({**payload, "id": local_id}))
        db.sync_map_mark_uploaded("activity", local_id, sig)
        changed += 1

    # Positive/source events first, then reversals whose local FK can now resolve.
    normal = [x for x in xp if not (dict(x.get("payload") or {}).get("reverses_sync_id"))]
    reversals = [x for x in xp if dict(x.get("payload") or {}).get("reverses_sync_id")]
    for item in normal + reversals:
        sid = str(item.get("entity_id", "")); payload = dict(item.get("payload") or {})
        if not sid:
            continue
        local_id, inserted = db.sync_insert_xp_event(sid, payload)
        if local_id is None:
            continue
        db.sync_map_mark_uploaded("xp_event", local_id, _signature(payload))
        if inserted:
            changed += 1; xp_changed = True

    # Retry any reversal whose referenced positive event arrived later in the same page.
    for item in reversals:
        sid = str(item.get("entity_id", "")); payload = dict(item.get("payload") or {})
        if db.sync_map_get_by_sync("xp_event", sid):
            continue
        local_id, inserted = db.sync_insert_xp_event(sid, payload)
        if local_id is not None:
            db.sync_map_mark_uploaded("xp_event", local_id, _signature(payload))
            if inserted:
                changed += 1; xp_changed = True

    for item in notes:
        sid = str(item.get("entity_id", "")); payload = dict(item.get("payload") or {})
        if not sid:
            continue
        local_id, inserted = db.sync_insert_note(sid, payload)
        db.sync_map_mark_uploaded("note", local_id, _signature(payload))
        if inserted:
            changed += 1

    for item in states:
        payload = dict(item.get("payload") or {})
        key = str(payload.get("key", item.get("entity_id", "")))
        if not key:
            continue
        if db.game_state_set_remote(key, payload.get("value", ""), item.get("modified_ts", 0)):
            db.sync_runtime_set("state_sig:" + key, _signature({"key": key, "value": str(payload.get("value", ""))}))
            changed += 1

    if xp_changed:
        try:
            import game_engine
            game_engine._reconcile_level_state_after_correction()  # exact ledger reconciliation after merge
        except Exception:
            try:
                db.game_state_delete("rolling_level_v1")
                db.game_state_set("character_peak_reconcile_v1", "1")
            except Exception:
                pass
    return {"changed": changed, "xp_changed": xp_changed}


def sync_once() -> dict:
    cfg = load_config()
    if not is_linked():
        raise SyncNotConfigured("WITNESS Sync is not linked on this device.")
    provider = _provider(cfg)
    local_items, markers = _collect_local_items()
    pushed = 0
    # Do not mark a local item uploaded until the specific cloud batch succeeds.
    marker_by_identity = {(t, lid): sig for t, lid, sig in markers}
    for i in range(0, len(local_items), MAX_PUSH_ITEMS):
        batch = local_items[i:i + MAX_PUSH_ITEMS]
        provider.push(cfg, batch)
        pushed += len(batch)
        # Mark only entities present in this successful batch.
        completed = []
        for cloud_item in batch:
            et = cloud_item["entity_type"]; sid = cloud_item["entity_id"]
            if et == "state":
                sig = marker_by_identity.get(("state", sid))
                if sig:
                    completed.append(("state", sid, sig))
            else:
                mapped = db.sync_map_get_by_sync(et, sid)
                if mapped:
                    sig = marker_by_identity.get((et, str(mapped["local_id"])))
                    if sig:
                        completed.append((et, str(mapped["local_id"]), sig))
        _mark_uploaded(completed)

    cursor = int(cfg.get("last_revision", 0) or 0)
    pulled = 0; changed = 0; pages = 0
    while pages < 20:
        pages += 1
        out = provider.pull(cfg, cursor, MAX_PULL_ITEMS)
        rows = list(out.get("items") or [])
        result = _apply_remote_items(rows)
        pulled += len(rows); changed += int(result.get("changed", 0) or 0)
        next_cursor = int(out.get("latest_revision", cursor) or cursor)
        cursor = max(cursor, next_cursor)
        if not out.get("has_more") or not rows:
            break

    cfg["last_revision"] = cursor
    cfg["last_sync_at"] = _now()
    cfg["last_error"] = ""
    cfg["last_push_count"] = pushed
    cfg["last_pull_count"] = pulled
    _save_config(cfg)
    return {
        "ok": True, "pushed": pushed, "pulled": pulled, "changed": changed,
        "last_revision": cursor, "last_sync_at": cfg["last_sync_at"],
    }


def record_error(message: str) -> None:
    cfg = load_config()
    if not cfg:
        return
    cfg["last_error"] = str(message or "")[:500]
    _save_config(cfg)
