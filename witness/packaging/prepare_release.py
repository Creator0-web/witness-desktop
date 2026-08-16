"""Validate release version and embed the public update repository for CI."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, help="owner/repository")
    parser.add_argument("--tag", required=True, help="release tag, e.g. v7.52.0")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        raise SystemExit("Invalid GitHub repository slug")

    import sys
    sys.path.insert(0, str(ROOT))
    from app_version import VERSION

    tag_version = args.tag[1:] if args.tag.lower().startswith("v") else args.tag
    if tag_version != VERSION:
        raise SystemExit(
            f"Release tag {args.tag!r} does not match app_version.VERSION={VERSION!r}")

    path = ROOT / "release_channel.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["repository"] = args.repository
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared WITNESS {VERSION} for update repository {args.repository}")


if __name__ == "__main__":
    main()
