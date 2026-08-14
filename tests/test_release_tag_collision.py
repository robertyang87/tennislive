"""同一个 Release tag 被两个产物目录共用时，旧的那份必须挂账。

**来路（2026-08-14）：** `match-reel.yml` 的 Release 那一步是

    TAG="reel-$SLUG"
    gh release upload "$TAG" "$REEL" --clobber

`--clobber` 是「先删旧的再传」。于是**同一条片子重渲一次，tag 上那份就被换掉了**
——而已经发出去的微信消息里那个 ▶ 按钮钉的正是这个 tag。

⚠️ **这条判据不拦「重渲」，也不改 tag 方案。** 「重渲替换掉旧片」本身说得通
（改了字幕、修了口径，让老消息指向修好的那一版往往正是想要的），而改成
`reel-<slug>-<日期>` 是另一个口径——两条路都成立，那是口径选择。

**它拦的是沉默。** 重渲之后，旧产物目录里那份 `render.json` 还留着它自己那一版的
`video_bytes` / `film_seconds`，而 `video_url` 指向的已经是另一条片子了。两个数
**内部自洽、对外全错**，而且不报错：

    output/2026-07-28/reel/nishikori-shang   video_bytes 35863138
    output/2026-07-29/reel/nishikori-shang   video_bytes 30185483
    → 同一个 tag `reel-nishikori-shang`，上面现在挂的是 7/29 那一份

这不是假想的代价。2026-08-14 回填片长时正是被它咬到：按 URL 去量，两条
`nishikori-shang` 会拿到**一模一样**的秒数，而那个数正要当观看比例的分母——
也就是说一条片子的分母会悄悄用上另一条片子的长度。当时是靠「两份量出来一样」
才露的馅，**换个数据碰巧不一样就发现不了**。

**出路是挂账，不是加豁免名单：** 旧的那份写一句 `_release_tag_note`，说明它
记的那一版已经不在 tag 上了。这是 per-产物 的一句话，不是一张要人天天喂的表
（本仓库为「只许减不许加是注释不是判据」栽过六次）。
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 旧的那份要写的键。值是一句话（为什么这份记录不作数、真的那一版在哪儿）。
NOTE_KEY = "_release_tag_note"


def _tracked_render_json() -> list[Path]:
    """被 git 跟踪的成片记录。

    ⚠️ 用 `git ls-files` 不用 `Path.glob`：CI 的稀疏检出把 `output/` 挡在
    外面，索引里的条目只是被标了 skip-worktree——`glob` 在 CI 上恒空，
    **而空列表和「一条产物都没有」长得一模一样**。
    ⚠️ **git 跑不起来要当场出声**，不许静静退成空列表当作通过。
    """
    out = subprocess.run(
        ["git", "ls-files", "output/*/reel/*/render.json",
         "output/interviews/*/render.json"],
        capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, f"git ls-files 跑不起来（{out.returncode}）：{out.stderr}"
    return [ROOT / line for line in out.stdout.split() if line]


def test_同一个Release_tag被两份产物共用时每一份都要挂账():
    """几份记录共用一条 Release 链接、而 `video_bytes` 对不上时，
    **每一份**都要写 `_release_tag_note`。

    ⚠️ **判据只声明它证得了的那件事**：这几份里至多有一份和 tag 上那个附件
    对得上，**而在仓库里分不出是哪一份**。日期目录只说明「渲的那天」，说不了
    「传的顺序」（同一天渲两趟、或者隔几天补传一次，日期都会骗人）；字节数更
    分不出——写这条判据时我第一版就是按「字节数最大的那份是当前的」挑的，
    真去 Range GET 一量，`nishikori-shang` **正好挑反**（tag 上是 30185483
    那一份，而它字节数更小）。**规矩写对了、实现替它猜了一句证不了的话**，
    正是本仓库反复记的那个形状。

    所以现在不挑：**组里每一份都必须承认自己可能不是当前那一份**，而那句话里
    要写清楚量出来的结果是什么。多写一句的代价，换掉的是一次会挑反的猜测。

    ⚠️ 它**自己会收敛**，不是一张要人喂的名单：新 slug 不会撞，撞了就写一句话，
    写完这条就绿。报错里原样写着要加的键和该说什么。
    """
    records = _tracked_render_json()
    # 判据自己的判据：主语没了（目录改名、glob 写错、`output/` 真被清空）的
    # 样子就是这个列表为空，而那时下面整个循环会安安静静地全绿。
    assert len(records) >= 20, (
        f"只数到 {len(records)} 份成片记录，判据失效了")

    by_url: dict[str, list[tuple[Path, int | None]]] = defaultdict(list)
    for path in records:
        data = json.loads(path.read_text(encoding="utf-8"))
        url = data.get("video_url")
        if url:
            by_url[url].append((path, data.get("video_bytes")))

    assert by_url, "一份成片记录都没有 video_url——成片走 Release 那条路断了？"

    missing: list[str] = []
    collisions = 0
    for url, rows in sorted(by_url.items()):
        if len(rows) < 2:
            continue
        sizes = {size for _, size in rows}
        if len(sizes) == 1:
            # 同一个 tag、同样的字节数：重复记录而已，指的是同一条片子，不算问题。
            continue
        collisions += 1
        tag = url.split("/download/")[-1].split("/")[0]
        for path, size in rows:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not str(data.get(NOTE_KEY, "")).strip():
                others = sorted(str(other.parent.relative_to(ROOT))
                                for other, _ in rows if other != path)
                missing.append(
                    f"{path.parent.relative_to(ROOT)}（记的 {size} 字节，"
                    f"tag `{tag}` 还被这几份共用：{others}）")

    assert not missing, (
        "这几份成片记录和它们指向的 Release 附件对不上，却没有挂账：\n  "
        + "\n  ".join(missing)
        + f"\n\n同一个 slug 重渲一次，`gh release upload --clobber` 就把 tag 上那份"
          f"换掉了，而旧目录里的 video_bytes / film_seconds 还留着自己那一版——"
          f"**内部自洽、对外全错，而且不报错**。\n"
          f"补法：组里**每一份**都加一个 `{NOTE_KEY}`，一句话写清 tag 上现在是哪"
          f"一份。⚠️ **别在仓库里猜**（按日期、按字节数都会挑反，实测过），量一次：\n"
          f"    Range: bytes=0-1 → Content-Range 的总长，和各份的 video_bytes 比\n"
          f"不要去删这些数（删了下一个人还会重新量一遍再踩一次），"
          f"也不要往任何名单里加行。")

    print(f"  {len(by_url)} 条 Release 链接，其中 {collisions} 条被重渲换过，"
          f"涉及的每一份都挂了账")


def test_挂账那句话不许写成一句空话():
    """挂了账要真的说清楚，别写「已知问题」四个字就算完。

    ⚠️ 本仓库的老规矩：**把一个已知的洞抹平，比留着它糟得多**。所以这一条要求
    那句话里必须出现另一个产物目录的日期——也就是「真的那一版在哪儿」这个
    唯一有用的信息。写不出来，说明写的人自己也没查。
    """
    import re

    checked = 0
    for path in _tracked_render_json():
        data = json.loads(path.read_text(encoding="utf-8"))
        note = str(data.get(NOTE_KEY, "")).strip()
        if not note:
            continue
        checked += 1
        assert len(note) >= 20, (
            f"{path.parent.name} 的 {NOTE_KEY} 只有 {len(note)} 个字：{note!r}——"
            "挂账要说清「记的那一版已经不在 tag 上了、真的那一版在哪儿」")
        assert re.search(r"\d{4}-\d\d-\d\d", note), (
            f"{path.parent.name} 的 {NOTE_KEY} 里没有日期：{note!r}——"
            "「真的那一版在哪个目录」是这句话唯一有用的信息，写不出来说明没查")

    # ⚠️ 这里**故意不设下限**：哪天所有碰撞都被清掉（比如换了 tag 方案），
    # 一条挂账都没有是正常的，而上面那条判据仍然守着「新碰撞要出声」。
    print(f"  {checked} 份挂了账的记录，措辞都过关")
