"""整改内容合同绑的是**素材构成**，不是台头上印的那四个字。

来路（2026-08-14 拿全部 67 条 reel spec 扫出来的）：`_validate_editorial_contract`
的 `required` 一直是 `topbar is not None`，而 `topbar` 只在
`cover.eyebrow == "赛场之上"` 时才强制。于是**把台头改成「网球有故事」，整份
合同（question / thesis / beats / human_context）就整条豁免掉了**——而豁免掉的
恰恰是素材构成最像二次创作的那几条：

    slug                    第三方源片   自有比赛画面   有合同吗
    lina-cincinnati-2012        7            0          ❌
    eala-story                  5            0          ❌
    eala-washington-story       5            0          ❌
    cincinnati-story            3            0          ❌
    08-08 之后的「赛场之上」      1            0          ✅ 33/59

这个号 2026-08-06 被视频号判过「二次创作信息增量不足」，这份合同就是为那次整改
建的。**那个风险跟着素材构成走，不跟着 `cover.eyebrow` 走**——平台看的是「用了
谁的画面、加了多少自己的东西」，它不读栏目名。

⚠️ 34 条存量会被这条新判据拦下（远超十条），所以它**不做成一堵墙**：挂豁免表，
按仓库惯例（见 `tests/test_reel_editorial.py` 顶上那段）分「已推送」/「还没推送」
两半，只许减不许加，每半各自自检。CLAUDE.md 里跨切点那次的教训就是硬闸拿 20 条
一扫 10 条会红，只好降级——**做成墙的下场是下一个人给所有 spec 填一份空壳合同
把它按掉，而那正好毁掉它唯一想拦的东西**。

这份文件只吃 `specs/` 和 `tools/`：CI 的稀疏检出不含 `output/`，拿产物当判据的
主语会在 CI 上变成一盏恒真的绿灯（本仓库栽过一次）。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SPEC_DIR = Path("specs/reels")

#: 这道闸落地的前一天。豁免表是**这一刻封口的一份存量名单**，所以「这条片子在
#: 那之前就渲过了」是可以从产物路径直接读出来的——`output/<日期>/reel/<slug>/`
#: 里那个日期就是判据，不用另记一张名单。
#:
#: ⚠️ 它**永远不用往后调**：名单只许减不许加，往后调等于给新片子开一个后门。
_LEGACY_CUTOFF = "2026-08-13"


def _reel():
    """和 `tests/test_match_reel.py` 同一条导入路径。"""
    sys.path.insert(0, "tools")
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


def _specs():
    for path in sorted(SPEC_DIR.glob("*.json")):
        yield path.stem, json.loads(path.read_text("utf-8"))


def _tracked_reel_products(name: str) -> dict[str, set[str]]:
    """`output/<日期>/reel/<slug>/<name>` 在**仓库**里的那些，按 slug 归日期。

    ⚠️ **`git ls-files` 而不是 `Path.glob`**，两个理由，第二个才是要命的：

      · cone 模式下稀疏检出把 `output/` 整个挡在工作区外面，而索引里的条目只是
        被标了 skip-worktree——`git ls-files` 在哪种模式下都数得到同一批。
      · CI 的稀疏检出**就是不含 `output/`**，`glob` 在那儿恒为空集，
        而**空集和「一条都没有」长得一模一样**：拿它当判据的主语，这条检查
        会在 CI 上变成一盏恒真的绿灯（本仓库栽过一次）。

    ⚠️ **`git ls-files` 在浅克隆上照样准**（CI 的 `actions/checkout` 默认
    `fetch-depth: 1`），因为它读的是索引不是历史。同一件事换成 `git log --grep`
    就完全不成立——那才是这份文件里没有任何一条判据去查提交历史的原因。
    """
    done = subprocess.run(
        ["git", "ls-files", f"output/*/reel/*/{name}"],
        capture_output=True, text=True, check=False)
    # 「读不到」和「没有」处置相反：读不到要出声，不许静静退成空集。
    assert done.returncode == 0, (
        f"git ls-files 跑不起来（{done.returncode}）：{done.stderr.strip()}。\n"
        "这几条判据的主语是仓库索引——读不到不等于「一条产物都没有」，"
        "所以这里不许退成空集当作通过。")
    found: dict[str, set[str]] = {}
    for line in done.stdout.split():
        m = re.fullmatch(rf"output/(\d{{4}}-\d\d-\d\d)/reel/([^/]+)/{re.escape(name)}",
                         line)
        if m:
            found.setdefault(m.group(2), set()).add(m.group(1))
    return found


def _spec_sources(spec):
    """spec 声明的源片。**不调 `spec_sources`**——它对残缺的 spec 会抛错，
    而这份文件只想数数，不想在扫描里替生产代码做校验。"""
    if isinstance(spec.get("sources"), dict):
        return dict(spec["sources"])
    if "source_url" in spec:
        return {"": spec["source_url"]}
    return {}


# ──────────────────────────────────────────────────────────────────────────
# 一、判据本身：用了别人的素材就要有合同，与栏目无关
# ──────────────────────────────────────────────────────────────────────────


def test_用了第三方源片就要有整改合同不看栏目():
    """这条闸**不许再按 `cover.eyebrow` 判**。

    判据钉两头：
      · 每一条用了第三方源片、又不在豁免表里的 spec，都必须真的填了合同；
      · 而且**换个栏目名绕不过去**——同一份 spec 只把台头改成「网球有故事」，
        它照样得红。只钉前一头的话，下一个人把 `required` 又绑回栏目名，
        这条测试仍然是绿的。
    """
    reel = _reel()
    checked = 0
    missing = []
    for slug, spec in _specs():
        urls = _spec_sources(spec)
        if not urls:
            continue
        checked += 1
        required = reel._editorial_contract_required(
            spec, urls, reel._topbar_lines(spec))
        if required and spec.get("editorial") is None:
            missing.append(slug)
    assert not missing, (
        "这几条用了别人的源片却没有 editorial 合同："
        f"{missing}\n"
        "\n"
        "⚠️ **这不是一张要人天天喂的名单。** 这条闸挂在 `validate_spec` 上，也就是\n"
        "`--dry-run` 那一刻就会拦住——合并之后新写的 spec **必然自带这个键**，\n"
        "这条断言从此自己收敛。会走到这儿只有一种情况：这条 PR 还挂着的这几天里，\n"
        "又落地了一条「网球有故事」/「开球之前」（那两个栏目原来整条豁免）。\n"
        "\n"
        "补一次要跑的就这两条（`editorial` 一个像素都不进画面，**不用重渲**）：\n"
        "  1. 往 specs/reels/<slug>.json 里加 editorial：\n"
        "     mode / question / thesis / beats(≥3) / human_context\n"
        "     字段说明见 docs/columns.md「『赛场之上』的整改内容合同」那节\n"
        "  2. PYTHONPATH=src python3 tools/build_match_reel.py render --dry-run \\\n"
        "       --spec specs/reels/<slug>.json --outdir /tmp/dry     # 0.2 秒，不联网\n"
        "\n"
        "· 真已经推过微信了（补合同也拦不住那次已经发生的发布）→ 挂进\n"
        "  `_EDITORIAL_LEGACY_已推送`，并在名字后面写清凭据（pushed.json / 那一笔提交）\n"
        "· **别把 cover.eyebrow 改成别的栏目绕过去**——那正是这条判据要拦的事"
    )
    # 判据自己的判据：主语没了（改了字段名、换了目录）要出声，别变成恒真绿灯。
    assert checked >= 40, f"只扫到 {checked} 条 spec，判据的主语像是没了"


def test_改个栏目名绕不过整改合同():
    """把台头从「赛场之上」改成「网球有故事」，合同照样要填。

    ⚠️ 这条是这次改动的**全部意义**，所以它必须真调 `_editorial_contract_required`
    而不是查源码里有没有某个字符串——「写了不等于跑过」。
    """
    reel = _reel()
    spec = json.loads((SPEC_DIR / "lina-cincinnati-2012.json").read_text("utf-8"))
    spec["slug"] = "a-brand-new-story"          # 躲开豁免表
    # ⚠️ **`pop` 而不是断言它现在没有合同。** 这条 spec 挂在「已推送」那半，
    # 将来有人给它补一份合同完全说得得通（那是好事），而这条测试问的是另一件事
    # ——「同样的素材构成，换个台头还拦不拦得住」。拿别人的当期状态当前提，
    # 就是给自己埋一条会被无关改动打红的判据。
    spec.pop("editorial", None)
    assert spec["cover"]["eyebrow"] == "网球有故事"
    assert len(_spec_sources(spec)) == 7, "这条 spec 的七条第三方源片是判据的前提"

    for eyebrow in ("网球有故事", "赛场之上", "开球之前", "随便编一个栏目"):
        spec["cover"]["eyebrow"] = eyebrow
        assert reel._editorial_contract_required(
            spec, _spec_sources(spec), None), f"台头写成「{eyebrow}」就绕过去了"
        with pytest.raises(reel.ReelError, match="editorial"):
            reel._validate_editorial_contract(spec, required=True)


def test_这道闸真的挂在validate_spec上():
    """⚠️ **这条是反向验证逼出来的，别删。**

    上面两条都直接调 `_editorial_contract_required`，于是把 `validate_spec` 里
    那一行**原样改回 `required=topbar is not None`**（也就是这次改动之前的写法），
    **两条测试照样全绿**——实测过。判据验的是「这个函数算得对」，而坏掉的是
    「没有人调它」，正是 `_cut_person` 那次的形状：签名对了、实现从来没跑起来过。

    所以这条**真跑一遍 `validate_spec`**：一条「网球有故事」、画面全来自
    YouTube、没有合同的 spec，必须在 `--dry-run` 那一刻就红。
    """
    reel = _reel()
    spec = {
        "slug": "wired-through-validate-spec",
        "cover": {"eyebrow": "网球有故事"},          # 没有顶栏，栏目也不是赛场之上
        "sources": {"a": "https://www.youtube.com/watch?v=x"},
        "segments": [{"source": "a", "start": 0, "end": 3}],
    }
    assert reel._topbar_lines(spec) is None, "这条 spec 的前提是「没有顶栏」"
    with pytest.raises(reel.ReelError, match="editorial"):
        reel.validate_spec(spec)

    # 另一头：补上合同就该放行到下一道闸（不能是「怎么写都红」）。
    spec["editorial"] = {
        "mode": "match_review",
        "question": "这场球最值得复盘的问题？",
        "thesis": "一句能被画面和资料支持的中心判断。",
        "beats": ["前段走势", "中段转折", "结局与回应"],
        "human_context": {
            "angle": "这一场独有的场外切口",
            "facts": ["一条能核验的事实"],
            "sources": ["https://www.wtatennis.com/news/x"],
        },
    }
    try:
        reel.validate_spec(spec)
    except reel.ReelError as exc:
        assert "editorial" not in str(exc), (
            f"补齐了合同还在报 editorial，这条闸变成了一堵墙：{exc}")


def test_自有画面才是唯一的出路():
    """`_third_party_sources` 认的是「要从别人的服务器下回来」，不是「有源片」。

    也就是说这条合同**只有一条出路：真的不用别人的素材**。写成恒真的常量就少了
    这条出路，而那条出路正是合同想鼓励的方向。
    """
    reel = _reel()
    mixed = {
        "yt": "https://www.youtube.com/watch?v=x",
        "brightcove": "https://players.brightcove.net/1/2/index.html?videoId=3",
        "ours": "assets/footage/我们自己拍的.mp4",
    }
    assert set(reel._third_party_sources(mixed)) == {"yt", "brightcove"}
    assert reel._third_party_sources({"ours": mixed["ours"]}) == {}

    ours_only = {"slug": "all-our-own-footage", "cover": {"eyebrow": "赛场之上"}}
    assert not reel._editorial_contract_required(
        ours_only, {"ours": mixed["ours"]}, None), (
        "全用自己的画面还要合同——那这条闸就不是在防二次创作，是在收过路费")


def test_顶栏那条既有的强制没有被撤掉():
    """`topbar` 那一项管的是另一件事（顶栏印赛事轮次比分），这次是 `or` 上去的。

    这么写只会**加宽**、绝不会放过原来拦得住的任何一条——所以要有一条钉住它：
    带顶栏但一条第三方源片都没有的 spec，照旧必须填合同。
    """
    reel = _reel()
    spec = {"slug": "topbar-but-our-own-footage", "cover": {"eyebrow": "赛场之上"}}
    assert reel._editorial_contract_required(
        spec, {"ours": "assets/我们自己拍的.mp4"}, ("WTA 1000 第三轮", "甲 6-4 乙")), (
        "有顶栏却不要合同了——原来拦得住的这一条被放过去了")


# ──────────────────────────────────────────────────────────────────────────
# 二、豁免表的自检：只许减不许加
# ──────────────────────────────────────────────────────────────────────────
#
# ⚠️ 表里每个 slug 必须**真的存在**、而且**真的还在犯这个毛病**。写错一个名字，
# 豁免就成了一盏恒真的绿灯——这个仓库为此专门立过规矩（`_LEGACY_NO_TOPBAR`、
# `_LEGACY_VS_COVERS`、`_HOOK_ECHO_LEGACY` 都带同一种自检）。


def _assert_legacy_half_holds(table, half):
    """一条豁免要立得住，得同时满足三件事，**后两件是从产物算的**。

    ⚠️ **「只许减不许加」写在注释里是一句话，不是判据。** 实测过：只查①②的话，
    往表里加一行**测试照样全绿**——而这张表每加一行就少拦一条片子。所以第③条
    钉的是「这条片子**在这道闸落地之前就已经渲过了**」，那是一个新写的 spec
    **不可能**满足的条件，也就把「不补合同、改挂豁免」这条捷径堵在了门口。
    """
    rendered = _tracked_reel_products("render.json")
    for slug in sorted(table):
        # ① 名字得真的是一条 spec——写错一个名字，豁免就成了一盏恒真的绿灯
        path = SPEC_DIR / f"{slug}.json"
        assert path.is_file(), \
            f"{half}：{slug} 这条 spec 已经没了，把它从豁免表里删掉"
        # ② 而且那个毛病得真的还在
        spec = json.loads(path.read_text("utf-8"))
        assert spec.get("editorial") is None, (
            f"{half}：{slug} 已经补上 editorial 合同了，把它从豁免表里删掉"
            f"——这张表只许减不许加"
        )
        # ③ 存量的凭据：这道闸落地之前就渲过了，产物在仓库里
        dates = rendered.get(slug, set())
        assert dates, (
            f"{half}：{slug} 在仓库里找不到 output/*/reel/{slug}/render.json，"
            f"也就是**它根本不是一条存量片子**。\n"
            f"这张豁免表是 {_LEGACY_CUTOFF} 封口的一份存量名单——"
            f"新写的 spec 请补 editorial 合同（不用重渲），别往表里加名字：\n"
            f"  **补进来不是把自检改松，是把这条闸对这条片子整个关掉。**")
        assert min(dates) <= _LEGACY_CUTOFF, (
            f"{half}：{slug} 最早的产物在 {min(sorted(dates))}，"
            f"晚于封口日 {_LEGACY_CUTOFF}——这不是存量，是一条新片子。\n"
            f"  **补进来不是把自检改松，是把这条闸对这条片子整个关掉。**\n"
            f"  正确做法：补 editorial 合同（`editorial` 一个像素都不进画面，"
            f"改完不用重渲）。\n"
            f"  ⚠️ 真是老片子被重渲、旧日期目录被清掉了才走到这儿的话，"
            f"**别去调 `_LEGACY_CUTOFF`**（往后调等于给新片子开后门），"
            f"把这一条的凭据写清楚再说。")


def test_已推送那半豁免表立得住():
    reel = _reel()
    _assert_legacy_half_holds(reel._EDITORIAL_LEGACY_已推送, "已推送")
    # 判据自己的判据：这半空了就说明表被谁清了，而不是「都补上了」。
    assert len(reel._EDITORIAL_LEGACY_已推送) >= 1, "已推送那半空了，判据的主语没了"


def test_还没推送那半豁免表立得住():
    """⏰ 这半是**债**，不是永久豁免：`editorial` 一个像素都不进画面，补一份
    合同连重渲都不用。改一条就从表里删一条。

    ⚠️ 这半**允许空**——空了是好事（债还完了），和上一半不一样，所以不钉下界。

    ⚠️ 而「还没推送」这四个字是可以**从产物核**的：自动推送那条路推完会往
    `output/<日期>/reel/<slug>/pushed.json` 写一个标记（`auto_push_gate` 的
    「已经推过了就别再发」查的就是它）。所以这半里的名字**不许有那个标记**——
    有标记还挂在这半，说明它其实已经发出去了，该挪到上面那半（永久），
    而不是留在这儿当一笔迟早要还的债。
    """
    reel = _reel()
    _assert_legacy_half_holds(reel._EDITORIAL_LEGACY_还没推送, "还没推送")

    pushed = _tracked_reel_products("pushed.json")
    misfiled = sorted(set(reel._EDITORIAL_LEGACY_还没推送) & set(pushed))
    assert not misfiled, (
        f"这几条挂在「还没推送」，可仓库里有它们的 pushed.json：{misfiled}\n"
        "也就是**已经发出去了**——微信那条消息收不回来，补一份合同也拦不住那次"
        "已经发生的发布。把名字挪到 `_EDITORIAL_LEGACY_已推送`（永久那半），"
        "并把 pushed.json 的日期写在名字后面当凭据。")

    both = reel._EDITORIAL_LEGACY_已推送 & reel._EDITORIAL_LEGACY_还没推送
    assert not both, f"这几条同时挂在两半里，推没推过说不清：{sorted(both)}"
    assert reel._EDITORIAL_LEGACY == (
        reel._EDITORIAL_LEGACY_已推送 | reel._EDITORIAL_LEGACY_还没推送), (
        "合表和两半对不上——闸读的是合表，改一半改漏了不会有人告诉你")


# ──────────────────────────────────────────────────────────────────────────
# 三、顶层 `voice` / `rate` 是死键
# ──────────────────────────────────────────────────────────────────────────
#
# 2026-08-14 量出来的：同一个键、同一天、两把嗓子。
#
#     specs/reels/eala-story.json            "voice": "zh-CN-YunxiNeural"
#       → output/2026-08-13/…/render.json     narration_voice: **Yunjian**
#     specs/reels/lina-cincinnati-2012.json  "voice": "zh-CN-YunxiNeural"
#       → output/2026-08-13/…/render.json     narration_voice: **Yunxi**
#
# ⚠️ 上面这两行是**产物**，只能在本地看（CI 的稀疏检出不含 `output/`），所以
# 它们留在注释里当来路，**不写进断言**——判据只吃 `specs/` 和 `tools/`。


def test_顶层voice和rate是死键要当场报错():
    """写了却没人读，而且不吭声——和 `_push` vs `push` 是同一个形状。"""
    reel = _reel()
    for key, value in (("voice", "zh-CN-YunxiNeural"), ("rate", "+6%")):
        spec = {"slug": "brand-new-reel", key: value}
        with pytest.raises(reel.ReelError, match=key):
            reel._reject_dead_voice_keys(spec)
    # 没写的、以及段级那个真字段，都不许被误伤
    reel._reject_dead_voice_keys({"slug": "brand-new-reel"})
    reel._reject_dead_voice_keys(
        {"slug": "brand-new-reel",
         "segments": [{"voice": {"rate": "-8%", "_why": "这一段是崩盘"}}]})


def test_这道闸真的挂在load_spec上():
    """只测函数行为拦不住「闸没接上」——`_cut_person` 那次就是签名对了、
    实现从来没跑起来过。"""
    reel = _reel()
    body = reel.load_spec.__code__.co_names
    assert "_reject_dead_voice_keys" in body, \
        "死键那道闸没挂进 load_spec，写了等于没写"


def test_顶层voice的豁免表立得住():
    """**只许减不许加**，而且这句话在这儿是**判据**不是注释。

    三头都钉（少一头就有一条静静走掉的路）：
      ① 名字得真的是一条 spec——写错一个名字，豁免就成了一盏恒真的绿灯；
      ② 那个死键得**真的还在**——删干净了就把名字也删掉；
      ③ 而且它得是**存量**（封口日之前就渲过了）。少了③，下一个人新写一条
         spec、顶层照旧写 `voice`，然后把名字加进这张表——**闸对它就没了**，
         而①②全绿。
    """
    reel = _reel()
    rendered = _tracked_reel_products("render.json")
    for slug in sorted(reel._DEAD_TOP_VOICE_LEGACY):
        path = SPEC_DIR / f"{slug}.json"
        assert path.is_file(), f"{slug} 这条 spec 已经没了，把它从豁免表里删掉"
        spec = json.loads(path.read_text("utf-8"))
        assert any(key in spec for key in reel._DEAD_TOP_VOICE_KEYS), (
            f"{slug} 的顶层 voice/rate 已经删掉了，把它从豁免表里也删掉"
            f"——这张表只许减不许加"
        )
        dates = rendered.get(slug, set())
        assert dates and min(dates) <= _LEGACY_CUTOFF, (
            f"{slug} 不是 {_LEGACY_CUTOFF} 之前的存量片子"
            f"（仓库里最早的产物：{min(sorted(dates)) if dates else '一个都没有'}）。\n"
            "**补进来不是把自检改松，是把这条闸对这条片子整个关掉。**\n"
            "顶层 voice/rate 是死键，清掉它只要删一行 JSON——**不用重渲**"
            "（这两个键一个字节都不进成片）。要逐段调语速/音高写 "
            "`segments[].voice`，要换整条片子的嗓子传 `--voice`。")
    # 反过来：库里不许再有第四条带死键、却没挂进表的 spec
    fresh = {slug for slug, spec in _specs()
             if any(key in spec for key in reel._DEAD_TOP_VOICE_KEYS)
             } - set(reel._DEAD_TOP_VOICE_LEGACY)
    assert not fresh, (
        f"这几条又写了顶层 voice/rate：{sorted(fresh)}——"
        "删掉那一行就行，那两个键没有任何代码读")
