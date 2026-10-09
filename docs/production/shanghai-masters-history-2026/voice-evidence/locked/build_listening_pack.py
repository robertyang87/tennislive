#!/usr/bin/env python3
"""Build a SHA-bound 8-file listening pack. Never records listening or pass."""
import argparse
import hashlib
import html
import json
import shutil
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-root", type=Path, required=True,
                    help="Repository root containing work/ production MP3 files")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    queue = json.loads(Path(__file__).with_name("review-queue.json").read_text())
    groups = {}
    errors = []
    for item in queue["items"]:
        groups.setdefault(item["source_audio_relative"], []).append(item)
    for relative, items in groups.items():
        src = args.audio_root / relative
        expected = {i["source_audio_sha256"] for i in items}
        if not src.is_file():
            errors.append(f"Missing exact production audio: {relative}")
        elif len(expected) != 1 or hashlib.sha256(src.read_bytes()).hexdigest() not in expected:
            errors.append(f"SHA mismatch: {relative}; cannot reuse old evidence")
    if errors:
        print(json.dumps({"status": "blocked", "errors": errors}, ensure_ascii=False, indent=2))
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for num, (relative, items) in enumerate(groups.items(), 1):
        src = args.audio_root / relative
        name = f"audio-{num:02d}.mp3"
        shutil.copyfile(src, args.output / name)
        targets = []
        for item in items:
            window = item["source_window_seconds"]
            locator = "整段听核，保留前后语境" if not window else f"字位约 {window[0]}–{window[1]} 秒"
            targets.append(
                f'<li>{html.escape(str(item["segment"]))} / '
                f'{html.escape(item["word"])} 第{item["occurrence"]}处：'
                f'{html.escape(item["char"])} = <b>{html.escape(item["target_reading"])}</b>；'
                f'{html.escape(locator)}。现有证据：'
                f'{html.escape(item["prior_verdict"])} / '
                f'{html.escape(str(item["prior_confidence"]))}，待核。</li>')
        rows.append(f'<section><h2>音频 {num}</h2><audio controls preload="metadata" src="{name}"></audio>'
                    f'<p>{html.escape(items[0]["narration"])}</p><ul>{"".join(targets)}</ul>'
                    f'<details><summary>原音 SHA-256</summary><code>{items[0]["source_audio_sha256"]}</code>'
                    f'</details></section>')
    page = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>上海大师赛 · 最小语音听核包</title>'
            '<style>body{font:17px/1.65 system-ui;max-width:850px;margin:32px auto;padding:0 18px}'
            'section{border-top:1px solid #bbb;padding:18px 0}audio{width:100%}code{word-break:break-all}</style>'
            '<h1>上海大师赛 · 最小语音听核包</h1>'
            '<p>8份实际原音，12个待核目标。所有文件已校验生产 SHA；本页面不记录或自动判定通过。</p>'
            '<p>按语境核目标音节及完整词，逐项记录听核者、时间、听到的读音和 SHA。'
            '听不清继续待核。重点通过后仍须完整播放最终混音，不能代替全片听核。</p>'
            + "".join(rows) + '</html>')
    (args.output / "index.html").write_text(page, encoding="utf-8")
    (args.output / "review-queue.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "pack_built", "audio_files": len(groups), "targets": len(queue["items"]),
                      "human_listened": False, "publishing_voice_pass": False}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

