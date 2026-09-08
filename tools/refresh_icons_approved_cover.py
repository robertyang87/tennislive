#!/usr/bin/env python3
"""Replace only the approved opening cover in the immutable reviewed episode."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

def run(args):
    return subprocess.check_output(args, text=True).strip()

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    original = Path("original-review/zheng-usopen-icons.mp4")
    assert digest(original) == "73d757f88fde5daac643776a684a598b73811911fd4cd80eabf6176f99cdbd66"
    out = Path("output/2026-09-08/reel/zheng-usopen-icons")
    out.mkdir(parents=True, exist_ok=True)
    poster = out / "poster.jpg"
    shutil.copyfile("assets/reel/zheng-usopen-icons-approved-cover-v2.jpg", poster)
    shutil.copyfile("original-review/subtitles.ass", out/"subtitles.ass")
    film = out / original.name
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-i",str(original),
        "-loop","1","-i",str(poster),"-filter_complex",
        "[0:v][1:v]overlay=0:0:enable='lt(n,36)':shortest=1[v]",
        "-map","[v]","-map","0:a","-c:v","libx264","-preset","fast","-crf","18",
        "-c:a","copy","-movflags","+faststart","-y",str(film)], check=True)
    def audio_hash(path):
        return run(["ffmpeg","-v","error","-i",str(path),"-map","0:a","-c","copy","-f","hash","-hash","sha256","-"])
    assert audio_hash(original) == audio_hash(film), "Original broadcast/narration audio changed"
    def duration(path):
        return float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(path)]))
    assert abs(duration(original)-duration(film)) < 0.05, "Timeline changed"
    evidence = {"revision":"approved-cover-v2","original_film_sha256":digest(original),
        "poster_sha256":digest(poster),"replaced_frames":[0,35],
        "audio_bitstream_unchanged":True,"duration_unchanged":True,
        "design":"User-approved 品字型, centered transparent headline, original font style and subtitle"}
    (out/"cover_revision.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(evidence,ensure_ascii=False))

if __name__ == "__main__":
    main()
