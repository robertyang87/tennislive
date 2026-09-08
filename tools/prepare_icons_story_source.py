#!/usr/bin/env python3
"""Prepare this episode's footage for inspection; never render or publish."""
import argparse
import json
from pathlib import Path

from grab_frames import download, sample, contact_sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=("jordan", "woods", "swiatek", "keys"))
    args = parser.parse_args()
    request = json.loads(Path("requests/stories/zheng-usopen-icons.json").read_text())
    source = request["sources"][args.source]
    out = Path("source-review") / args.source
    out.mkdir(parents=True, exist_ok=True)
    video = download(source["url"], out)
    # Retain source only in the expiring Actions artifact, never commit media.
    frames = sample(video, out, 8.0, 640, 0.0, 0.0)
    contact_sheet(frames, out / "contact.jpg")
    (out / "provenance.json").write_text(json.dumps(source, ensure_ascii=False, indent=2))
    print(f"Prepared {args.source}: {len(frames)} candidate frames; visual review pending")


if __name__ == "__main__":
    main()
