#!/usr/bin/env python3
"""Inspect a finite frozen TTS ZIP; never synthesize or declare QC approval."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))
from tennislive.video.tts_bundle import TTSBundleError, validate_bundle  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--expected-requests', type=Path,
                        help='JSON list of complete current tts_request objects')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--no-decode', action='store_true',
                        help='Integrity/request check only; report explicitly marks audio decode unverified')
    args = parser.parse_args()
    expected = None if args.expected_requests is None else json.loads(args.expected_requests.read_text())
    try:
        report = validate_bundle(args.bundle, expected, decode_audio=not args.no_decode)
    except TTSBundleError as exc:
        parser.exit(2, f'Frozen TTS bundle rejected: {exc}\n')
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding='utf-8')
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
