#!/usr/bin/env python3
"""按 `data/social_shot_requests/*.json` 把还没截的图截下来。

**请求文件本身就是这张图的来路**：谁、什么时候、按什么选择器截的，跟着仓库走，
不用回头翻某一次 run 的表单。这也是 `social-shot.yml` 的 push 那条入口——
`workflow_dispatch` 只有当工作流已经在默认分支上时才 dispatch 得动，而截图
往往是在特性分支上做片子的过程中才需要的。

请求文件长这样：

    {
      "slug": "wawrinka-farewell",
      "_why": "为什么这条片子需要这几张截图（写给下一个人看的）",
      "shots": [
        {
          "name": "x-farewell",
          "url": "https://x.com/stanwawrinka/status/2092254457358643314",
          "selector": "article",
          "width": 1000, "height": 1600, "wait_ms": 9000,
          "revision": 1,
          "_why": "他 8 月 25 日那篇告别长文的原帖"
        }
      ]
    }

⚠️ **已经截过的不重截**：判据是 `assets/social/<slug>/<name>.png` 在不在，
外加旁证里的 `revision` 对不对得上。要重截就把 `revision` 加一（**不是**删图——
删图会让「还没截」和「截过但要重来」长得一样，而前者是常态）。

⚠️ **一张失败不许把整趟带崩**：这一趟可能有好几张，一张撞上登录墙不该让
已经截好的那几张也提交不了。逐张 try，最后按「有没有一张失败」定退出码——
但**成功那几张照样落库**（提交在工作流那一步，这里只管产出）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ⚠️ **这一行必须排在 import 前面**：这个文件被当脚本跑（`python tools/xxx.py`），
# 而 `capture_social_shot` 是它隔壁的兄弟模块——把 sys.path 的调整放进
# `__main__` 就晚了，模块级的 import 已经先炸了。
sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture_social_shot as cap  # noqa: E402

REQUESTS = Path("data/social_shot_requests")
OUT_ROOT = Path("assets/social")


def _already_done(out: Path, revision: int) -> bool:
    """这张截过了没有。**只有图和旁证都在、且 revision 对得上**才算截过。

    旁证缺失时当成没截过——那多半是上一趟中途失败留下的半截产物，
    而「有图但说不清是哪儿来的」比没有图更糟。
    """
    proof = out.with_suffix(out.suffix + ".json")
    if not out.is_file() or not proof.is_file():
        return False
    try:
        got = json.loads(proof.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return int(got.get("revision") or 1) == revision


def main() -> int:
    if not REQUESTS.is_dir():
        print(f"[截图] 没有 {REQUESTS}/，这一趟没有要截的。")
        return 0
    files = sorted(REQUESTS.glob("*.json"))
    if not files:
        print(f"[截图] {REQUESTS}/ 是空的，这一趟没有要截的。")
        return 0

    failed: list[str] = []
    done = skipped = 0
    for path in files:
        req = json.loads(path.read_text(encoding="utf-8"))
        slug = str(req.get("slug") or path.stem).strip()
        shots = req.get("shots") or []
        if not isinstance(shots, list) or not shots:
            print(f"[截图] {path.name}：没有 shots，跳过")
            continue
        for shot in shots:
            name = str(shot.get("name") or "").strip()
            url = str(shot.get("url") or "").strip()
            if not name or not url:
                failed.append(f"{path.name}: 有一条缺 name 或 url")
                continue
            revision = int(shot.get("revision") or 1)
            out = OUT_ROOT / slug / f"{name}.png"
            if _already_done(out, revision):
                skipped += 1
                print(f"[截图] {slug}/{name} 已经是 revision {revision}，不重截")
                continue
            print(f"[截图] {slug}/{name} ← {url}")
            try:
                proof = cap.capture(
                    url, out,
                    selector=str(shot.get("selector") or ""),
                    # ⚠️ 没写就传 `None`，让 capture 按手机/桌面各自的预设填——
                    # 在这儿写死一组数会把手机预设整个盖掉，而它不报错。
                    width=int(shot["width"]) if shot.get("width") else None,
                    height=int(shot["height"]) if shot.get("height") else None,
                    scale=int(shot["scale"]) if shot.get("scale") else None,
                    wait_ms=int(shot.get("wait_ms") or 6000),
                    hide=tuple(shot.get("hide") or ()),
                    # 社媒帖子默认走手机视口——一条帖子在手机上本来就是竖的，
                    # 截出来直接贴合 3:4 的画布，不用再裁一刀。
                    mobile=bool(shot.get("mobile", True)),
                )
            except SystemExit as exc:  # 登录墙那一支，已经在工具里说过原因
                failed.append(f"{slug}/{name}: 工具报 exit {exc.code}")
                continue
            except Exception as exc:  # noqa: BLE001 — 一张失败不许带崩其余的
                failed.append(f"{slug}/{name}: {type(exc).__name__} {exc}")
                continue
            # revision 和请求里的 `_why` 一起写进旁证：一张图的来路要自足，
            # 不能要求读的人再去翻请求文件。
            proof["revision"] = revision
            proof["why"] = str(shot.get("_why") or "")
            proof["request_file"] = str(path)
            out.with_suffix(out.suffix + ".json").write_text(
                json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            done += 1
            mark = "⚠️ 整屏兜底" if proof["fallback_full_viewport"] else "按选择器裁"
            print(f"  ✅ {out}（{proof['bytes'] // 1024} KB，{mark}）")

    print(f"\n[截图] 这一趟：新截 {done} 张，跳过 {skipped} 张已有的，"
          f"失败 {len(failed)} 张")
    for line in failed:
        print(f"  ❌ {line}")
    # **有失败就非零退出，但成功那几张已经落在盘上**——提交那一步照样会把
    # 它们收进去。「一张都没截成」和「截了三张坏了一张」不该长得一样。
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
