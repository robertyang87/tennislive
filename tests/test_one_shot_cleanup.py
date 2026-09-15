"""一次性补救的工作流和脚本，活干完就该走——它们不是「占地方」，是**活雷**。

来路（2026-09-15，账号所有者：「把一些不必要的代码和无关的 ci 内容移除，
保持整体流水线高效优质产出视频和素材」）。

量出来的形状很整齐：50 条工作流里有 10 条是**单目标一次性任务**，每条只盯一个
文件（自己的 yml，或一份 `requests/stories/*.json`），全部服务于几条**已经发完**
的片子——光 `zheng-usopen-icons` 一条就挂了 5 条工作流。

⚠️ **它们不是「触发不了的死代码」**：查过，触发文件一个不少地都还在。所以真正的
代价是**误触发**——改一下 `specs/reels/zheng-usopen-icons.json`，就会踢起一趟
65 分钟的重渲，渲一条 9 月 8 号就发完、账本里记着已推送的片子。

删之前三样证据齐了（判据是产物，不是印象）：

1. **活干完了**——`output/**/render.json` 落库，且 `data/*_publish_ledger/` 里
   记着已推送；
2. **没人引用**——`tests/` 里零命中（`push-existing.yml` 有 3 处命中，所以
   **它留着**：判据写明它是赛程包那个栏目唯一的发布出口）；
3. **不扫全量**——没有任何测试钉「工作流数量下限」，删了不会让别的判据失主语。

工具那半边同一个判据，但**按各自的 docstring 判，不按名字猜**：写死在一条已发
片子上的（`2004 US Open` / `yellow-ball` / `hawkeye` 的 B-roll / `Isner-Mahut` /
`ten champions` / 费德勒入名人堂 / 红土球印）才删；**通用工具一个没动**——
Commons 分类枚举、深度遍历、入库、预览、源探测都留着，CLAUDE.md「空结果 ≠
不存在」那节记的教训（分类名要让接口自己报、年份分类藏在深一层）正是它们的实现。

⚠️ **这条判据防的是「那一个」，不是「那一类」**，而且是有意的：「一次性任务」
机械上分辨不出来——`push-existing.yml` 的触发路径同样钉着一个带日期的文件
（`data/manual_push_requests/2026-09-08-zheng-copy.json`），而它是活的。想做成
通用规则就得配一张豁免表，而 CLAUDE.md 反复记着「一条天天误报的闸会被人写豁免
压掉，把它唯一想拦的那一类一起关掉」。所以这儿只钉「这 21 个别长回来」。

**要恢复其中任何一个，从 git 历史里取回来，并且改掉这条测试**——和 `daily.yml`
那次一样，让它是一次看得见的决定。
"""

from pathlib import Path

# 只许减不许加。加回来之前先读上面那段。
_REMOVED_WORKFLOWS = (
    "zheng-rebuild-editorial",
    "zheng-rybakina-rebuild-source",
    "zheng-wildcards-delivery",
    "icons-cover-refresh",
    "icons-square-revision",
    "icons-story-publish",
    "icons-story-render",
    "icons-story-source-review",
    "recover-shelton-alcaraz",
    "nishikori-caption-gap-fix",
)

_REMOVED_TOOLS = (
    "hunt_2004_usopen.py",
    "hunt_channels_round2.py",
    "hunt_ballmark_wide.py",
    "hunt_rg2026_ballmark.py",
    "hunt_longest_match.py",
    "hunt_ten_champions.py",
    "hunt_yellow_ball.py",
    "grab_yellow_shortlist.py",
    "multi_source_hunt.py",
    "probe_explainer_broll.py",
    "repair_federer_assets_local.py",
)

# 留下来的那几个，判据要**同时**钉住——只钉「删掉的没回来」的话，
# 一次手抖把活的一起删了，这条测试照样绿。
_MUST_STAY_WORKFLOWS = (
    "push-existing",   # 赛程包唯一的发布出口，test_match_reel 钉着
    "match-reel",
    "interview-clip",
    "explainer",
    "orchestrate",
    "ci",
)
_MUST_STAY_TOOLS = (
    "deep_commons.py",          # Commons 分类要深一层——CLAUDE.md 记过的教训
    "discover_categories.py",   # 让接口自己报分类叫什么，别猜
    "verify_commons_files.py",
    "commons_sheet.py",
    "add_venue.py",
    "probe_wta_highlight.py",
)


def test_一次性补救的工作流不许长回来():
    for name in _REMOVED_WORKFLOWS:
        path = Path(f".github/workflows/{name}.yml")
        assert not path.exists(), (
            f"{path} 又回来了。它是一条**单目标一次性任务**，服务的片子已经发完、"
            "账本里记着已推送——留着的代价是误触发（改一下那条 spec 就踢起一趟"
            "重渲）。真要恢复，连这条判据一起改，让它是一次看得见的决定。"
        )


def test_写死在已发片子上的一次性脚本不许长回来():
    for name in _REMOVED_TOOLS:
        path = Path(f"tools/{name}")
        assert not path.exists(), (
            f"{path} 又回来了。它是为某一条**已经发完**的片子写死的一次性抓图/"
            "修复脚本，不收参数、换一条片子用不了。通用工具不在这张表里。"
        )


def test_这条判据自己不是恒真的():
    """删干净了 ≠ 判据有效——活的那些必须还在，否则一次误删照样全绿。

    反向验证过：把 `push-existing.yml` 拿掉，这条当场红。
    """
    for name in _MUST_STAY_WORKFLOWS:
        assert Path(f".github/workflows/{name}.yml").is_file(), (
            f"{name}.yml 不见了——这是活的生产线，不在被清理的名单里")
    for name in _MUST_STAY_TOOLS:
        assert Path(f"tools/{name}").is_file(), (
            f"tools/{name} 不见了——它是通用工具，不是一次性脚本")

    assert len(_REMOVED_WORKFLOWS) == 10 and len(_REMOVED_TOOLS) == 11, (
        "名单长度对不上——这两张表只许减不许加，改了就说明有人在往回加")
