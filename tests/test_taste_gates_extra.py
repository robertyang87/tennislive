"""tools/taste_gates_extra.py 的判据：账号所有者口味规则里量过全库、留下来的那几道。

每一道三件事都要钉住：

1. **被打回的那一版真的红**（真阳）——用的就是账号所有者当时否掉的原文
2. **改好之后的那一版真的绿**（反面锚点）——判据宽一点就会把好写法一起判红
3. **全库已发的 spec 一条都不红**（误伤 0），存量表只许减不许加、每一条都真的还在违规

最后一条钉接线：`validate_spec`（`--dry-run`）真的调了它，自动 spec 只报不拦。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from production_history import should_check

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import taste_gates_extra as T  # noqa: E402

REELS = ROOT / "specs" / "reels"
INTERVIEWS = ROOT / "specs" / "interviews"


def _reels() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text("utf-8")) for p in sorted(REELS.glob("*.json"))}


def _xhs(slug: str) -> str | None:
    path = REELS / f"{slug}.xhs.txt"
    return path.read_text("utf-8") if path.is_file() else None


def _court(**cover) -> dict:
    return {"slug": "new-spec", "cover": {"eyebrow": "赛场之上", "layout": "solo", **cover},
            "segments": [{"start": 0, "end": 5, "narration": "下一轮，她还能赢吗？"}]}


# ─────────────────────────────────────────────────────────────── ① 总分差 ──

def test_owner_requested_sun_closing_is_exact_and_not_a_legacy_exemption():
    spec = json.loads((REELS / "sun-gauff-led-replay-story-2026.json").read_text("utf-8"))
    assert spec["segments"][-1]["narration"] == (
        "比分能重置，感觉未必能一起退回去。"
        "期待更可靠的赛场，也期待她握住下一次机会。")
    assert spec["slug"] not in T.ENDING_LEGACY
    assert T.ending_problem(spec) is None


@pytest.mark.parametrize("mutation", ["slug", "column", "text", "last_segment", "quote"])
def test_owner_requested_sun_closing_does_not_waive_other_endings(mutation):
    spec = _court(eyebrow="网球有故事")
    spec["slug"] = "sun-gauff-led-replay-story-2026"
    spec["segments"][-1]["narration"] = (
        "比分能重置，感觉未必能一起退回去。"
        "期待更可靠的赛场，也期待她握住下一次机会。")
    if mutation == "slug":
        spec["slug"] = "some-other-story"
    elif mutation == "column":
        spec["cover"]["eyebrow"] = "赛场之上"
    elif mutation == "text":
        spec["segments"][-1]["narration"] = "五比七，一比六。"
        spec["_production"] = {"readyforrender": True}
    elif mutation == "last_segment":
        spec["segments"].append({"start": 5, "end": 7, "narration": "一比六。"})
    else:
        spec["segments"][-1]["quote"] = "六比一。"
    assert T.ending_problem(spec)


def test_钩子和推送标题不拿全场总分差说事():
    # chung-nagal 第一版（3a72b12e^），账号所有者 2026-09-19 否掉的原文
    rejected = _court(hook="一盘落后翻上来\n全场只多赢一分")
    msg = T.total_margin_problem(rejected)
    assert msg
    # 改法提示不许把人往 O6 上送（09-27：钩子里「破发」「抢七」也不用）——照着「写破发点」
    # 改完，下一趟就红在 O6 上，又是一轮返工（review 第 3 轮）
    assert "破发点" not in msg and "不写「破发」「抢七」" in msg, msg
    assert T.total_margin_problem({**_court(hook="背伤毁掉的生涯\n他咬了三小时翻回来"),
                                   "push": {"summary": "纳瓦罗多赢一分逆转"}})
    for hook in ("总分九十七平\n最后四局全拿走", "她少赢了七个小分\n比分却是她赢"):
        assert T.total_margin_problem(_court(hook=hook)), hook
    # 自动草稿里真出现过的推送标题（specs/reels/pending，旧版正则只认得 19 份里的 8 份）
    for summary in ("高芙总分落后18分仍直落两盘", "科斯秋克总得分领先遭逆转", "克维多总分打平仍三盘险胜",
                    "郑钦文总得分75仍输球", "多9分却输球", "全场落后9分仍赢球"):
        assert T.total_margin_problem({**_court(hook="x"), "push": {"summary": summary}}), summary
    # 反面锚点：改好的那一版、以及关键分的写法
    for hook in ("背伤毁掉的生涯\n他咬了三小时翻回来", "3个赛点全丢了\n最后4分全是她的",
                 "前10次机会全落空\n黄泽林挺进8强", "首盘1比4落后\n后7局赢下6局",
                 "只差一分\n被拖进决胜盘"):
        assert T.total_margin_problem(_court(hook=hook)) is None, hook
    # 反面锚点：「全场」说的是状态，不是总分（review 探出来的误伤）；分钟、几分之一、至少
    for text in ("全场状态差", "全场一直领先", "全场发球差强人意", "全场一直领先两盘", "全场多次破发",
                 "多花了十分钟", "四分之一决赛", "至少三分"):
        assert not T.TOTAL_MARGIN.search(text), text


def test_总分差只管比赛片_网球有故事讲计分故事不拦():
    """账号所有者那两句（09-13、09-19 chung-nagal）说的都是一场球的封面。「总得分多却输了
    比赛」在「网球有故事」里本身就是一个正经的计分故事，不能硬红。"""
    story = _court(hook="总得分多\n却输了比赛")
    assert T.total_margin_problem(story), "赛场之上照旧红"
    story["cover"]["eyebrow"] = "网球有故事"
    assert T.total_margin_problem(story) is None
    story["cover"]["eyebrow"] = ""
    assert T.total_margin_problem(story), "eyebrow 空着按赛场之上算（自动草稿就是空的）"
    hard, _ = T.interview_taste_extra({"slug": "x-interview",
                                       "cover": {"title": ["全场只多赢三分", "「我一直相信自己」"]}})
    assert hard and "总分差" in hard[0], "赛后开麦照旧管"


def test_总分差只有一份正则_预检摆事实用的就是它():
    """`taste_preflight` 原来自己抄了一份（一个漏「总分落后18分」、一个把「全场多次破发」
    摆成总分说法）。一个数写两处必分叉——钉住它们是同一个对象。"""
    import taste_preflight as tp  # noqa: PLC0415

    assert tp.TOTAL_MARGIN is T.TOTAL_MARGIN


# ─────────────────────────────────────────────────────── ② 赛点同义反复 ──

def test_赛点盘点只兑现一个是同义反复_破发点不算():
    # bouzkova-jovic（62fb9194），钩子分两行——换行不能让它漏掉
    assert T.one_of_n_problem(_court(hook="三个赛点\n只兑现了一个"))
    assert T.one_of_n_problem(_court(hook="x"), xhs_text="五个盘点，她只把握住一个")
    # 反面锚点：破发点是真会变的效率（这里只钉「不是 N 选 1 的同义反复」——钩子里写不写
    # 「破发」归 O6 那道判据管）；「一个没给」是救点
    for hook in ("十三个破发点\n他只兑现两个", "五个赛点\n一个没给", "约维奇连救两个"):
        assert T.one_of_n_problem(_court(hook=hook)) is None, hook


def test_盘点跨盘的效率可以认领_one_of_n_why():
    """复审 nit（2026-09-27）：「首盘两个盘点都没拿下、丢了这一盘；两盘下来三个盘点只兑现了
    一个」跨了两个终止单元，是真会变的效率——手写 spec 要有一个和别的 `_why` 同形状的口，
    豁免表只许减、不是出口。三个入口（reel spec／小红书正文／采访）认的是同一个键。"""
    line = "首盘两个盘点都没拿下；两盘下来三个盘点只兑现了一个"
    bad = _court(hook="x")
    bad["segments"] = [{"narration": line}, *bad["segments"]]
    assert T.one_of_n_problem(bad), "不认领照样红"
    assert any("只兑现了一个" in h for h in T.spec_taste_extra(bad)[0])
    claimed = {**bad, "_one_of_n_why": "盘点跨了两盘：首盘两个没拿下丢盘，第二盘兑现一个"}
    assert T.one_of_n_problem(claimed) is None
    assert not any("只兑现了一个" in h for h in T.spec_taste_extra(claimed)[0])
    assert T.xhs_taste_extra(bad, line)[0]
    assert not T.xhs_taste_extra(claimed, line)[0], "小红书正文那一面也要认同一个键"
    iv = {"slug": "new-iv", "cover": {"title": ["首秀赢了", line]}, "push": {"summary": "x"}}
    assert T.interview_taste_extra(iv)[0]
    assert not T.interview_taste_extra({**iv, "_one_of_n_why": "跨盘"})[0]
    assert T.one_of_n_problem({**bad, "_one_of_n_why": "  "}), "空白不算认领"


def test_采访的赛点同义反复只管我们的文案_当事人的原话照实翻():
    """账号所有者 08-19「杜绝类似的弱智文案」说的是我们写的字。`zh` 是球员自己的话的译文——
    球员说「三个盘点只拿下一个」就照实翻，不许因此把片子拦在渲染入口、把自动草稿挡在
    转正外（和「彭帅」那条同一个形状：review 复现过这个假红）。"""
    iv = json.loads((INTERVIEWS / "tien-cobolli-laver-cup-2026-interview.json").read_text("utf-8"))
    assert not T.interview_taste_extra(iv)[0], "底稿原样要是绿的"
    said = {**iv, "zh": list(iv["zh"])}
    said["zh"][-1] = "我那盘有三个盘点，只拿下了一个，所以很沮丧"
    assert not T.interview_taste_extra(said)[0], "当事人的原话被判成了我们的文案"
    wrote = {**iv, "takeaway": {**(iv.get("takeaway") or {}), "point": "三个盘点只兑现了一个"}}
    assert any("只兑现了一个" in h for h in T.interview_taste_extra(wrote)[0]), "我们写的照样红"


def test_赛点同义反复只管我们的文案_解说原声照实翻():
    """赛场之上那一面同一个形状：`quote` 段是转播解说自己的话（账号所有者 2026-09-19
    「精彩的原声解说……配上中英文字幕保留下来」），解说喊一句「三个盘点只拿下一个」就照实
    配双语字幕，不许因此把手写 spec 在 `--dry-run` 拦红（review 第 3 轮复现过这个假红）。"""
    spec = _reels()["alcaraz-fritz-laver-cup-2026"]
    assert not T.spec_taste_extra(spec)[0], "底稿原样要是绿的"
    seg = next(i for i, s in enumerate(spec["segments"]) if s.get("_quote_kind") == "broadcast")
    said = {**spec, "segments": [dict(s) for s in spec["segments"]]}
    said["segments"][seg]["quote"] = [
        {"at": 5.28, "text": "Three set points, and he only converts one!\n三个盘点，他只拿下了一个！"}]
    assert not T.spec_taste_extra(said)[0], "解说的原话被判成了我们的文案"
    wrote = {**spec, "segments": [dict(s) for s in spec["segments"]]}
    wrote["segments"][0]["narration"] = "三个盘点，他只拿下了一个。"
    assert any("只拿下了一个" in h for h in T.spec_taste_extra(wrote)[0]), "我们写的旁白照样红"


# ─────────────────────────────────────────────────── ③ 彭帅（转述来的，只报） ──

def test_会发出去的字里提了彭帅只报_注解不管():
    """形状：会发出去的字里有就出一句提醒，注解栏不管。**它是一条提醒，不是闸**——
    口味规则书里这条标的是「转述（09-16）」，没有账号所有者的原话；那种规则他 2026-09-27
    定了只按自查过，没有原话之前不许做成闸（下一条测试钉行为）。"""
    spec = _court(hook="x")
    spec["segments"][0]["narration"] = "深圳撞上疫情，又撞上彭帅那件事。"
    note = T.peng_shuai_note(T._outward(spec))
    assert note and "转述" in note, note
    assert "账号所有者 2026-09-16：「" not in note, "这条没有他的原话，提醒里不许写成引语"
    # 注解栏可以记（asian-games-vs-china-open 的 `_facts` 里就有「2010 彭帅」）
    noted = {**_court(hook="x"), "_facts": ["2010 彭帅"]}
    assert T.peng_shuai_note(T._outward(noted)) is None


def _mention(spec: dict, xhs: str, word: str) -> tuple[dict, str]:
    """把「<word>那件事。」注进会发出去的几处：第一段旁白（注在末段会撞上「收尾一问」）、
    推送导语、采访字幕、正文。"""
    import copy  # noqa: PLC0415

    spec, line = copy.deepcopy(spec), f"{word}那件事。"
    for seg in spec.get("segments") or []:
        if isinstance(seg, dict) and seg.get("narration"):
            seg["narration"] += line
            break
    push = spec.setdefault("push", {})
    push["lead"] = str(push.get("lead") or "") + line
    if isinstance(spec.get("zh"), list) and spec["zh"]:
        spec["zh"][-1] = str(spec["zh"][-1]) + line
    return spec, f"{xhs}\n{line}"


def test_不提彭帅是转述来的_三个入口都只报不拦(tmp_path, capsys):
    """review 复现过的阻塞：这条做成硬闸时，同一句话注「李娜」`validate_spec` 绿、注「彭帅」
    红；采访线上一条如实翻译球员提到彭帅的字幕会停在渲染入口，含这句字幕的自动草稿转不了正。

    判据：同形的对照词（两个字的中国球员名）和「彭帅」各注一遍——每个入口**硬的那一半
    一模一样**，只报的那一半多出一句转述提醒。渲染入口（`validate_spec`、
    `enforce_spec_wording`、`build_interview_clip.check_taste_extra`）照样过。"""
    reel = pytest.importorskip("build_match_reel")
    clip = pytest.importorskip("build_interview_clip")
    slug = "medvedev-royer-hangzhou-2026-r2"
    base = reel.load_spec(REELS / f"{slug}.json")
    base_xhs = _xhs(slug) or ""
    iv_path = INTERVIEWS / "tien-cobolli-laver-cup-2026-interview.json"
    iv_base = json.loads(iv_path.read_text("utf-8"))
    iv_xhs = iv_path.with_suffix(".xhs.txt").read_text("utf-8")

    def verdicts(word: str) -> dict:
        spec, xhs = _mention(base, base_xhs, word)
        iv, ixhs = _mention(iv_base, iv_xhs, word)
        where = tmp_path / word
        where.mkdir()
        path = where / f"{slug}.json"
        path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        path.with_suffix(".xhs.txt").write_text(xhs, encoding="utf-8")
        reel.validate_spec(json.loads(json.dumps(spec)))            # 不抛
        reel.enforce_spec_wording(json.loads(json.dumps(spec)), path)
        ipath = where / iv_path.name
        ipath.write_text(json.dumps(iv, ensure_ascii=False), encoding="utf-8")
        ipath.with_suffix(".xhs.txt").write_text(ixhs, encoding="utf-8")
        clip.check_taste_extra(iv, ipath)                           # 不 SystemExit
        return {"spec": T.spec_taste_extra(spec),
                "xhs": T.xhs_taste_extra(spec, xhs),
                "interview": T.interview_taste_extra(iv, ixhs)}

    control, probed = verdicts("李娜"), verdicts("彭帅")
    for entry in ("spec", "xhs", "interview"):
        assert probed[entry][0] == control[entry][0], (
            f"{entry}_taste_extra：注进「彭帅」之后硬的那一半变了——转述来的规则只报，"
            f"永不做成闸：{probed[entry][0]}")
        extra = [n for n in probed[entry][1] if "彭帅" in n]
        assert extra and "转述" in extra[0], f"{entry}_taste_extra 该多一句转述提醒：{probed[entry][1]}"
        assert not [n for n in control[entry][1] if "彭帅" in n]
    assert "彭帅" in capsys.readouterr().out, "渲染入口要把提醒印出来"


# ────────────────────────────────────────────── ④ 赛场之上封面不用信箱式 ──

def test_赛场之上封面不用fit_width_认领也不放行():
    # zhang-fernandez 被否掉的那一版（008a8806）**写着 `_fit_why`**
    rejected = _court(portrait={"image": "x.jpg", "fit": "width",
                                "_fit_why": "源图 1280×720 横构图，cover 要放大 2.00 倍"})
    assert T.cover_fit_problem(rejected)
    assert T.cover_fit_problem(_court(portrait={"image": "x.jpg", "zoom": 2.0})) is None
    story = _court(portrait={"image": "x.jpg", "fit": "width"})
    story["cover"]["eyebrow"] = "网球有故事"
    assert T.cover_fit_problem(story) is None, "网球有故事的信箱式不在这条里"


# ─────────────────────────────────────────── ⑤ 赛场之上一律 solo，认领不放行 ──

def test_赛场之上的VS封面写了_layout_why也不放行():
    # shang-mannarino 42cfae85：cutout + 一段认真的 `_layout_why`，账号所有者 2026-09-24 否掉
    rejected = _court(layout="cutout", _layout_why="solo 要的本场官方实拍出片时不存在")
    assert T.solo_layout_problem(rejected)
    assert T.solo_layout_problem(_court()) is None
    story = _court(layout="cutout")
    story["cover"]["eyebrow"] = "网球有故事"
    assert T.solo_layout_problem(story) is None, "网球有故事讲交手史可以用 H2H 双人版"


# ──────────────────── ⑥ 前瞻事实回头查：只有一道闸，在 reel_facts（不在这个模块） ──

@pytest.mark.usefixtures("_empty_reel_ledger")
def test_前瞻事实只有一道闸_认领字段是_rechecked_at():
    """review 复现过的阻塞：这个模块曾另写一份前瞻事实闸（认领 `_pending_resolved`），而 main
    上已经有 `reel_facts.waiting_fact_problem`（认领 `_rechecked_at`）。两道闸各不认对方的
    字段：只写 `_rechecked_at` 被这一份拦；只写 `_pending_resolved` 被那一份拦（它扫全部
    注解，`_pending_resolved` 里抄的「正式名单」自己就是命中）；两样都写才过。合进 main
    当场打红 `test_片子推送一落账_全库扫描不许跟着红_重渲入口照样拦`。

    钉三件事：① 口味闸这一刀对「要等名单」不出声（硬的、只报的都和不写一样）；② 按 main
    的口径只写 `_rechecked_at`，渲染入口和全库盘点都绿；③ 不写照样红，红在 reel_facts
    那一句——报错指人去写 `_rechecked_at`，不是另一个字段。"""
    reel = pytest.importorskip("build_match_reel")
    base = reel.load_spec(REELS / "medvedev-royer-hangzhou-2026-r2.json")
    waiting = {**base, "_facts": ["挪威 2 月鲁德退赛过——所以正式名单要等抽签日"]}
    assert T.spec_taste_extra(waiting) == T.spec_taste_extra(base), (
        "口味闸这一刀又管起了前瞻事实——同一条规矩只许一道闸（reel_facts.waiting_fact_problem）")
    with pytest.raises(reel.ReelError, match="_rechecked_at") as red:
        reel.validate_spec(json.loads(json.dumps(waiting)))
    assert "_pending_resolved" not in str(red.value)
    rechecked = {**waiting, "_rechecked_at": "2026-09-18T06:50Z"}
    reel.validate_spec(json.loads(json.dumps(rechecked)))                          # 渲染入口
    reel.validate_spec(json.loads(json.dumps(rechecked)), allow_published_legacy=True)  # 全库盘点


# ───────────────────────── ⑦~⑪ 从 pytest 挪进 validate_spec 的那五道（形状测试） ──

def test_收尾停在数据上就红_落在一问上就绿():
    # wong-lehecka 0ab84ddd，账号所有者：「不要平白地叙事，要能引爆传播」
    spec = _court()
    spec["segments"][0]["narration"] = "一比六、六比三、六比四。排名差九十六位，生涯排名最高胜。"
    assert T.ending_problem(spec)
    spec["segments"][0]["narration"] += "下一次这样的球，要等多久？"
    assert T.ending_problem(spec) is None
    quoted = _court()
    quoted["segments"].append({"start": 5, "end": 9, "quote": [
        {"at": 1.0, "text": "Can she do it this time?\n这一次，她能拿下吗？"}]})
    quoted["segments"][0]["narration"] = "六比四。"
    assert T.ending_problem(quoted) is None, "末拍是带问号的原声也算数"


def test_推送标题剥完为空和代词插进连读():
    spec = _court(matchup=[{"name": "莱巴金娜"}, {"name": "高芙"}], winner="莱巴金娜")
    spec["push"] = {"summary": "莱巴金娜逆转晋级"}
    assert T.push_summary_problem(spec)
    spec["push"] = {"summary": "决胜局四十比零落后她逆转"}
    assert "代词" in T.push_summary_problem(spec)
    for good in ("零比二落后连赢六局", "莱巴金娜逆转，下一轮打萨巴伦卡"):
        spec["push"] = {"summary": good}
        assert T.push_summary_problem(spec) is None, good


def test_推送标题的代词豁免表只许减():
    specs = _reels()
    for slug in T.SUMMARY_FLUENCY_LEGACY:
        assert slug in specs, f"{slug} 这条 spec 已经没了，从表里删掉"
        assert T.SUMMARY_PRONOUN_SPLIT.search(
            str((specs[slug].get("push") or {}).get("summary") or "")), \
            f"{slug} 已经不违规了，从 SUMMARY_FLUENCY_LEGACY 里删掉"


def test_数据图缺制胜分UE_TennisTV片尾_quote段认领():
    spec = _court()
    spec["stats"] = {"a": {"aces": 3}, "b": {"aces": 1}}
    assert T.winners_ue_problem(spec)
    spec["stats"]["_winners_ue_why"] = "TNNS hasExtendedStats=false"
    assert T.winners_ue_problem(spec) is None

    tv = {**_court(), "_source": "Tennis TV 官方 YouTube"}
    assert T.tennistv_trim_problem(tv)
    assert T.tennistv_trim_problem({**tv, "_tennistv_trim": "末段收在片尾板前 2.1s"}) is None

    q = _court()
    q["segments"].append({"start": 5, "end": 8, "quote": "Game, set and match!\n比赛结束！"})
    assert T.quote_kind_problem(q)
    q["segments"][-1]["_quote_kind"] = "broadcast"
    assert T.quote_kind_problem(q) is None


def test_小红书正文不许markdown_tag行不误伤():
    assert T.xhs_markdown_problem("**加粗**的正文")
    assert T.xhs_markdown_problem("> 引用块")
    assert T.xhs_markdown_problem("#网球 #赛场之上 #网球时差\n- 横杠开头的行") is None


# ═══════════════════════════════════════════════════════════ 只报的四道 ══

def test_只报的四道真的会报_也不会报错好写法():
    assert T.hook_identity_note(_court(hook="只差一分被拖进决胜盘\n他还是淘汰了八号种子"))
    assert T.hook_identity_note(_court(hook="菲斯发球局全没丢\n世界第八还是告负"))
    for ok in ("五比一被追平\n她照样掀翻世界第一", "次盘5比2被追平\n7比5淘汰头号种子",
               "只差一分被拖进决胜盘\n他还是挺进了8强"):
        assert T.hook_identity_note(_court(hook=ok)) is None, ok
    story = _court(hook="温网捧杯之后\n他再没打过一场", topic="辛纳退出中网")
    story["cover"]["eyebrow"] = "网球有故事"
    story["slug"] = "sinner-beijing-withdrawal-2026"
    assert T.social_first_note(story)
    assert T.social_first_note({**story, "_social_checked": "X @janniksin 44s 视频"}) is None
    assert T.screen_numerals_note([("钩子", "三天前刚拿青少年冠军")])
    assert T.screen_numerals_note([("钩子", "只用了三十四分钟")]), "「分钟」是计数，照旧要报"
    for ok in ("3个赛点全丢了", "抢十逆转门西克", "第十五次", "世界第一", "一局没丢", "两个赛点",
               "这一拍十分漂亮", "打进四分之一决赛"):
        assert T.screen_numerals_note([("钩子", ok)]) is None, ok
    assert T.nickname_note(["你支持的是麦迪还是我"])
    assert T.nickname_note(["你支持的是凯斯还是我"]) is None


def _ledger(directory: Path, slug: str, status: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{slug}.json").write_text(json.dumps(
        {"slug": slug, "attempts": [{"status": status, "at": "2026-09-19T02:36:40Z"}]}),
        encoding="utf-8")


def test_汉字数字那条只对还没发出去的片子出声(_empty_reel_ledger, monkeypatch, tmp_path):
    """它在全库报一半（规矩之前的写法），而已发的不为文案重渲——对已经发出去的片子每趟
    dry-run 都印一遍，只会把它训练成没人看的噪音。按发布账本认「发出去了」。

    ⚠️ 账本一律钉在 tmp_path 上（`reel_facts.REEL_LEDGER_DIR` 那行注释：判据测试一律不许读
    真账本）——所以 `already_published` 的路径只从 `reel_ledger_dir()` / `interview_ledger_dir()`
    来；它原来自己拼 `ROOT/data/<账本>`，fixture 钉不住（review 第 3 轮）。"""
    slug = "chung-nagal-davis-cup-2026"
    spec = _reels()[slug]
    assert T.screen_numerals_note([("钩子", spec["cover"]["hook"])]), "底稿要真的有汉字计数"
    assert T.reel_ledger_dir() == _empty_reel_ledger, "fixture 钉不住账本路径"
    _, soft = T.spec_taste_extra(spec)
    assert [n for n in soft if "汉字" in n], "账本是空的＝没发过，照旧要报"
    _ledger(_empty_reel_ledger, slug, "sent")
    _, soft = T.spec_taste_extra(spec)
    assert not [n for n in soft if "汉字" in n], soft
    _, soft = T.spec_taste_extra({**spec, "slug": "chung-nagal-new"})
    assert [n for n in soft if "汉字" in n], "没发过的照旧要报"
    _ledger(_empty_reel_ledger, "failed-once", "failed")
    assert not T.already_published("failed-once", T.reel_ledger_dir()), "失败的那次不算发出去"
    assert not T.already_published("no-such-slug", T.reel_ledger_dir())

    import auto_push_interview_gate  # noqa: PLC0415

    iv_dir = tmp_path / "interview-ledger"
    monkeypatch.setattr(auto_push_interview_gate, "LEDGER_DIR", iv_dir)
    iv = {"slug": "x-interview", "cover": {"title": ["三天前刚拿冠军", "「我一直相信自己」"]}}
    assert [n for n in T.interview_taste_extra(iv)[1] if "汉字" in n], "没发过的采访照旧要报"
    _ledger(iv_dir, "x-interview", "accepted")
    assert T.already_published("x-interview", T.interview_ledger_dir()), "采访账本写的是 accepted"
    assert not [n for n in T.interview_taste_extra(iv)[1] if "汉字" in n]


def test_采访账本路径认_empty_interview_ledger那个钉(_empty_interview_ledger):
    """`interview_ledger_dir()` 和 `publication_ledger.interview_published` 同一个钉法：设了
    `TENNISLIVE_INTERVIEW_LEDGER_DIR` 就只读那个目录（合并 wp/auto-spec-main-green 时补的——
    那一包给采访账本加了这个钉，这一包原来只认 `auto_push_interview_gate.LEDGER_DIR`，
    钉了空账本的测试照样读到真账本）。"""
    assert T.interview_ledger_dir() == _empty_interview_ledger
    iv = {"slug": "x-interview", "cover": {"title": ["三天前刚拿冠军", "「我一直相信自己」"]}}
    assert [n for n in T.interview_taste_extra(iv)[1] if "汉字" in n], "空账本＝没发过，照旧要报"
    _ledger(_empty_interview_ledger, "x-interview", "accepted")
    assert not [n for n in T.interview_taste_extra(iv)[1] if "汉字" in n], "钉住的账本里发过了"


# ═════════════════════════════════════════════ 全库误伤 0 ＋ 存量表只许减 ══

def test_全库已发的spec一条都不红():
    specs = _reels()
    assert len(specs) > 200, "spec 目录像是没扫到"
    red = {}
    for slug, spec in specs.items():
        if not should_check('tests/test_taste_gates_extra.py::test_全库已发的spec一条都不红', ROOT / "specs/reels" / f"{slug}.json"):
            continue
        hard, _ = T.spec_taste_extra(spec)
        hard += T.xhs_taste_extra(spec, _xhs(slug))[0]
        if hard:
            red[slug] = [h.split("\n")[0][:80] for h in hard]
    assert not red, f"已发的 spec 被判红了（误伤，或者存量表漏挂）：{red}"
    # 采访线：自动链刚提交、还没核也没发的 spec **只报**（K 的 `unverified_auto_spec`）——
    # `interview-auto-render` 用 GITHUB_TOKEN 直推 main、CI 不跑，这里判红就红在下一个
    # 无关的 PR 上；同一道闸（`check_taste_extra`）在出片那一趟 `main()` 开头照样拦它，
    # 请求那条路在 `production_preflight.check_request` 就拦（批次 4 复审 BLOCKING）。
    import build_interview_request as req  # noqa: PLC0415
    iv_red, iv_auto = {}, {}
    for path in sorted(INTERVIEWS.glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        xhs = path.with_suffix(".xhs.txt")
        spec = json.loads(path.read_text("utf-8"))
        hard, _ = T.interview_taste_extra(spec, xhs.read_text("utf-8") if xhs.is_file() else None)
        if hard:
            (iv_auto if req.unverified_auto_spec(spec, path.stem) else iv_red)[path.stem] = hard
    req.report_unverified_auto("采访 spec 的口味闸（另一半）", iv_auto)
    assert not iv_red, f"已发的采访 spec 被判红了：{iv_red}"


@pytest.mark.parametrize("table,check", [
    ("TOTAL_MARGIN_LEGACY", lambda s: T.total_margin_problem({**s, "slug": "_"})),
    ("ONE_OF_N_LEGACY", lambda s: T.one_of_n_problem({**s, "slug": "_"})),
    ("FIT_WIDTH_LEGACY", lambda s: T.cover_fit_problem({**s, "slug": "_"})),
    ("SOLO_EXTRA_LEGACY", lambda s: T.solo_layout_problem({**s, "slug": "_"})),
])
def test_存量表只许减不许加(table, check):
    """表里每一条都要真的存在、而且**摘掉豁免之后真的还红**——写错一个名字，
    豁免就成了一盏恒真的绿灯。"""
    specs = _reels()
    for slug in sorted(getattr(T, table)):
        assert slug in specs, f"{table} 里的 {slug} 找不到 spec，从表里删掉"
        assert check(specs[slug]), f"{slug} 已经不违规了，从 {table} 里删掉——只许减不许加"


# ═══════════════════════════════════════════════════════════════ 接线 ══

def test_validate_spec接了这道闸_自动spec只报不拦(capsys):
    reel = pytest.importorskip("build_match_reel")
    spec = reel.load_spec(REELS / "medvedev-royer-hangzhou-2026-r2.json")
    reel.validate_spec(spec)                                  # 原样是绿的
    spec["cover"]["hook"] = "总分只差八分\n梅德韦杰夫挺进8强"
    with pytest.raises(reel.ReelError, match="总分差"):
        reel.validate_spec(spec)
    spec["_production"] = {**(spec.get("_production") or {}), "status": "ready_for_render"}
    reel.validate_spec(spec)                                  # 自动 spec：只报
    assert "[口味] 只报" in capsys.readouterr().out


def test_小红书正文那一面接在措辞座位上(tmp_path):
    """`validate_spec` 拿不到 `.xhs.txt`，markdown／赛点同义反复的正文那一面坐在
    `enforce_spec_wording`（dry-run / check-narration / render 三条路共用的那个座位）。"""
    reel = pytest.importorskip("build_match_reel")
    slug = "medvedev-royer-hangzhou-2026-r2"
    spec = json.loads((REELS / f"{slug}.json").read_text("utf-8"))
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    xhs = (REELS / f"{slug}.xhs.txt").read_text("utf-8")
    path.with_suffix(".xhs.txt").write_text(xhs, encoding="utf-8")
    reel.enforce_spec_wording(spec, path)                      # 原样是绿的
    path.with_suffix(".xhs.txt").write_text(xhs + "\n\n**加粗的一句**", encoding="utf-8")
    with pytest.raises(reel.ReelError, match="markdown"):
        reel.enforce_spec_wording(spec, path)


def test_采访线的口味闸接在渲染入口和转正入口(tmp_path):
    clip = pytest.importorskip("build_interview_clip")
    spec = {"slug": "x-interview", "cover": {"title": ["全场只多赢三分", "「我一直相信自己」"]},
            "push": {"summary": "兹维列夫只多赢三分"}}
    path = tmp_path / "x-interview.json"
    with pytest.raises(SystemExit, match="总分差"):
        clip.check_taste_extra(spec, path)
    clip.check_taste_extra({"slug": "ok", "cover": {"title": ["决胜盘一度落后", "他赢了"]}}, path)
    body = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    main = body[body.index("def main("):]
    assert main.index("check_taste_extra(") < main.index('outdir = OUTDIR'), \
        "`main()` 里 check_taste_extra 要排在任何下载／切行之前"
    promote = (ROOT / "tools" / "promote_interview_draft.py").read_text(encoding="utf-8")
    assert "interview_taste_extra(spec, copy_text)[0]" in promote, "转正入口没接口味闸"
