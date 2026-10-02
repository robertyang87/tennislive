"""解说片（「网球有故事」字卡稿）的渲前预检：`tools/explainer_preflight.py`。

三头都要钉，缺一头都是恒真：

① **接上了**：它是 `explainer.yml` 的第一道闸，排在装字体／Chromium／ffmpeg 之前；
② **每一项都会红**：`CHECKS` 里每一项都有一个会红的例子——加一项不给例子，这里就红；
③ **存量零误伤**：今天在产的 52 条稿子全过（红了就是判据写宽了，或者真有一条要改）。

外加两条来路：原来那几次推了微信才被指出的返工（f58553ef / 2c38adef / d18bba31 /
2756cec3），原样放回去，预检当场就红。
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import explainer_preflight as P  # noqa: E402
from tennislive.video import explainer as E  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "explainer.yml"


def _steps() -> list[dict]:
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return spec["jobs"]["explainer"]["steps"]


def _index(steps: list[dict], needle: str) -> int:
    hits = [i for i, s in enumerate(steps) if needle in str(s.get("name", ""))]
    assert len(hits) == 1, f"explainer.yml 里名字含「{needle}」的步骤有 {len(hits)} 个"
    return hits[0]


def test_预检是工作流的第一道闸_排在所有安装之前():
    steps = _steps()
    pre = _index(steps, "渲前预检")
    run = str(steps[pre].get("run", ""))
    assert 'python tools/explainer_preflight.py --slug "$SLUG"' in run, run
    assert "|| true" not in run and not steps[pre].get("continue-on-error"), (
        "预检红了要让整趟停下来——吞掉退出码等于没装")
    # slug 的默认值和 concurrency.group 同一个写法，别另起一个出处
    assert steps[pre]["env"]["SLUG"] == "${{ github.event.inputs.slug || 'hawkeye' }}"
    for later in ("安装中文字体", "安装 Chromium", "安装 ffmpeg", "生成解说视频"):
        assert pre < _index(steps, later), f"预检要排在「{later}」之前"
    # 前面只许有 checkout / setup-python——一点安装都不许排在它前面
    before = [s.get("uses", s.get("name")) for s in steps[:pre]]
    assert all(str(b).startswith(("actions/checkout", "actions/setup-python")) for b in before), before


def test_每条在产的字卡稿今天都过得了预检():
    red = {}
    for slug in E._SCRIPTS:
        for name, problems in P.preflight(slug):
            if problems:
                red.setdefault(slug, []).append(f"{name}：{problems[0].splitlines()[0]}")
    assert len(E._SCRIPTS) >= 40, "字卡稿一条都没扫到，判据失效了"
    assert not red, "\n".join(f"{s} → {v}" for s, v in red.items())


# ── ② 每一项都有一个会红的例子 ─────────────────────────────────────────

_SLUG = "hawkeye"   # 不在任何一张存量表里的在产稿子


def _beat(deck, index=1, **changes):
    segments = list(deck.segments)
    segments[index] = dataclasses.replace(segments[index], **changes)
    return dataclasses.replace(deck, segments=segments)


def _break_column(deck, monkeypatch):
    monkeypatch.setitem(E._OPENINGS, deck.slug, {**E._OPENINGS[deck.slug], "column": "开球之前"})
    return deck


def _break_fake_word(deck, monkeypatch):
    opening = E._OPENINGS[deck.slug]
    monkeypatch.setitem(E._OPENINGS, deck.slug,
                        {**opening, "narration": opening["narration"] + "规则书写着自动生效。"})
    return deck


def _break_one_line(deck, monkeypatch):
    monkeypatch.setitem(E._OPENINGS, deck.slug, {
        **E._OPENINGS[deck.slug], "question": "排名到了为什么还要去打资格赛这件事是谁定的？"})
    return deck


def _break_reading(deck, monkeypatch):
    """`speakable` 把比分的「-」和「挑」都换掉了，所以稿子本身写不红这一项——
    它守的是**念之前那一步**：哪天 `speakable` 漏了一种形状，这一项和
    `test_配音把比分读成几比几而不是几杠几` 一起红。所以例子是让 `speakable` 失手。"""
    monkeypatch.setattr(E, "speakable", lambda text: text)
    return _beat(deck, narration="辛纳 6-3 领先。")


_BREAKERS = {
    "栏目": _break_column,
    "小红书正文 1000 字": lambda d, m: dataclasses.replace(
        d, xhs=d.xhs.split("\n", 1)[0] + "\n\n" + "字" * 1001),
    "标题字位": lambda d, m: dataclasses.replace(
        d, xhs="1" * 21 + "\n" + d.xhs.split("\n", 1)[1]),
    "标签": lambda d, m: dataclasses.replace(
        d, xhs=d.xhs.rsplit("\n\n", 1)[0] + "\n\n#网球时差 #网球"),
    "封面首句窗口": lambda d, m: _beat(
        d, 0, narration="这是一句为了把决定窗口撑爆而写得非常非常非常非常长的封面第一句话吗？"),
    "封面一行": _break_one_line,
    "开场问题卡": lambda d, m: _beat(d, 0, title="这一屏没有问出问题"),
    "字卡认领": lambda d, m: dataclasses.replace(d, slug="__全新的一条字卡稿__"),
    "冒号与记号": lambda d, m: _beat(d, title="答案：维纳斯说"),
    "每屏要点": lambda d, m: _beat(d, points=("只剩一条",)),
    "末屏一问": lambda d, m: _beat(d, len(d.segments) - 1, question=""),
    "配音读法": _break_reading,
    "假词": _break_fake_word,
    # fils-tokyo-qualifying 第一版（2026-09-26）：单字的「第三」「第十」按序数留着，
    # 「第十二」换成了 12——同一行字幕里三个排名两种写法，渲完抽帧才看见。
    "数字半中半洋": lambda d, m: _beat(d, narration="阿尔卡拉斯第三，弗里茨第十，蒂亚福第十二。"),
    "多哈迪拜轮换": lambda d, m: _beat(d, narration="多哈和迪拜的档次是逐年轮换的。"),
    "全称断言": lambda d, m: _beat(d, narration="他一共只进过三次大满贯决赛，三次全部拿下。"),
    "相对时间词": lambda d, m: _beat(d, narration="北京时间今天，美网正赛开打。"),
}


def test_每一项预检都有一个会红的例子():
    assert set(_BREAKERS) == {name for name, _ in P.CHECKS}, (
        "CHECKS 和这里的例子对不上：加了一项预检就要给它一个会红的例子，"
        "否则那一项可能是一条恒真的绿灯")


@pytest.mark.parametrize("name", [name for name, _ in P.CHECKS])
def test_这一项预检真的会红(name, monkeypatch):
    check = dict(P.CHECKS)[name]
    clean = P.load_deck(_SLUG, P.WIDEST_DATE_LABEL)
    assert check(clean) == [], f"「{name}」在干净的 {_SLUG} 上就红了"
    broken = _BREAKERS[name](clean, monkeypatch)
    assert check(broken), f"「{name}」拿到一个明明违规的例子却没红"


# ── 来路：原来那几次推了微信才被指出的，原样放回去 ──────────────────────

def _prepend(monkeypatch, slug: str, text: str, beat: int = 0) -> None:
    beats = list(E._SCRIPTS[slug])
    row = list(beats[beat])
    row[3] = text + row[3]
    beats[beat] = tuple(row)
    monkeypatch.setitem(E._SCRIPTS, slug, tuple(beats))


def _red(slug: str) -> dict[str, list[str]]:
    return {name: probs for name, probs in P.preflight(slug) if probs}


def test_原来那几次返工_预检当场就红(monkeypatch):
    # 2c38adef：ranking-math 第 ⑤ 屏「多哈和迪拜的档次是逐年轮换的」
    _prepend(monkeypatch, "ranking-math", "多哈和迪拜的档次是逐年轮换的，这三站的名单每年都要重查。")
    assert "多哈迪拜轮换" in _red("ranking-math")
    # 2756cec3：qualifier-ceiling 第 ① 屏「北京时间今天，美网正赛开打」
    _prepend(monkeypatch, "qualifier-ceiling", "北京时间今天，美网正赛开打。")
    assert "相对时间词" in _red("qualifier-ceiling")
    # d18bba31：second-serve-clock 带着 1118 字的正文发了出去（超的是 hook）
    caption = E._CAPTIONS["second-serve-clock"]
    monkeypatch.setitem(E._CAPTIONS, "second-serve-clock",
                        {**caption, "hook": caption["hook"] + "字" * 800})
    assert "小红书正文 1000 字" in _red("second-serve-clock")
    # f58553ef：「一共只进过三次大满贯决赛」——换到一条不在存量表里的稿子上
    _prepend(monkeypatch, "hawkeye", "他一共只进过三次大满贯决赛，三次全部拿下。")
    assert "全称断言" in _red("hawkeye")


def test_命令行合格退出0_不合格退出1_没这条稿子退出2(monkeypatch, capsys):
    assert P.main(["--slug", _SLUG, "--date", "2026-09-27"]) == 0
    out = capsys.readouterr().out
    # 合格的也要列出来——只在出错时出声的检查证明不了它看过
    assert out.count("✓") == len(P.CHECKS), out

    _prepend(monkeypatch, _SLUG, "北京时间今天，美网正赛开打。")
    assert P.main(["--slug", _SLUG, "--date", "2026-09-27"]) == 1
    out = capsys.readouterr().out
    assert "✗ 相对时间词" in out and "不用等 TTS" in out

    assert P.main(["--slug", "__没有这条__"]) == 2


def test_栏目认不出时报成一行而不是炸成traceback(monkeypatch, capsys):
    """`column_of` 对没登记／撤掉的栏目会抛 KeyError；「相对时间词」那一项原来直接调它，
    整份预检炸成一段 traceback，其余十几项的报告一起没了（2026-09-27 对抗 review）。"""
    for column in ("没登记过的栏目", "开球之前"):   # 后一个是撤掉的栏目
        monkeypatch.setitem(E._OPENINGS, _SLUG, {**E._OPENINGS[_SLUG], "column": column})
        deck = P.load_deck(_SLUG)
        problems = P.dated_word_problems(deck)
        assert problems and "栏目认不出" in problems[0], problems
        assert P.main(["--slug", _SLUG, "--date", "2026-09-27"]) == 1
        out = capsys.readouterr().out
        assert "✗ 栏目" in out and "✗ 相对时间词" in out, out
        # 其余各项照样报完：合格的那些一个不少
        assert out.count("✓") == len(P.CHECKS) - (3 if column == "没登记过的栏目" else 2), out


def test_最宽的日期真的是最宽的():
    """标题字位按 `WIDEST_DATE_LABEL` 量才等于替所有日期量——这句话本身要钉住。"""
    import datetime as dt

    from tennislive.render.xiaohongshu import xhs_title_len

    day, widths = dt.date(2028, 1, 1), set()
    while day.year == 2028:
        widths.add(xhs_title_len(f"🎾{day.month}.{day.day} "))
        day += dt.timedelta(days=1)
    assert xhs_title_len(f"🎾{P.WIDEST_DATE_LABEL} ") == max(widths), sorted(widths)
    assert len(widths) > 1, "日期宽度一样的话，这条测试就没在量东西"
