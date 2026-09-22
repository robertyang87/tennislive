#!/usr/bin/env python3
"""抓一位球员的**官方头像**，存进 `assets/players/headshots/`。

给「数据统计对照图」的头像用——那张图要的是圆形小头像，跟 VS 海报用的
半身抠图（`assets/players/wta-<id>-<slug>.png`）是两回事，不要混着找。

    PYTHONPATH=src python3 tools/fetch_official_headshot.py wta "Naomi Osaka"
    PYTHONPATH=src python3 tools/fetch_official_headshot.py atp "Ben Shelton" --id S0AG \\
        --via https://www.mubadaladcopen.com

两条巡回赛的取法完全不同，别用同一套逻辑：

**WTA**——有干净的按姓名搜索接口，ID 自动查：
    1. `api.wtatennis.com/tennis/players/?pageSize=5&name=<姓>` → 拿 id
    2. `wtafiles.blob.core.windows.net/images/headshots/<id>.jpg`
       ——这个域名是从球员主页 HTML 里 `headshots/<id>.jpg` 这个模式反查出来的
       （`www.wtatennis.com/players/<id>/<slug>` 页面源码里能找到），
       接口本身不接受 name 参数，必须先查到 id。
       ⚠️ **后缀两种都有，没有规律，所以两种都要试**（`WTA_HEADSHOT_EXTS`）：
       布兹科娃 320983 是 `.jpg`，卡尔塔尔 329918 只有 `.png`。2026-09-22 之前
       这里只拼 `.jpg`，后者报的 404 被读成了「这个人没有官方头像」。

**ATP**——没有按姓名搜索的接口，ID 要事先知道（球员主页 URL 里带着）：
    `atptour.com/en/players/<slug>/<ID>/overview`
    ⚠️ **`atptour.com` 总站对这台环境 403**，但任意一个赛事自己的域名会镜像
    同一批资源（`--via` 传一个能连通的赛事域名，比如
    `https://www.mubadaladcopen.com`），走
    `<域名>/-/media/alias/player-headshot/<ID>` 取图。
    ⚠️ **ID 猜错会返回一张占位剪影**，HTTP 200、Content-Type 也是
    image/png，肉眼分不出来——用颜色数判：占位剪影只有 2 种颜色，
    真头像有几百种。这个判据本脚本自动做，不对就报错。

存下来的文件名：`assets/players/headshots/<tour>-<id>.jpg`（或 `.png`），
按 tour+id 命名是因为**同一个人在两条巡回赛的头像位置不通用**，而 id
本身就是防重复下载的键——同一个人再抓一次会直接命中缓存。
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "players" / "headshots"

UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0.0.0 Safari/537.36")}


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _distinct_colors(data: bytes) -> int:
    """占位剪影只有 2 种颜色（灰底+一个剪影色），真头像有几百种——
    比状态码/Content-Type 可靠得多，那两样占位图和真图完全一样。"""
    from io import BytesIO

    from PIL import Image
    im = Image.open(BytesIO(data)).convert("RGB")
    colors = im.getcolors(maxcolors=100_000)
    return len(colors) if colors else 100_000


def wta_player_id(name: str) -> int:
    surname = name.strip().split()[-1]
    url = f"https://api.wtatennis.com/tennis/players/?pageSize=10&name={surname}"
    data = json.loads(_get(url))
    want = name.strip().lower()
    for row in data.get("content") or []:
        if str(row.get("fullName", "")).strip().lower() == want:
            return int(row["id"])
    raise SystemExit(
        f"WTA 球员库里按姓 {surname!r} 搜不到全名精确匹配 {name!r}；"
        f"搜到的候选：{[r.get('fullName') for r in data.get('content') or []]}")


# ⚠️ **这个 blob 上两种后缀都有货，而且没有规律**：布兹科娃（320983）是 `.jpg`，
# 卡尔塔尔（329918）只有 `.png`。原来这里只拼 `.jpg`，于是后者一律报
# `404 The specified blob does not exist`——**而那句话和「这个人没有官方头像」
# 长得一模一样**（CLAUDE.md「空结果 ≠ 不存在」）。
#
# ⚠️⚠️ 它已经造出过一条**假的「查空」**：`bartunkova-charaeva` 的 `_no_stats_why`
# 写着「`fetch_official_headshot.py wta` 对 330364 和 329198 都返回 404」——
# 2026-09-22 逐个后缀量过，**330364（巴尔通科娃）有 `.png`**，只有 329198
# （恰拉耶娃）是两个后缀都真没有。也就是说那条注解的**结论**（缺一张就画不成
# 这张图）仍然成立，**理由却有一半是编的**——CLAUDE.md「编出来的判据 ＋ 正确的
# 结论」记的正是这种自带免检的形状。那条片子已发，不重渲，只把账记在这儿。
#
# 现在两个后缀都试，报错时把两条都打出来，让「真的没有」自己证明自己。
WTA_HEADSHOT_EXTS = ("jpg", "png")


def fetch_wta(name: str, out_dir: Path = OUT_DIR) -> Path:
    pid = wta_player_id(name)
    for ext in WTA_HEADSHOT_EXTS:
        dest = out_dir / f"wta-{pid}.{ext}"
        if dest.is_file():
            print(f"[头像] 命中缓存 {dest}")
            return dest
    tried: list[str] = []
    for ext in WTA_HEADSHOT_EXTS:
        url = f"https://wtafiles.blob.core.windows.net/images/headshots/{pid}.{ext}"
        try:
            data = _get(url)
        except urllib.error.HTTPError as exc:  # 404 只说明这个后缀没有
            tried.append(f"{url} → HTTP {exc.code}")
            continue
        n = _distinct_colors(data)
        if n < 20:
            raise SystemExit(
                f"{name}（WTA id={pid}）取到的图只有 {n} 种颜色，像是占位剪影，"
                f"不是真头像：{url}")
        dest = out_dir / f"wta-{pid}.{ext}"
        out_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"[头像] {name} → {dest}（WTA id={pid}，{n} 种颜色，{len(data)} 字节）")
        return dest
    raise SystemExit(
        f"{name}（WTA id={pid}）在 WTA 头像 blob 上两个后缀都没有——"
        + "；".join(tried))


def fetch_atp(name: str, player_id: str, via: str, out_dir: Path = OUT_DIR) -> Path:
    dest = out_dir / f"atp-{player_id}.png"
    if dest.is_file():
        print(f"[头像] 命中缓存 {dest}")
        return dest
    url = f"{via.rstrip('/')}/-/media/alias/player-headshot/{player_id}"
    data = _get(url)
    n = _distinct_colors(data)
    if n < 20:
        raise SystemExit(
            f"{name}（ATP id={player_id!r}）取到的图只有 {n} 种颜色，像是占位剪影"
            f"（ID 大概率查错了），不是真头像：{url}")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"[头像] {name} → {dest}（ATP id={player_id}，{n} 种颜色，{len(data)} 字节）")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tour", choices=["wta", "atp"])
    ap.add_argument("name")
    ap.add_argument("--id", help="ATP 必填：球员主页 URL 里的那串 ID（如 S0AG）")
    ap.add_argument("--via", help="ATP 必填：一个能连通的赛事域名，用来镜像 atptour.com 的资源")
    args = ap.parse_args()

    if args.tour == "wta":
        fetch_wta(args.name)
    else:
        if not args.id or not args.via:
            raise SystemExit("ATP 头像要显式给 --id 和 --via（atptour.com 总站对这台环境 403）")
        fetch_atp(args.name, args.id, args.via)


if __name__ == "__main__":
    main()
