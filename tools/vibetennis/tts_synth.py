#!/usr/bin/env python3
"""vibetennis 中文配音合成：读 <集>/narration.json，逐句用 edge-tts 合成到 <集>/voice/<file>.mp3，
并写词边界 <集>/voice/<file>.json（格式同 EP03–EP05：[{type:'WordBoundary', off, dur, text}]，秒）。

只重合成 tts 文本、声线或语速变了的句子（哈希记在 voice/_tts_hash.json），没变的不动。
会话沙箱能连上：edge-tts 的 SSL 上下文写死了 certifi，碰上代理的自签 CA 就报 CERTIFICATE_VERIFY_FAILED
（看起来像「连不上」）。下面检测到代理 CA（/root/.ccr/ca-bundle.crt 或 SSL_CERT_FILE）就换上它（2026-11-05 实测，EP08 41 句在会话里合成）。
GitHub Actions 上照旧可以跑：.github/workflows/vibetennis-tts.yml。

    python3 tools/vibetennis/tts_synth.py tools/vibetennis/episodes/<slug>
"""
import asyncio, hashlib, json, sys
from pathlib import Path
import edge_tts
import os, ssl
import edge_tts.communicate as _etc
_CA = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.isfile(_CA):
    _etc._SSL_CTX = ssl.create_default_context(cafile=_CA)

async def synth(text, voice, rate, mp3, js):
    c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    wb = []
    with open(mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                wb.append({"type": "WordBoundary", "off": ch["offset"] / 1e7, "dur": ch["duration"] / 1e7, "text": ch["text"]})
    if not wb: raise RuntimeError(f"{mp3.name}：没有拿到词边界")
    js.write_text(json.dumps(wb, ensure_ascii=False))

async def main(ep):
    ep = Path(ep); d = json.loads((ep / "narration.json").read_text())
    vd = ep / "voice"; vd.mkdir(exist_ok=True); hp = vd / "_tts_hash.json"
    old = json.loads(hp.read_text()) if hp.exists() else {}; new = {}; done = 0
    for l in d["lines"]:
        f = l["file"]; h = hashlib.sha1(f'{d["voice"]}|{d["rate"]}|{l["tts"]}'.encode()).hexdigest()[:16]; new[f] = h
        if old.get(f) == h and (vd / f"{f}.mp3").exists() and (vd / f"{f}.json").exists(): continue
        for attempt in range(4):
            try: await synth(l["tts"], d["voice"], d["rate"], vd / f"{f}.mp3", vd / f"{f}.json"); break
            except Exception as e:
                print(f"{f} 第 {attempt+1} 次失败：{e}"); await asyncio.sleep(2 ** attempt)
        else: raise SystemExit(f"{f} 合成失败")
        done += 1; print(f"{f} ✓ {l['tts']}")
    for f in set(old) - set(new):
        for ext in ("mp3", "json"): (vd / f"{f}.{ext}").unlink(missing_ok=True)
    hp.write_text(json.dumps(new, ensure_ascii=False, indent=1)); print(f"合成 {done} 句，共 {len(new)} 句")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
