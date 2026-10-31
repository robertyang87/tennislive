#!/usr/bin/env python3
"""把一条 vibetennis 成片推到微信（PushPlus）：标题＋正文＋海报＋成片＋复制页。

**正文和标题完全复用赛场之上那套**（`tools/push_reel.py`）：
`prepare_copy` 出标题（`EP01.vibetennis|现场更快` 这种「EP 两位集数＋.＋栏目＋|＋主题」，不写日期，
集数登记在 `data/vibetennis_episodes.json`；≤20 字、
无空白）和去掉标题的正文（≤5 个 tag，活动期自动补活动 tag），`build_html` 排版，
`wait_for_delivery` 先等复制页和成片链接真的能打开，再 `push`。

和 push_reel 唯一的差别：这一栏**没有旁白**，所以不过 `voice_quality_gate`（它要的是
配音清单和听审记录，这条片子一句配音都没有）；发布前改由 `publish_gate.validate_qc`
复核 vibetennis 自己的 L2 凭证。

    python3 tools/vibetennis/push.py --outdir output/2026-10-30/vibetennis/<slug> \
        --receipt-out "$RUNNER_TEMP/pushplus-receipt.json"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "src"))

import push_reel as pr  # noqa: E402
from tennislive.render import push_style as ps  # noqa: E402
from common import SPEC_DIR  # noqa: E402
from publish_gate import validate_qc  # noqa: E402


# 这一栏是 16:9 横屏成片；共用推送模板的按钮写的是「竖版」。只在这一栏替换按钮文字，
# 不改 push_style / push_reel（别的栏目不变，reel 修订单钉住的主题源码哈希也不动）。
LANDSCAPE_BUTTON_TEXT = "▶ 打开横版成片"


def landscape_button(html: str) -> str:
    if html.count(ps.VIDEO_BUTTON_TEXT) != 1:
        raise SystemExit(f"推送 HTML 里「{ps.VIDEO_BUTTON_TEXT}」不是恰好一处，模板变了，先看一眼")
    return html.replace(ps.VIDEO_BUTTON_TEXT, LANDSCAPE_BUTTON_TEXT)


def compose(outdir: Path) -> tuple[str, str, str, str]:
    """返回 (标题, 正文纯文本, 推送 HTML, 成片链接)——dry-run 和真推共用。"""
    slug = outdir.name
    copy = SPEC_DIR / f"{slug}.xhs.txt"
    column, title, body = pr.prepare_copy(copy, outdir)
    meta = pr.push_meta(copy)
    text = f"{title}\n\n{body}"
    url = pr.released_video_url(outdir)
    if not url:
        raise SystemExit(f"{outdir}/render.json 没有 video_url——先跑 tools/vibetennis/release.py")
    poster = pr.poster_url(outdir) if (outdir / pr.POSTER_NAME).is_file() else ""
    if not poster:
        raise SystemExit("海报不在，不推")
    html = pr.build_html(url, pr.copy_page_url(outdir), meta.get("lead", ""), text, poster,
                         column=column)
    return title, body, landscape_button(html), url


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--receipt-out", default="")
    ap.add_argument("--dry-run", action="store_true", help="只打印标题、正文和 HTML，不发")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    title, body, html, url = compose(outdir)
    print(f"[标题] {title}\n[正文]\n{body}\n[成片] {url}")
    if args.dry_run:
        out = outdir / "push_preview.html"
        out.write_text(html, encoding="utf-8")
        print(f"[dry-run] 推送 HTML → {out}（不发）")
        return 0
    if not (outdir / "copy.html").is_file():
        raise SystemExit("copy.html 不在——先跑 release.py（它会写复制页）")
    validate_qc(Path.cwd(), outdir.name, outdir)
    pr.wait_for_delivery(pr.copy_page_url(outdir), title, url)
    validate_qc(Path.cwd(), outdir.name, outdir)   # 网络等待之后再复核一次字节身份
    receipt = pr.push(title, html, asset_dir=outdir)
    if args.receipt_out:
        print(f"[PushPlus] 流水号凭据已写入：{pr.write_receipt(args.receipt_out, receipt)}")
    print(f"已推送：{title}\n  成片 {url}\n  复制页 {pr.copy_page_url(outdir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
