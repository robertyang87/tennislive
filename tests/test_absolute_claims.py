"""全称断言那道闸：三条线一份词表，计数式按「生涯动词」认。

来路和量法在 `tools/absolute_claims.py` 的 docstring：
- 解说片这条线原来一道闸都没有——`wawrinka-wildcard`「一共只进过三次大满贯决赛，
  三次全部拿下」推了微信才被指出是四次（f58553ef）；
- 计数式按词放宽量过一次是 9 处命中 7 处误伤（tennis-editorial「我本来想把词表放宽，
  是数据把它否掉的」），这次按「生涯动词 ＋ 同一个数说两遍」再量：闸扫的字段上 9 份命中、
  再加小红书正文 13 份命中，都零误伤（两个面的数和量法见模块 docstring）。
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import absolute_claims as A  # noqa: E402

#: 必须认出来的——全是**生涯／交手**计数（开集，多输一次这句话就错）。
_OPEN_SET = (
    # f58553ef 之前 `wawrinka-wildcard` 第 ④ 屏的原句（打过四次，第四次 2017 法网负纳达尔）
    "他一共只进过三次大满贯决赛，三次全部拿下。",
    "三次交手，中岛此前三次都输——其中一次是今年一月的布里斯班决赛",   # nakashima-medvedev
    "两次打进大满贯决赛，两次都输给德约科维奇。",                   # tsitsipas-royer
    "大满贯的四分之一决赛他去过十次，十次都停在那儿。",             # rublev-virtanen
    "两个人交手过两次，郑钦文两次都输了。",                         # putintseva-bencic
)

#: 不许认的——**这一场之内**的计数（闭集，逐分数据本身就穷举得了），
#: 前五条就是 tennis-editorial 那张「误伤」表，后面是存量里真出现过的同形句。
_IN_MATCH = (
    "决胜盘一共只有四十六个小分",
    "这场球的破发点一共只有四个",
    "上一盘她一共只赢了一局",
    "保发四次全部失败",
    "五场球，她一共只丢了三盘",
    "五次破发点，五次都变成了破发——一个都没浪费。",          # eala-ruse
    "全场两次零比四十，两次都把发球局送了出去。",              # medvedev-zandschulp
    "三次被逼到赛点，三次都扛了过去。",                        # keys-bondar
    "两次拿到盘点，两次都被他救掉。",                          # wu-walton
    # 动词对了、宾语是这一场之内的——存量里没有，写判据时自己造句造出来的
    "两次打进抢七，两次都拿下了。",
    # 同形的另外三句，2026-09-27 对抗 review 造出来的：宾语是盘和局，一场／一周之内数得完
    "他两次站上发球胜赛局，两次都没能拿下",
    "这一周她三次打进第三盘，三次都赢了",
    "本届他两次打进五盘大战，两次都赢",
    # 比分不是断言：采访线 swiatek-arango 的封面文字当场被老词表误认过
    "斯瓦泰克六比零胜阿朗戈",
)


def test_计数式认得出生涯和交手_认不出这一场之内的计数():
    for text in _OPEN_SET:
        assert A.claim_phrases([text]), f"该认的没认：{text}"
    for text in _IN_MATCH:
        assert not A.claim_phrases([text]), f"误伤了这一场之内的计数：{text} → {A.claim_phrases([text])}"
    # 词表那一档照旧
    assert A.claim_phrases(["硬地的巡回赛正赛，她零胜"]) == ["零胜"]
    # `count_form=False` 只看词表——竖版短片计数式存量表靠它豁免那一句
    assert not A.claim_phrases([_OPEN_SET[0]], count_form=False)


def test_认领要两个不同主机_同一个站点算一个():
    phrase = A.claim_phrases([_OPEN_SET[0]])[0]
    texts = [_OPEN_SET[0]]
    assert A.unsourced(texts, None) == [(phrase, 0)]
    assert A.unsourced(texts, {phrase: "查过了"}) == [(phrase, 0)]
    assert A.unsourced(texts, {phrase: "https://www.atptour.com/a ；https://www.atptour.com/b"}) \
        == [(phrase, 1)]
    assert A.unsourced(texts, {
        phrase: "生涯统计 https://www.atptour.com/x ；2017 法网男单 https://en.wikipedia.org/y",
    }) == []
    # 报错要说出路：去哪儿认领、计数式为什么也算
    msg = A.problem_text([(phrase, 0)], "`explainer._CLAIMS['x']`")
    assert "`explainer._CLAIMS['x']`" in msg and "两个独立源" in msg and "计数式" in msg


# ── 竖版短片 ────────────────────────────────────────────────────────────

def _reel():
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


def test_竖版短片的闸也认计数式_存量表只豁免计数式那一句():
    reel = _reel()
    bad = {"slug": "全新的一条", "segments": [],
           "cover": {"hook": "三次交手，三次都输给了他"}}
    with pytest.raises(reel.ReelError, match="全称断言"):
        reel._absolute_claims_need_a_source(bad)

    legacy = sorted(A.REEL_COUNT_LEGACY)[0]
    # 计数式存量：计数式那一句放行……
    reel._absolute_claims_need_a_source({**bad, "slug": legacy})
    # ……词表那一档照旧要认领（存量表不是整条放行）
    with pytest.raises(reel.ReelError, match="零胜"):
        reel._absolute_claims_need_a_source({
            **bad, "slug": legacy, "cover": {"hook": "三次交手，三次都输 硬地零胜"}})


def test_自动产的竖版短片_计数式只报不拦_词表照旧硬拦(capsys):
    """模型写不了 `_claims`——计数式做成硬的，promote 会把一条写着「三次交手，三次都赢」
    的草稿静静跳过（自动链卡成「今天没有候选」）。词表那一档不跟着松。"""
    reel = _reel()
    counted = {"slug": "全新的一条", "segments": [],
               "cover": {"hook": "三次交手，三次都输给了他"}}
    auto = {**counted, "_production": {"status": "ready_for_render"}}
    # 手写的：计数式照旧拦
    with pytest.raises(reel.ReelError, match="全称断言"):
        reel._absolute_claims_need_a_source(counted)
    # 自动的：计数式只报——报要真的报出来，别变成静默放行
    reel._absolute_claims_need_a_source(auto)
    out = capsys.readouterr().out
    assert "自动 spec，计数式只报不拦" in out and "三次交手" in out, out
    # 自动的：词表那一档照旧拦（和计数式写在同一条里也一样）
    with pytest.raises(reel.ReelError, match="零胜"):
        reel._absolute_claims_need_a_source(
            {**auto, "cover": {"hook": "三次交手，三次都输 硬地零胜"}})


def test_竖版短片计数式存量表只许减不许加():
    reel = _reel()
    assert len(A.REEL_COUNT_LEGACY) <= 8, "计数式存量 2026-09-27 冻结在 8 条，只许减不许加"
    for slug in sorted(A.REEL_COUNT_LEGACY):
        path = ROOT / "specs" / "reels" / f"{slug}.json"
        assert path.is_file(), f"存量表里的 {slug} 不存在了——过期的名字就是恒真的绿灯"
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert spec.get("slug") == slug
        still = [p for p, _ in A.unsourced(reel.spec_outward_text(spec), spec.get("_claims"))
                 if A.is_count_phrase(p)]
        assert still, f"{slug} 的计数式已经认领了（或者删了），从 REEL_COUNT_LEGACY 里删掉"


# ── 解说片（`explainer._CLAIMS`） ────────────────────────────────────────

def test_解说片的全称断言要在_CLAIMS里认领两个独立源():
    import explainer_preflight as P  # noqa: PLC0415
    from tennislive.video import explainer as E  # noqa: PLC0415

    red = {deck.slug: P.claim_problems(deck)
           for deck in (P.load_deck(slug) for slug in E._SCRIPTS)}
    red = {slug: probs for slug, probs in red.items() if probs}
    assert not red, "\n".join(p for probs in red.values() for p in probs)

    # 存量表自检：名字要在、而且真的还欠着出处
    assert len(A.EXPLAINER_LEGACY) <= 9, "解说片存量 2026-09-27 冻结在 9 条，只许减不许加"
    for slug in sorted(A.EXPLAINER_LEGACY):
        assert slug in E._SCRIPTS, f"{slug} 已经不是字卡稿了，从 EXPLAINER_LEGACY 里删掉"
        deck = P.load_deck(slug)
        assert A.unsourced(P.outward_texts(deck), E._CLAIMS.get(slug)), (
            f"{slug} 已经没有没认领的全称断言了，从 EXPLAINER_LEGACY 里删掉")


def test_解说片写了计数式不认领就红_认领两个源就放行(monkeypatch):
    """f58553ef 那一句原样放回一条**不在存量表里**的稿子上，预检当场红。"""
    import explainer_preflight as P  # noqa: PLC0415
    from tennislive.video import explainer as E  # noqa: PLC0415

    slug = "hawkeye"
    assert slug not in A.EXPLAINER_LEGACY
    beats = list(E._SCRIPTS[slug])
    first = list(beats[0])
    first[3] = first[3] + "他一共只进过三次大满贯决赛，三次全部拿下。"
    monkeypatch.setitem(E._SCRIPTS, slug, (tuple(first), *beats[1:]))
    red = P.claim_problems(P.load_deck(slug))
    assert red and "进过三次" in red[0], red

    phrase = A.claim_phrases(["他一共只进过三次大满贯决赛，三次全部拿下。"])[0]
    monkeypatch.setitem(E._CLAIMS, slug, {phrase: "https://www.atptour.com/a"})
    assert P.claim_problems(P.load_deck(slug)), "一个源不够"
    monkeypatch.setitem(E._CLAIMS, slug, {
        phrase: "https://www.atptour.com/a ；https://en.wikipedia.org/b"})
    assert P.claim_problems(P.load_deck(slug)) == []


# ── 采访线 ──────────────────────────────────────────────────────────────

def _interview_specs():
    for path in sorted((ROOT / "specs" / "interviews").glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        yield path, json.loads(path.read_text(encoding="utf-8"))


def test_采访线的全称断言要认领_引号里的是受访者的话():
    red, seen = [], 0
    for path, spec in _interview_specs():
        seen += 1
        problem = A.interview_problem(spec, path.stem)
        if problem:
            red.append(f"{path.name}：{problem.splitlines()[2]}")
    assert seen >= 50, f"只扫到 {seen} 份采访 spec，扫描面塌了"
    assert not red, "\n".join(red)

    assert len(A.INTERVIEW_LEGACY) <= 2, "采访线存量 2026-09-27 冻结在 2 条，只许减不许加"
    for slug in sorted(A.INTERVIEW_LEGACY):
        path = ROOT / "specs" / "interviews" / f"{slug}.json"
        assert path.is_file(), f"存量表里的 {slug} 不存在了"
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert A.unsourced(A.interview_texts(spec), spec.get("_claims")), (
            f"{slug} 已经没有没认领的全称断言了，从 INTERVIEW_LEGACY 里删掉")

    ours = {"push": {"lead": "她是本赛季唯一一个八站首战全胜的球员。"}}
    assert A.interview_problem(ours, "全新的一条")
    quoted = {"push": {"lead": "她说：「过去十年我从来没有成功过。」"}}
    assert A.interview_problem(quoted, "全新的一条") is None
    # 注解不算发出去的话
    assert A.interview_problem({"push": {"_why": "上一版写了「唯一一个」"}}, "x") is None


def test_采访线自动转正的模板文案过得了全称断言那道闸():
    """采访线的闸对自动转正的 spec 也是硬的（没有竖版短片「自动 spec 只报」那一刀）——
    成立的前提是**自动草稿不带文案、promote 只填模板**。模板里哪天写进「唯一一个」
    「N 次打进，N 次都」，自动 dispatch 的 render 会在前置检查上整批红，这里先红。

    带着 push/takeaway 的草稿只可能是**手改过的**（人写得了 `_claims`），照旧硬拦；
    人工请求不经过草稿（`build_interview_request` 直接写正式 spec），见下一条。
    """
    import promote_interview_draft as PI  # noqa: PLC0415

    draft = {
        "_draft": True,
        "slug": "brand-new-oncourt",
        "url": "https://example.test/oncourt",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "event": "2026 辛辛那提大师赛",
        "zh": ["a"],
        "match": {"id": "2026:cincinnati:r3:alexander-zverev", "event": "辛辛那提大师赛",
                  "year": 2026, "round": "第三轮", "interviewee_en": "Alexander Zverev"},
        "source_verification": {
            "status": "verified", "detected_type": "on_court",
            "method": "human_visual_verdict", "source_url": "https://example.test/oncourt",
            "evidence": [{"kind": "visual_verdict", "by": "test"}]},
    }
    spec = PI.promote(draft, ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内"))
    texts = A.interview_texts(spec)
    # 模板真的铺进了扫描面（不然下面那句放行是空转）
    assert any("兹维列夫" in t for t in texts) and spec["takeaway"] and spec["cover"], texts
    assert A.interview_problem(spec, spec["slug"]) is None, A.claim_phrases(texts)

    # 手补进草稿的文案 promote 原样保留——写了断言没认领，照旧红
    asked = {**draft, "push": {"lead": "他此前六次打进正赛，六次全部首轮出局。"}}
    spec = PI.promote(asked, ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内"))
    assert A.interview_problem(spec, spec["slug"]), "人写的文案不在自动分流里，要硬拦"


def _interview_request(slug: str) -> dict:
    """一份内联的人工采访请求，形状照 `requests/interviews/zverev-tien-laver-cup-2026-interview.json`
    剪的（复审 2026-09-27 的 nit）：原来这几条测试直接读仓库里的真请求，那几份一归档、
    改名，测试就死在 FileNotFoundError 上，什么都没测。文案里没有全称断言，原样过得了闸。"""
    return {
        "slug": slug,
        "url": "https://www.youtube.com/watch?v=SJlfFppeoF4",
        "source": "Laver Cup",
        "source_title": "Alexander Zverev On-Court Interview | Laver Cup 2026 Match 10",
        "requested_content_type": "on_court",
        "received_at": "2026-09-27T15:58:40Z",
        "event": "2026 拉沃尔杯 第三天",
        "winner": "兹维列夫",
        "featured_player": "兹维列夫",
        "opening": {"kind": "none", "why": "官方场上采访，源片就是采访本身。"},
        "match": {
            "id": f"2026:laver-cup:{slug}", "event": "2026 Laver Cup",
            "event_search": "Laver Cup", "round": "Day 3 Match 10 (singles)", "year": 2026,
            "winner": "兹维列夫", "loser": "勒纳·钱", "participants": ["兹维列夫", "勒纳·钱"],
            "winner_en": "Alexander Zverev", "loser_en": "Learner Tien",
            "score": "7-6(3) 6-3", "court": "The O2",
        },
        "cover": {"frame_at": 30, "title": ["前一天握赛点被逆转", "兹维列夫锁定欧洲夺冠"],
                  "sub": "拉沃尔杯第三天单打 赛后场上采访", "tag": "2026 拉沃尔杯 · 兹维列夫"},
        "takeaway": {"close": {"point": "前一天被逆转 今天他亲手锁定冠军",
                               "ask": "欧洲队13比5夺冠 下一届你看好谁？"}},
        "push": {"matchup": "兹维列夫 vs 勒纳·钱", "score": "7-6(3) 6-3", "event": "",
                 "summary": "兹维列夫赛后开麦",
                 "lead": "兹维列夫 7-6(3)、6-3 胜勒纳·钱，欧洲队 13-5 夺回拉沃尔杯。",
                 "auto": False},
        "xhs": "前一天握着赛点被逆转，今天兹维列夫亲手把拉沃尔杯拿回了欧洲。\n\n"
               "#网球时差 #拉沃尔杯 #兹维列夫 #赛后开麦",
    }


def test_人工请求的_claims跟进正式spec_没认领在build那一刻就红(tmp_path, monkeypatch):
    """人工请求**不经过草稿**：`build_interview_request` 直接写 specs/interviews/<slug>.json，
    `promote_all` 那道闸看不见它。所以要两件事——

    ① 请求里的 `_claims` 跟着文案进正式 spec。原来 `build_spec` 和「只改元数据」那条路
       都不抄：push 原样进去了、认领丢了，人核过源的断言照样红在 render 前置检查上；
    ② 没认领的在 build 那一刻（`production_preflight.check_request`，ASR／翻译之前）就红，
       报错指回请求文件——不等 dispatch 之后再红一趟。

    复现（对抗 review 2026-09-27）：一份真请求的形状（`_interview_request`），
    push.lead 换成一句计数式。
    """
    import build_interview_request as B  # noqa: PLC0415
    import interview_source_gate  # noqa: PLC0415
    import production_preflight as PP  # noqa: PLC0415

    req = _interview_request("claims-follow-interview")
    slug = req["slug"]
    benign = copy.deepcopy(req)
    claim = "他此前六次打进正赛，六次全部首轮出局。"
    sourced = {claim: "逐场表核过 https://a.example/x ；https://b.example/y"}
    req["push"] = {**req["push"], "lead": claim}

    # ① build_spec：认领跟进正式 spec，render 前置检查那一关放行
    spec = B.build_spec({**req, "_claims": sourced}, ["谢谢大家"], duration=300.0)
    assert spec.get("_claims") == sourced, "请求里的认领没进正式 spec"
    assert A.interview_problem(spec, slug) is None
    # ……没认领的照红（上面那句放行不是空转）；没写 `_claims` 的请求 spec 里也不凭空多一个空键
    bare = B.build_spec(req, ["谢谢大家"], duration=300.0)
    assert "_claims" not in bare and A.interview_problem(bare, slug)

    # ② check_request：build 那一刻就拦，报错指回请求文件
    copies = []
    monkeypatch.setattr(PP, "check_copy", lambda *a, **k: copies.append(a))
    with pytest.raises(ValueError, match="全称断言") as err:
        PP.check_request(req)
    assert f"requests/interviews/{slug}.json 的 `_claims`" in str(err.value)
    assert not copies, "断言那一关排在文案检查前面，红了就不用再起子进程"
    PP.check_request({**req, "_claims": sourced})
    PP.check_request(benign)                        # 没改过的请求原样过得了
    assert len(copies) == 2

    # ③ 「只改元数据」那条路（转写相关的键没变，不重跑 ASR）：
    #    文案改成断言、没认领 → build 红、正式 spec 不动；补上认领 → 认领和文案一起落盘
    specs, out = tmp_path / "specs", tmp_path / "output"
    (out / slug).mkdir(parents=True)
    specs.mkdir()
    (out / slug / "cap_asr.json3").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(B, "SPECS", specs)
    monkeypatch.setattr(B, "OUTDIR", out)
    monkeypatch.setattr(B, "_transcribe_request",
                        lambda *a, **k: pytest.fail("只改元数据不许重跑 ASR"))
    existing = B.build_spec(benign, ["谢谢大家"], duration=300.0)
    existing["_request_origin"] = {"request": copy.deepcopy(benign), "duration": 300.0}
    spec_path = specs / f"{slug}.json"
    spec_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    (specs / f"{slug}.xhs.txt").write_text(str(benign.get("xhs") or ""), encoding="utf-8")
    before = spec_path.read_bytes()
    req_path = tmp_path / "request.json"

    req_path.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="全称断言"):
        B._build_one(req_path, object(), write=True)
    assert spec_path.read_bytes() == before, "红了就不许写正式 spec"

    req_path.write_text(json.dumps({**req, "_claims": sourced}, ensure_ascii=False),
                        encoding="utf-8")
    B._build_one(req_path, object(), write=True)
    written = json.loads(spec_path.read_text("utf-8"))
    assert written["push"]["lead"] == claim
    assert written.get("_claims") == sourced, "只改元数据那条路没把认领带进 spec"
    assert A.interview_problem(written, slug) is None
    interview_source_gate.validate_source_contract(written)

    # ④ 请求把那句断言连同认领一起撤掉：spec 里的 `_claims` 跟着删，不留一个 `null`
    req_path.write_text(json.dumps(benign, ensure_ascii=False), encoding="utf-8")
    B._build_one(req_path, object(), write=True)
    written = json.loads(spec_path.read_text("utf-8"))
    assert written["push"] == benign["push"]
    assert "_claims" not in written, f"请求删了 `_claims`，spec 里剩下 {written.get('_claims')!r}"


def test_采访线的全称断言在runner的前置检查里就红(tmp_path, monkeypatch):
    """`interview-clip.yml` 的「发布文案前置检查」跑的就是 production_preflight。"""
    import production_preflight as PP  # noqa: PLC0415

    spec = tmp_path / "brand-new-interview.json"
    spec.write_text(json.dumps(
        {"push": {"lead": "他此前六次打进正赛，六次全部首轮出局。"}}, ensure_ascii=False),
        encoding="utf-8")
    copies = []
    monkeypatch.setattr(PP, "check_copy", lambda *a, **k: copies.append(a))
    monkeypatch.setattr(sys, "argv", ["production_preflight.py", "--spec", str(spec),
                                      "--column", "赛后开麦"])
    with pytest.raises(SystemExit, match="全称断言"):
        PP.main()
    assert not copies, "断言那一关要排在文案检查前面，红了就不用再起子进程"

    # 竖版短片那条线不走这一关（它的闸在 validate_spec 里）
    monkeypatch.setattr(sys, "argv", ["production_preflight.py", "--spec", str(spec),
                                      "--column", "赛场之上"])
    PP.main()
    assert copies


def _workflow_run(name: str) -> str:
    """按 YAML 解析取某一步的 `run:`——不按文本切（注释里会提到步骤名）。"""
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load((ROOT / ".github/workflows/interview-auto-render.yml")
                         .read_text(encoding="utf-8"))
    runs = [step["run"] for job in doc["jobs"].values() for step in job["steps"]
            if step.get("name") == name and "run" in step]
    assert len(runs) == 1, f"找不到（或不止一个）步骤「{name}」"
    return runs[0]


def test_一条人工请求没过闸_不连坐同一趟的其余请求(tmp_path, monkeypatch, capsys):
    """`interview-auto-render.yml`「人工指定请求转写、切行并逐行翻译」原来单条红就整步
    退出 1：同一趟后面的「补片头」「提交」全被跳过，别的请求白 build 一遍、没提交，每 10
    分钟重来一趟，直到有人修好那一条（复审 2026-09-27）。

    现在两条请求一起跑、其中一条带没认领的全称断言：
    ① `build_interview_request --failed-list` 退出 0，好的那条照常落盘；坏的那条一个字节
       都不写、`::error file=` 指回请求文件、记进失败清单；
    ② 提交那一步跳过坏的那条的转写，好的照常 add（真跑那段 bash，git 打桩）；
    ④ dispatch 那一步也跳过坏的那条（它的正式 spec 还是上一版），好的照常投；
    ③ 最后一步读失败清单：有就写 run 摘要、把整趟标红；没有就绿。
    """
    import subprocess  # noqa: PLC0415

    import build_interview_request as B  # noqa: PLC0415
    import production_preflight as PP  # noqa: PLC0415
    import tennislive.research.brief as brief  # noqa: PLC0415

    # 产物目录照仓库的相对布局摆（output/interviews/<slug>），下面②那段 bash 就在 tmp_path 里跑
    requests_dir, specs = tmp_path / "requests", tmp_path / "specs"
    out = tmp_path / "output" / "interviews"
    for folder in (requests_dir, specs):
        folder.mkdir()
    monkeypatch.setattr(B, "REQUESTS", requests_dir)
    monkeypatch.setattr(B, "SPECS", specs)
    monkeypatch.setattr(B, "OUTDIR", out)
    monkeypatch.setattr(B, "_transcribe_request",
                        lambda *a, **k: pytest.fail("只改元数据不许重跑 ASR"))
    monkeypatch.setattr(PP, "check_copy", lambda *a, **k: None)

    class _Ready:                                   # 只改元数据那条路不调模型
        ready = True

    monkeypatch.setattr(brief, "Chat", _Ready)

    def seed(name: str, lead: str) -> tuple[str, Path]:
        benign = _interview_request(name)
        slug = benign["slug"]
        (out / slug).mkdir(parents=True)
        (out / slug / "cap_asr.json3").write_text("{}", encoding="utf-8")
        existing = B.build_spec(benign, ["谢谢大家"], duration=300.0)
        existing["_request_origin"] = {"request_sha256": "上一版",
                                       "request": copy.deepcopy(benign), "duration": 300.0}
        (specs / f"{slug}.json").write_text(json.dumps(existing, ensure_ascii=False),
                                            encoding="utf-8")
        (specs / f"{slug}.xhs.txt").write_text(str(benign.get("xhs") or ""), encoding="utf-8")
        req = {**benign, "push": {**benign["push"], "lead": lead}}
        (requests_dir / f"{name}.json").write_text(json.dumps(req, ensure_ascii=False),
                                                   encoding="utf-8")
        return slug, requests_dir / f"{name}.json"

    bad_slug, bad_path = seed("unclaimed-interview", "他此前六次打进正赛，六次全部首轮出局。")
    good_slug, _ = seed("benign-interview", "兹维列夫拿下决定性的 3 分，欧洲队夺回拉沃尔杯。")
    bad_before = {p: p.read_bytes() for p in (specs / f"{bad_slug}.json",
                                              specs / f"{bad_slug}.xhs.txt", bad_path,
                                              out / bad_slug / "cap_asr.json3")}
    assert len(B.pending_paths()) == 2, "两条都该是待 build 的——不然下面测的不是「同一趟」"

    # ① 一条红、一条照常写；退出码不因为单条变 1
    failed = tmp_path / "request-failed.txt"
    monkeypatch.setattr(sys, "argv", ["build_interview_request.py", "--write",
                                      "--failed-list", str(failed)])
    assert B.main() == 0
    stdout = capsys.readouterr().out
    rows = [line.split("\t") for line in failed.read_text("utf-8").splitlines()]
    assert len(rows) == 1, rows
    path_col, slug_col, reason = rows[0]
    assert path_col.endswith(bad_path.name) and slug_col == bad_slug
    assert "全称断言" in reason and f"requests/interviews/{bad_slug}.json" in reason
    assert f"::error file={path_col}::" in stdout and "没过闸" in stdout
    assert f"✅ {good_slug}" in stdout
    good = json.loads((specs / f"{good_slug}.json").read_text("utf-8"))
    assert good["push"]["lead"].startswith("兹维列夫拿下决定性的 3 分")
    assert {p: p.read_bytes() for p in bad_before} == bad_before, "没过闸的那条不许落盘"

    # 工作流真的把清单交给了这个工具，最后那一步 `always()` 且读的是同一个文件
    import re  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    build_step = _workflow_run("人工指定请求转写、切行并逐行翻译")
    assert re.search(r"build_interview_request\.py --write\s*\\?\s*--failed-list "
                     r"/tmp/request-failed\.txt", build_step), build_step
    doc = yaml.safe_load((ROOT / ".github/workflows/interview-auto-render.yml")
                         .read_text(encoding="utf-8"))
    names = [step.get("name") for job in doc["jobs"].values() for step in job["steps"]]
    report_name = "人工请求没过闸：其余已照常提交、dispatch，整趟标红"
    assert names.index(report_name) > names.index("dispatch 未 render 的正式 spec（每 slug 一个 run，并行）")
    report_if = next(step["if"] for job in doc["jobs"].values() for step in job["steps"]
                     if step.get("name") == report_name)
    assert "always()" in report_if, "前面哪一步红了，这一步也得跑到"

    # ② 提交那一步：坏的那条的转写不进 add，好的照常（git 打桩，只记参数）
    commit = _workflow_run("提交生成与提升结果")
    start = commit.index('FAILED_SLUGS=""')
    end = commit.index("\nfi", commit.index("done < /tmp/request-slugs.txt")) + 3
    slugs = tmp_path / "request-slugs.txt"
    slugs.write_text(f"{bad_slug}\n{good_slug}\n", encoding="utf-8")
    loop = (commit[start:end].replace("/tmp/request-failed.txt", str(failed))
            .replace("/tmp/request-slugs.txt", str(slugs)))
    ran = subprocess.run(["bash", "-euo", "pipefail", "-c",
                          'git() { echo "GIT $*"; }\n' + loop],
                         cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert f"GIT add -f output/interviews/{good_slug}/cap_asr.json3" in ran.stdout
    assert f"output/interviews/{bad_slug}/" not in ran.stdout.replace(f"[跳过] {bad_slug}", "")
    assert f"[跳过] {bad_slug}" in ran.stdout

    # ④ dispatch 那一步：没过闸的那条不投——它的正式 spec 还是上一版，上一版的 render 要是
    #    没落地（过了 STALE_MINUTES），pick 会把它当待渲再投，push.auto 的话旧版就抢先发了
    #    （复审 2026-09-27 的 nit）。pick / gh / git 打桩，真跑那段 bash。
    dispatch = _workflow_run("dispatch 未 render 的正式 spec（每 slug 一个 run，并行）")
    stubs = ('python() { if [ "$2" = "--mark-one" ]; then echo "MARK $3"; '
             f'else printf "待渲：\\n%s\\n%s\\n" {bad_slug} {good_slug}; fi; }}\n'
             'gh() { echo "GH $*"; }\ngit() { echo "GIT $*"; }\n')

    def dispatched(listing: Path) -> subprocess.CompletedProcess:
        body = (dispatch.replace("/tmp/request-failed.txt", str(listing))
                .replace("/tmp/todo.txt", str(tmp_path / "todo.txt")))
        return subprocess.run(["bash", "-eo", "pipefail", "-c", stubs + body],
                              cwd=tmp_path, capture_output=True, text=True, timeout=30,
                              env={**os.environ, "GITHUB_STEP_SUMMARY": str(tmp_path / "d.md")})

    ran = dispatched(failed)
    assert ran.returncode == 0, ran.stderr
    assert f"-f slug={good_slug} -f mode=render" in ran.stdout and f"MARK {good_slug}" in ran.stdout
    assert f"slug={bad_slug}" not in ran.stdout and f"MARK {bad_slug}" not in ran.stdout
    assert f"[跳过] {bad_slug}" in ran.stdout
    # 清单空着（这一趟都过了闸）：两条照常投——上面那句不投不是把 dispatch 整个关了
    ran = dispatched(tmp_path / "none-failed.txt")
    assert ran.returncode == 0, ran.stderr
    assert all(f"MARK {s}" in ran.stdout for s in (bad_slug, good_slug)), ran.stdout

    # ③ 最后一步：有失败就写摘要、整趟标红；清单空着就绿
    report = _workflow_run(report_name)
    summary = tmp_path / "summary.md"

    def final(listing: str) -> subprocess.CompletedProcess:
        failed.write_text(listing, encoding="utf-8")
        summary.write_text("", encoding="utf-8")
        return subprocess.run(
            ["bash", "-eo", "pipefail", "-c", report.replace("/tmp/request-failed.txt", str(failed))],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "GITHUB_STEP_SUMMARY": str(summary)})

    red = final("\t".join(rows[0]) + "\n")
    assert red.returncode == 1 and "1 条人工请求没过闸" in red.stdout
    assert path_col in summary.read_text("utf-8") and bad_slug in summary.read_text("utf-8")
    green = final("")
    assert green.returncode == 0 and summary.read_text("utf-8") == ""


def test_请求读不了时失败清单的slug列按文件名认_不许空着(tmp_path, monkeypatch):
    """失败清单第二列是 dispatch／提交那两道闸 `cut -f2` 过滤用的 slug。请求在 build 那一刻
    读不了（JSON 被改坏、slug 被删）时原来写 `""`——那两道就拦不住它上一版的正式 spec
    （复审 2026-09-27 nit）。按文件名认：requests/interviews/<slug>.json。"""
    import build_interview_request as B  # noqa: PLC0415
    import tennislive.research.brief as brief  # noqa: PLC0415

    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    broken = requests_dir / "broken-interview.json"
    broken.write_text("{ 这不是 JSON", encoding="utf-8")
    no_slug = requests_dir / "no-slug-interview.json"
    no_slug.write_text(json.dumps({"url": "https://example.com"}), encoding="utf-8")
    monkeypatch.setattr(B, "pending_paths", lambda only="": [broken, no_slug])

    class _Ready:
        ready = True

    monkeypatch.setattr(brief, "Chat", _Ready)
    failed = tmp_path / "request-failed.txt"
    monkeypatch.setattr(sys, "argv", ["build_interview_request.py", "--write",
                                      "--failed-list", str(failed)])
    assert B.main() == 0
    rows = [line.split("\t") for line in failed.read_text("utf-8").splitlines()]
    assert [row[1] for row in rows] == ["broken-interview", "no-slug-interview"], rows


def test_check_request逐条调用不许把sys_path越撑越长(monkeypatch):
    """一趟 build 逐条请求各调一次 `check_request`；原来每调一次就往 sys.path 头上插一次
    tools/（复审 2026-09-27 的 nit）。"""
    import production_preflight as PP  # noqa: PLC0415

    monkeypatch.setattr(PP, "check_copy", lambda *a, **k: None)
    req = _interview_request("sys-path-interview")
    PP.check_request(req)
    before = list(sys.path)
    for _ in range(3):
        PP.check_request(req)
    assert sys.path == before
