#!/usr/bin/env python3
"""章节卡、数据统计卡的**动态版**（试点）：同一份 HTML，加一个 `seek(t)` 逐帧渲。

## 来路

账号所有者 2026-10-20 看过 awesome-opus-video-skills 那份索引后同意先做试点：
「赛场之上」一条片子里有 5~6 张静态字卡，而他说过「不要总用字卡」。
做法借自 howseen-ai/claude-motion-design（MIT）：**一切由时间算出来**——页面只
暴露 `window.seek(t)`，没有 CSS transition、没有定时器、帧与帧之间没有状态，
所以同一秒渲两遍逐像素相同（和我们「渲染是确定性的」那条一致）。

版式一个像素都不改：直接复用 `render_title_card.build` / `render_stat_card.build`
的 HTML，只在外面套一层动画脚本。动效守它那份「反 AI 味」守则里和我们口径一致的几条：
一屏只动一样东西（错开先后，不同时乱动）、只用 ease-out（不用弹跳）、
动完就停（3 秒内收住，剩下的时间留给旁白和阅读）。
**数字不做滚动**：滚动的中间帧会出现「35% (58/91)」这种对不上的假数据，
而这个号对数据准确的要求是零容忍；只做整行进场。

    python3 tools/animate_cards.py title --text "第二盘1比6\\n三个发球局全丢" \\
        --kicker "第二盘 · 急转直下" --seconds 6 --out /tmp/title.mp4
    python3 tools/animate_cards.py stat --spec specs/reels/<slug>.json \\
        --seconds 8 --out /tmp/stat.mp4

⚠️ 这是试点工具，还没接进 `build_match_reel.py` 的出片链路；接不接、怎么接
等账号所有者看过并排对照再定。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "src"))

FPS = 25          # 与官方集锦源片一致，接进片子时不用转帧率
SCALE = 2         # 2× 截图再 lanczos 缩回，字边和静态版一样锐

# 所有动画由 t（秒）算出：ease-out 三次方，clamp 在 0~1。
_SEEK_CORE = r"""
<style>*{transition:none!important;animation:none!important}</style>
<script>
const clamp=(x)=>Math.max(0,Math.min(1,x));
const ease=(x)=>1-Math.pow(1-clamp(x),3);
const prog=(t,start,dur)=>ease((t-start)/dur);
window.__ready=false;
"""

_TITLE_JS = r"""
function setup(){
  const th=document.querySelector('.thesis');
  const parts=th.innerHTML.split(/<br\s*\/?>/i);
  th.innerHTML=parts.map(p=>'<span class="ln"><span class="lni">'+p+'</span></span>').join('<br>');
  const st=document.createElement('style');
  st.textContent='.ln{display:inline-block;overflow:hidden;vertical-align:top;padding:0 .08em}.lni{display:inline-block;will-change:transform}';
  document.head.appendChild(st);
}
window.seek=function(t){
  const k=document.querySelector('.kicker');
  if(k){const p=prog(t,0.0,0.45);k.style.opacity=p;k.style.transform='translateY('+(16*(1-p))+'px)';}
  document.querySelectorAll('.lni').forEach((el,i)=>{
    const p=prog(t,0.25+0.2*i,0.6);
    el.style.transform='translateY('+(105*(1-p))+'%)';
  });
  const h=document.querySelector('.handle');
  if(h){h.style.opacity=0.72*prog(t,0.9,0.5);}
};
"""

_STAT_JS = r"""
function setup(){}
window.seek=function(t){
  document.querySelectorAll('.h2h-ring').forEach(el=>{
    const p=prog(t,0.0,0.5);
    el.style.opacity=p;el.style.transform='scale('+(0.92+0.08*p)+')';
  });
  document.querySelectorAll('.h2h-cn,.h2h-flagrow').forEach(el=>{el.style.opacity=prog(t,0.2,0.45);});
  document.querySelectorAll('.h2h-set-row').forEach((el,i)=>{
    const p=prog(t,0.35+0.22*i,0.4);
    el.style.opacity=p;el.style.transform='translateY('+(14*(1-p))+'px)';
  });
  document.querySelectorAll('.h2h-meta').forEach(el=>{el.style.opacity=prog(t,1.0,0.4);});
  document.querySelectorAll('.srow').forEach((row,i)=>{
    const start=1.0+0.13*i, p=prog(t,start,0.4);
    row.style.opacity=p;row.style.transform='translateY('+(18*(1-p))+'px)';
  });
};
"""

_SEEK_TAIL = r"""
document.fonts.ready.then(()=>{setup();window.seek(0);window.__ready=true;});
</script>
"""

# 动画在这一刻之前全部收住；之后的帧和最后一帧逐像素相同，只截一次反复用。
SETTLE = {"title": 1.6, "stat": 2.5}


def _inject(html: str, js: str) -> str:
    tail = _SEEK_CORE + js + _SEEK_TAIL
    if "</body>" in html:
        return html.replace("</body>", tail + "</body>", 1)
    return html + tail


def _shot(tab, t: float) -> bytes:
    tab.evaluate(f"window.seek({t})")
    tab.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
    return tab.screenshot(type="png")


def render_frames(html: str, out: Path, *, size: tuple[int, int], seconds: float,
                  settle: float) -> Path:
    """逐帧 seek(t) → 截图 → ffmpeg 合成 25fps、yuv420p、无声的 mp4。"""
    from render_stat_card import _launch_browser  # noqa: PLC0415
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    w, h = size
    page = out.with_suffix(".anim.html")
    page.write_text(html, encoding="utf-8")
    total = int(round(seconds * FPS))
    moving = min(total, int(round(settle * FPS)) + 1)
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
         "-c:v", "png", "-i", "-", "-vf", f"scale={w}:{h}:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", str(FPS),
         "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    try:
        with sync_playwright() as pw:
            browser = _launch_browser(pw)
            tab = browser.new_page(viewport={"width": w, "height": h},
                                   device_scale_factor=SCALE)
            tab.goto(page.resolve().as_uri())
            tab.wait_for_function("window.__ready === true", timeout=20_000)
            tab.wait_for_function(
                "Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)",
                timeout=15_000)
            for n in range(moving):
                enc.stdin.write(_shot(tab, n / FPS))
            # 静止段一律取动画收住之后的终态（seek 一个远大于动画长度的 t），
            # 不拿「收住时刻」那一帧：收住时刻估短了，终态就会停在半路上。
            final = _shot(tab, 1e3)
            for _ in range(total - moving):
                enc.stdin.write(final)
            browser.close()
    finally:
        enc.stdin.close()
        enc.wait()
        page.unlink(missing_ok=True)
    if enc.returncode != 0 or not out.is_file():
        raise SystemExit(f"动态卡没合成出来：{out}")
    return out


def title_video(text: str, out: Path, *, kicker: str = "", seconds: float,
                size: tuple[int, int] = (1080, 1440)) -> Path:
    import render_title_card  # noqa: PLC0415
    html = render_title_card.build(text, kicker=kicker, size=size)
    return render_frames(_inject(html, _TITLE_JS), out, size=size, seconds=seconds,
                         settle=SETTLE["title"])


def stat_video(spec: dict, out: Path, *, seconds: float) -> Path:
    import render_stat_card  # noqa: PLC0415
    html = render_stat_card.build(spec, variant="film")
    return render_frames(_inject(html, _STAT_JS), out, size=(1080, 1440),
                         seconds=seconds, settle=SETTLE["stat"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="kind", required=True)
    t = sub.add_parser("title")
    t.add_argument("--text", required=True)
    t.add_argument("--kicker", default="")
    s = sub.add_parser("stat")
    s.add_argument("--spec", required=True, type=Path)
    for p in (t, s):
        p.add_argument("--seconds", type=float, default=6.0)
        p.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    if a.kind == "title":
        title_video(a.text.replace("\\n", "\n"), a.out, kicker=a.kicker, seconds=a.seconds)
    else:
        stat_video(json.loads(a.spec.read_text(encoding="utf-8")), a.out, seconds=a.seconds)
    print(f"[动态卡] {a.out}（{a.out.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
