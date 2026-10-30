"""vibetennis 栏目共用的常量与小工具。

vibetennis 是「网球时差」的第四个栏目（账号所有者 2026-10-30：「你帮我单独在
tennislive 里建一个新的子栏目，叫 vibetennis」），做 Vibe 知识风格的 3D 科普：
16:9 横屏、全息科幻质感、字幕锚定在内容旁边、音效跟画面对齐、时长随内容（约 3 分钟）。

它的成片是**本地/会话里用 Three.js 预渲好的整片**，不走 match-reel 那条
「源片 + 旁白 + 3:4」的渲染线，所以 spec 放在 `specs/vibetennis/`、产物放在
`output/<日期>/vibetennis/<slug>/`，质检和推送门禁也是这一栏自己的（`tools/vibetennis/`）。
推送正文、复制页、标题规则、PushPlus 发送、发布账本**复用**赛场之上那套
（`tools/push_reel.py`、`tools/publication_ledger.py`），不另写一份。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLUMN = "vibetennis"
SPEC_DIR = Path("specs/vibetennis")
OUT_KIND = "vibetennis"
LEDGER_COLUMN = "vibetennis"
CANVAS = (1920, 1080)
POSTER_NAME = "poster.jpg"
COVER_FRAME_NAME = "cover_16x9.jpg"   # 不再生成；qc 确认它不在（封面不进视频）
MARKER = "pushed.json"
REVISION_NAME = "publication_revision.json"   # 已推送后的「只换封面」修订单
# `output/2026-10-30/vibetennis/vibetennis-live-faster-2026/render.json`
RENDER_JSON = re.compile(r"^output/(\d{4}-\d\d-\d\d)/vibetennis/([^/]+)/render\.json$")
# 时长随内容走，但这一栏承诺的是「三分钟左右讲清一件事」：
# 一分半以下讲不清，五分钟以上就不是这个栏目了。
MIN_SECONDS, MAX_SECONDS = 90.0, 300.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def spec_paths(slug: str, root: Path = ROOT) -> tuple[Path, Path]:
    base = root / SPEC_DIR
    return base / f"{slug}.json", base / f"{slug}.xhs.txt"


def load_spec(slug: str, root: Path = ROOT) -> dict:
    spec_path, _ = spec_paths(slug, root)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    problems = spec_problems(spec, slug)
    if problems:
        raise SystemExit(f"{spec_path}：" + "；".join(problems))
    return spec


def spec_problems(spec: dict, slug: str) -> list[str]:
    """一条 vibetennis spec 至少要说清这几件事；缺一件就别往下走。"""
    bad = []
    if spec.get("slug") != slug:
        bad.append(f"slug 写的是 {spec.get('slug')!r}，文件名是 {slug!r}")
    if spec.get("column") != COLUMN or (spec.get("cover") or {}).get("eyebrow") != COLUMN:
        bad.append(f"column 和 cover.eyebrow 都必须是 {COLUMN!r}")
    film = spec.get("film") or {}
    if list(film.get("canvas") or []) != list(CANVAS):
        bad.append(f"film.canvas 必须是 {list(CANVAS)}（这一栏是 16:9 横屏）")
    cover = spec.get("cover") or {}
    if cover.get("layout") == "custom":
        # 所有者逐版审定的定制封面（2026-10-30 第一集起）：poster.jpg 由仓库里的脚本生成
        script = str(cover.get("script") or "")
        if not script.startswith("tools/vibetennis/episodes/") or not script.endswith(".py"):
            bad.append("cover.layout=custom 时 cover.script 要指向 tools/vibetennis/episodes/ 下的生成脚本")
    elif cover.get("layout") != "solo" or not (cover.get("portrait") or {}).get("image"):
        bad.append("封面走仓库的 solo 海报模板（cover.portrait.image 指向原生高清渲染帧），"
                   "或 layout=custom ＋ cover.script")
    if film.get("cover_in_film") is not False:
        bad.append("film.cover_in_film 必须是 false——封面单独一张图，不合进视频（所有者 2026-10-30）")
    if not str(cover.get("hook", "")).strip():
        bad.append("cover.hook 是空的")
    ed = spec.get("editorial") or {}
    if not (ed.get("question") and ed.get("thesis") and len(ed.get("beats") or []) >= 3):
        bad.append("editorial 要有 question、thesis 和至少三个 beats")
    if not ed.get("sources"):
        bad.append("editorial.sources 是空的——科普片的每个数都要有出处")
    push = spec.get("push") or {}
    if not str(push.get("summary", "")).strip():
        bad.append("push.summary 是空的（标题末尾那一格）")
    return bad


def outdir_for(date: str, slug: str, root: Path = ROOT) -> Path:
    return root / "output" / date / OUT_KIND / slug
