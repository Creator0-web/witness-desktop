"""Small, dependency-free Windows updater for WITNESS.

Distribution model:
- GitHub Releases hosts one installer asset named ``WITNESS-Setup.exe`` plus
  ``WITNESS-Setup.exe.sha256``.
- A packaged build embeds ``release_channel.json`` with the repository slug.
- WITNESS checks the latest stable release in a background thread.
- If a newer version exists, the UI offers one-click Update & Restart.
- The installer replaces only program files. Personal data lives separately in
  the local profile created by ``profile_runtime.py``.

The source-tree ``release_channel.json`` intentionally leaves ``repository``
blank. The GitHub Actions release workflow writes the real repository slug into
it immediately before building the Windows package. This prevents development
copies from accidentally contacting or self-updating from the wrong project.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

from app_version import VERSION

_USER_AGENT = f"WITNESS/{VERSION} desktop-updater"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _bundle_root() -> Path:
    """Location of bundled read-only assets, or the source root in dev."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()
    return Path(__file__).resolve().parent


def _read_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def channel_config() -> dict:
    cfg = _read_json(_bundle_root() / "release_channel.json", {})
    if not isinstance(cfg, dict):
        cfg = {}
    try:
        check_minutes = int(cfg.get("check_minutes") or 0)
    except Exception:
        check_minutes = 0
    if check_minutes <= 0:
        try:
            check_minutes = max(60, int(cfg.get("check_hours") or 6) * 60)
        except Exception:
            check_minutes = 360
    return {
        "channel": str(cfg.get("channel") or "stable"),
        "repository": str(cfg.get("repository") or "").strip(),
        "asset_name": str(cfg.get("asset_name") or "WITNESS-Setup.exe"),
        "sha256_asset_name": str(
            cfg.get("sha256_asset_name") or "WITNESS-Setup.exe.sha256"),
        "check_minutes": max(1, check_minutes),
        # Retained for older callers/config files. New Qt builds schedule by minutes.
        "check_hours": max(1, (max(1, check_minutes) + 59) // 60),
    }


def configured() -> bool:
    repo = channel_config()["repository"]
    return bool(_REPO_RE.fullmatch(repo))


def _version_tuple(value: str) -> tuple[int, ...]:
    text = str(value or "").strip().lower()
    if text.startswith("v"):
        text = text[1:]
    # Stable WITNESS releases are numeric semver-like tags (v7.52.0). Ignore
    # suffixes defensively so v7.52.0-hotfix still compares as 7.52.0.
    nums = re.findall(r"\d+", text)
    if not nums:
        return (0,)
    return tuple(int(x) for x in nums[:4])


def is_newer(candidate: str, current: str = VERSION) -> bool:
    a = list(_version_tuple(candidate))
    b = list(_version_tuple(current))
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return tuple(a) > tuple(b)


def _urlopen(req, timeout):
    return urllib.request.urlopen(req, timeout=timeout)


def _fetch_json(url: str, timeout: int = 8) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with _urlopen(req, timeout=timeout) as response:
        raw = response.read()
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError("Update service returned an unexpected response.")
    return obj


def check_latest(timeout: int = 8) -> dict:
    """Return update status without mutating the installation."""
    cfg = channel_config()
    repo = cfg["repository"]
    if not _REPO_RE.fullmatch(repo):
        return {
            "enabled": False,
            "available": False,
            "current_version": VERSION,
            "reason": "release hosting is not configured in this development build",
        }

    payload = _fetch_json(
        f"https://api.github.com/repos/{repo}/releases/latest", timeout=timeout)
    if payload.get("draft") or payload.get("prerelease"):
        return {
            "enabled": True,
            "available": False,
            "current_version": VERSION,
            "reason": "latest release is not a stable published release",
        }

    tag = str(payload.get("tag_name") or "").strip()
    latest = tag[1:] if tag.lower().startswith("v") else tag
    assets = payload.get("assets") or []
    by_name = {
        str(x.get("name")): str(x.get("browser_download_url"))
        for x in assets
        if isinstance(x, dict) and x.get("name") and x.get("browser_download_url")
    }
    installer_url = by_name.get(cfg["asset_name"], "")
    sha_url = by_name.get(cfg["sha256_asset_name"], "")
    available = bool(tag and is_newer(latest) and installer_url and sha_url)

    result = {
        "enabled": True,
        "available": available,
        "current_version": VERSION,
        "latest_version": latest,
        "tag": tag,
        "release_name": str(payload.get("name") or tag or latest),
        "release_url": str(payload.get("html_url") or ""),
        "installer_url": installer_url,
        "sha256_url": sha_url,
        "asset_name": cfg["asset_name"],
        "published_at": str(payload.get("published_at") or ""),
    }
    if tag and is_newer(latest) and not available:
        result["reason"] = "new release exists but its installer/hash assets are incomplete"
    return result


def _download_bytes(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with _urlopen(req, timeout=timeout) as response:
        return response.read()


def download_update(release: dict,
                    progress: Callable[[int], None] | None = None) -> Path:
    """Download and SHA-256 verify the installer for a checked release."""
    installer_url = str(release.get("installer_url") or "")
    sha_url = str(release.get("sha256_url") or "")
    if not installer_url or not sha_url:
        raise RuntimeError("The update release is missing its installer or SHA-256 file.")

    expected_text = _download_bytes(sha_url).decode("utf-8", errors="replace").strip()
    expected = expected_text.split()[0].lower() if expected_text else ""
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("The update SHA-256 file is invalid.")

    version = str(release.get("latest_version") or "update")
    dest_dir = Path(tempfile.gettempdir()) / "WITNESS Updates" / version
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_path = dest_dir / "WITNESS-Setup.exe"
    part_path = dest_dir / "WITNESS-Setup.exe.part"

    req = urllib.request.Request(installer_url, headers={"User-Agent": _USER_AGENT})
    digest = hashlib.sha256()
    with _urlopen(req, timeout=60) as response, part_path.open("wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        last_pct = -1
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress and total > 0:
                pct = max(0, min(100, int(done * 100 / total)))
                if pct != last_pct:
                    last_pct = pct
                    progress(pct)

    actual = digest.hexdigest().lower()
    if actual != expected:
        try:
            part_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise RuntimeError("Update download failed integrity verification.")
    os.replace(part_path, final_path)
    if progress:
        progress(100)
    return final_path


def launch_update_and_restart(installer_path: str | Path) -> Path:
    """Schedule an Inno Setup update after the current app exits.

    The helper batch waits briefly, runs the per-user installer silently, and
    reopens the installed WITNESS executable only if setup succeeds.
    """
    if os.name != "nt":
        raise RuntimeError("Automatic installation is only available on Windows.")
    installer = Path(installer_path).resolve()
    if not installer.is_file():
        raise FileNotFoundError(str(installer))

    helper = Path(tempfile.gettempdir()) / "WITNESS Updates" / "apply-witness-update.cmd"
    helper.parent.mkdir(parents=True, exist_ok=True)
    app_exe = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "WITNESS" / "WITNESS.exe"
    # Paths are quoted. Percent signs are not interpolated because concrete
    # absolute paths are written into the temporary helper.
    body = (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'"{installer}" /SP- /SILENT /SUPPRESSMSGBOXES /NORESTART '
        "/CLOSEAPPLICATIONS /NORESTARTAPPLICATIONS\r\n"
        "if errorlevel 1 goto done\r\n"
        f'start "" "{app_exe}" /updated\r\n'
        ":done\r\n"
        'del "%~f0"\r\n'
    )
    helper.write_text(body, encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        ["cmd.exe", "/d", "/c", str(helper)],
        creationflags=flags,
        close_fds=True,
    )
    return helper
