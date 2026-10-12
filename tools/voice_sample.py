"""One-off on branch tts/wta-finals-race-2026-10-12: synthesize narration
segments for wta-finals-race-2026-10-12 (Yunjian +18% +10Hz) with word timings."""
import asyncio, json, sys, subprocess
from pathlib import Path
import edge_tts
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "output/voice-samples") / "wta-finals-race-2026-10-12"
OUT.mkdir(parents=True, exist_ok=True)
S = json.loads(Path("data/tts-jobs/wta-finals-race-2026-10-12.json").read_text(encoding="utf-8"))
async def go():
    for k, t in S:
        c = edge_tts.Communicate(t, "zh-CN-YunjianNeural", rate="+18%", pitch="+10Hz", boundary="WordBoundary")
        marks = []
        with open(OUT / f"{k}.mp3", "wb") as f:
            async for ch in c.stream():
                if ch["type"] == "audio": f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    marks.append([ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]])
        (OUT / f"{k}.json").write_text(json.dumps(marks, ensure_ascii=False), encoding="utf-8")
        print(k, len(marks))
asyncio.run(go())
