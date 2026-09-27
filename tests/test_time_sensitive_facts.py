"""写的时候成立、发出去之后过期的两类话（`reel_facts.time_sensitive_problems`）。

① 注解里写了「正式名单要等抽签日」——每次渲之前都要回头查（davis-china 895dad7b：
   写了要等、两版都没回头查，读者当众指出阵容不对）。
② 「网球有故事」是常青栏目，钩子和旁白不许钉在发布那一天（qualifier-ceiling 2756cec3：
   「北京时间今天，美网正赛开打」）。

两条的量法（为什么只认这几种说法）写在 `tools/reel_facts.py` 那两个正则上面。
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import reel_facts as F  # noqa: E402


def _ledger(tmp_path: Path, slug: str, *sent_at: str) -> Path:
    attempts = [{"status": "sent", "at": at} for at in sent_at]
    attempts.append({"status": "failed", "at": "2099-01-01T00:00:00Z"})  # 不是 sent 不算
    (tmp_path / f"{slug}.json").write_text(
        json.dumps({"slug": slug, "attempts": attempts}), encoding="utf-8")
    return tmp_path


# ── ① 写了「要等」就要回头查 ────────────────────────────────────────────

def test_注解里写了名单要等_就要写回头查的时刻_而且要晚于上一次推送(tmp_path):
    spec = {"slug": "davis-new", "_facts": ["挪威 2 月鲁德退赛过——所以正式名单要等抽签日"]}
    empty = tmp_path / "none"
    empty.mkdir()
    problem = F.waiting_fact_problem(spec, ledger_dir=empty)
    assert problem and "_rechecked_at" in problem and "正式名单" in problem

    # 没发过：写了一个带时区的时刻就放行
    ok = {**spec, "_rechecked_at": "2026-09-17T12:40Z"}
    assert F.waiting_fact_problem(ok, ledger_dir=empty) is None
    # 没写时区的时刻比不了先后
    naive = {**spec, "_rechecked_at": "2026-09-17 12:40"}
    assert "认不出" in F.waiting_fact_problem(naive, ledger_dir=empty)

    # 发过一次：回头查的时刻不晚于那一次 → 重发之前没查
    ledger = _ledger(tmp_path, "davis-new", "2026-09-16T09:48:29Z", "2026-09-17T13:25:18Z")
    stale = F.waiting_fact_problem(ok, ledger_dir=ledger)
    assert stale and "重发之前没回头查" in stale
    fresh = {**spec, "_rechecked_at": "2026-09-18T06:50Z"}
    assert F.waiting_fact_problem(fresh, ledger_dir=ledger) is None
    # 深层注解也算（段里的 `_why`、cover 里的 `_frame_why`）
    deep = {"slug": "davis-new", "segments": [{"narration": "x", "_why": "正式名单待公布"}]}
    assert F.waiting_fact_problem(deep, ledger_dir=empty)
    # 旁白里说「正式名单」不是注解，不归这条管
    said = {"slug": "davis-new", "segments": [{"narration": "正式名单已经公布"}]}
    assert F.waiting_fact_problem(said, ledger_dir=empty) is None


def test_工作流程里的要等不算_只认名单抽签官宣():
    """存量注解里裸的「要等」27 处，只有 davis-china 那一处是「这件事还没定」。"""
    for note in ("剪辑的时候要等死球了再去切下一段视频",
                 "具体帧要等 runner 渲完 poster.jpg 拉回来看一眼再定",
                 "旁白说「六比五」要等板翻过来",
                 "她的第三轮对手要等同一区那场打完才定"):
        assert F.waiting_fact_problem({"slug": "x", "_why": note}) is None, note
    for note in ("正式名单要等抽签日", "要等官宣", "名单定了再写", "抽签后落库", "阵容待公布"):
        assert F.waiting_fact_problem({"slug": "x", "_why": note}), note


# ── ② 常青栏目不钉「今天」 ───────────────────────────────────────────────

def _story(narration: str, **extra) -> dict:
    return {"slug": "story-new", "cover": {"eyebrow": "网球有故事", "hook": "钩子"},
            "segments": [{"narration": narration}], **extra}


def test_网球有故事不许把一件事钉在发布那一天():
    # 2756cec3 之前 qualifier-ceiling 第 ① 屏的原句
    problem = F.dated_words_problem(_story("北京时间今天，美网正赛开打。"))
    assert problem and "北京时间今天" in problem and "_dated_why" in problem
    for text in ("今晚，他又一次站上这里的决赛", "今天公布的首批名单里", "就是刚刚结束的辛辛那提",
                 "今天凌晨，多伦多。"):
        assert F.dated_words_problem(_story(text)), text
    # 认领了就放行；「赛场之上」本来就是当天的片子，不归这条管
    assert F.dated_words_problem(_story("今晚，他又一次站上决赛", _dated_why="冲着今晚那场做的")) is None
    same_day = _story("今晚，他又一次站上决赛")
    same_day["cover"]["eyebrow"] = "赛场之上"
    assert F.dated_words_problem(same_day) is None


def test_到今天和现在那种今天不算():
    """裸的「今天／刚刚」存量里命中 30 条上下，大半是「现在」「勉强」的意思，不过期。"""
    for text in ("从一九七二年办到今天，它去过十五座城市", "直到今天，ITF 认可的比赛用球颜色仍然只有两种",
                 "而今天排在前十的那些人里", "那个月，费德勒才刚刚第一次挤进去",
                 "复出到今天，她十一胜十三负", "搭档今天被激怒到，要求她一定要赢"):
        assert F.dated_words_problem(_story(text)) is None, text


# ── 接在渲染入口上：`validate_spec`（`--dry-run` 0.2 秒就报） ───────────────

def _reel():
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


def test_两条都接在validate_spec上_手写硬拦_自动只报(capsys):
    reel = _reel()
    spec = json.loads((ROOT / "specs/reels/laver-cup-history-2026.json").read_text("utf-8"))
    reel.validate_spec(copy.deepcopy(spec))   # 原样放行

    dated = copy.deepcopy(spec)
    voiced = next(s for s in dated["segments"] if s.get("narration"))
    voiced["narration"] = "北京时间今天凌晨，" + voiced["narration"]
    with pytest.raises(reel.ReelError, match="常青栏目"):
        reel.validate_spec(dated)

    waiting = copy.deepcopy(spec)
    waiting["_facts"] = ["正式名单要等抽签日"]
    with pytest.raises(reel.ReelError, match="_rechecked_at"):
        reel.validate_spec(waiting)

    # 自动产的 spec 没人写认领——只报不拦，别把自动链卡成「今天没有候选」
    auto = copy.deepcopy(dated)
    auto["_production"] = {**(auto.get("_production") or {}), "status": "ready_for_render"}
    try:
        reel.validate_spec(auto)
    except reel.ReelError as exc:
        assert "常青栏目" not in str(exc), "自动 spec 这一条应该只报不拦"
    assert "[时效] 自动 spec，只报不拦" in capsys.readouterr().out


# ── 全库：存量零误伤，豁免表只许减不许加 ─────────────────────────────────

def test_全库存量过得了这两条_豁免表自证它豁免的还在违规():
    specs = {p.stem: json.loads(p.read_text(encoding="utf-8"))
             for p in sorted((ROOT / "specs" / "reels").glob("*.json"))}
    assert len(specs) >= 250, f"只扫到 {len(specs)} 份 spec，扫描面塌了"
    red = {slug: F.time_sensitive_problems(spec) for slug, spec in specs.items()}
    red = {slug: probs for slug, probs in red.items() if probs}
    assert not red, "\n".join(f"{s}：{p[0].splitlines()[0]}" for s, p in red.items())

    assert len(F.LEGACY_WAITING_FACT) <= 1 and len(F.LEGACY_DATED_WORDS) <= 3, "只许减不许加"
    for slug in F.LEGACY_WAITING_FACT:
        spec = specs[slug]
        assert any(F.WAITING_FACT_RE.search(t) for _, t in F.annotation_strings(spec)), (
            f"{slug} 的注解里已经没有「要等」了，从 LEGACY_WAITING_FACT 删掉")
    for slug in F.LEGACY_DATED_WORDS:
        spec = specs[slug]
        cover = spec.get("cover") or {}
        texts = [cover.get("hook"), cover.get("narration")]
        texts += [s.get("narration") for s in spec.get("segments") or [] if isinstance(s, dict)]
        assert cover.get("eyebrow") == "网球有故事" and F.dated_word_hits(texts), (
            f"{slug} 已经不钉「今天」了，从 LEGACY_DATED_WORDS 删掉")


# ── 字卡稿那一面（`explainer._SCRIPTS`，判据在渲前预检里） ────────────────

def test_字卡稿同一条规矩_认领口是dated_why(monkeypatch):
    import explainer_preflight as P  # noqa: PLC0415
    from tennislive.video import explainer as E  # noqa: PLC0415

    red = [p for slug in E._SCRIPTS for p in P.dated_word_problems(P.load_deck(slug))]
    assert not red, "\n".join(red)
    assert len(P.DATED_WORDS_LEGACY) <= 3, "只许减不许加"
    for slug in P.DATED_WORDS_LEGACY:
        deck = P.load_deck(slug)
        texts = [s.narration for s in deck.segments] + [s.title for s in deck.segments]
        texts.append(str((E._CAPTIONS.get(slug) or {}).get("hook", "")))
        assert F.dated_word_hits(texts), f"{slug} 已经不钉「今天」了，从 DATED_WORDS_LEGACY 删掉"

    # 2756cec3 之前 qualifier-ceiling 第 ① 屏的原句放回去，预检当场红
    slug = "qualifier-ceiling"
    beats = list(E._SCRIPTS[slug])
    first = list(beats[0])
    first[3] = "北京时间今天，美网正赛开打。" + first[3]
    monkeypatch.setitem(E._SCRIPTS, slug, (tuple(first), *beats[1:]))
    assert P.dated_word_problems(P.load_deck(slug))
    monkeypatch.setitem(E._OPENINGS, slug, {**E._OPENINGS[slug], "dated_why": "冲着开赛那天做的"})
    assert P.dated_word_problems(P.load_deck(slug)) == []
