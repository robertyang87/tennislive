"""措辞判据的单一出处 + 自动链发布前执法（2026-08-26 内容自动化盘点）。

来路：几成几/写秒/报到分/强字轮次/爱局/要到/盘点主语这批判据原来只活在
pytest 里，而自动出片链（备料 → 提升 → 渲染 → 发布）用 GITHUB_TOKEN 直推
main、**不触发 CI**——模型/自动产的 spec 从生成到发进微信一次都没被扫过。
已经漏过一条（tiafoe-musetti-cincinnati-2026-qf 带着「7点05分」推送，事后
挂豁免表），装闸当天又在 pending 里抓到一条现行（musetti-zheng 的「十六强」）。

现在正则/豁免表/扫描面收在 tools/spec_wording.py 一份，三方共用：
- pytest（全库扫描 + 豁免表自检，判据在 test_reel_editorial / test_match_reel）
- build_match_reel 的 enforce_spec_wording（dry-run / check-narration / render
  一个 seat 全过）
- promote_reel_draft（模型草稿转正那一刻）
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))

from tools.spec_wording import (  # noqa: E402
    CLOCK_MINUTE_LEGACY,
    RALLY_SECONDS_LEGACY,
    check_spec_wording,
)


def _bad_spec() -> dict:
    return {
        "cover": {"hook": "他打进四强"},
        "push": {"summary": "一发只进了三成四",
                 "lead": "中英双语字幕，全程。"},
        "segments": [
            {"narration": "十一点十分开球。这一分打了三十八秒。爱局收尾。"},
            {"narration": "卢布列夫拿到三个盘点。三个都没能救下来。"},
            {"narration": "一口气要到三个破发点。"},
        ],
        "topbar": {},
    }


def test_八类措辞违规一次全抓出来():
    problems = check_spec_wording(_bad_spec(), "not-in-any-legacy", None)
    joined = "\n".join(problems)
    for needle in ("几成几", "写成了秒", "报到了分钟", "强字", "爱局",
                   "要到", "谁在救", "制作规格"):
        assert needle in joined, f"「{needle}」那一类没抓出来：\n{joined}"


def test_promote模板不许再把字幕规格话术写回文案():
    """两个 promote 模板 2026-08-26 之前都写着「…与中英字幕」——每条自动产的
    文案都带着违规出生，interview 那张 78 文件的豁免表就是这么攒出来的。
    reel 侧 BILINGUAL_MENTION 零豁免地拦在 check_spec_wording 里；这条另钉
    模板源码本身（注释行剥掉——修这个坑的注释里正引着那几个词）。"""
    import re  # noqa: PLC0415

    banned = re.compile(r"中英双语|中英文字幕|中英字幕|双语字幕")
    for name in ("tools/promote_reel_draft.py",
                 "tools/promote_interview_draft.py"):
        code = "\n".join(
            ln for ln in Path(name).read_text("utf-8").splitlines()
            if not ln.lstrip().startswith("#"))
        # 只许出现在拦截逻辑里（引用 BILINGUAL_MENTION / 报错文案），
        # 不许出现在会写进 xhs/push 的模板字符串里
        for m in banned.finditer(code):
            ctx = code[max(0, m.start() - 200):m.end() + 200]
            assert "BILINGUAL_MENTION" in ctx or "无旁白冷开场" in ctx, (
                f"{name} 的模板又把「{m.group(0)}」写回了文案："
                f"…{code[max(0, m.start()-60):m.end()+20]}…")


def test_豁免表按slug放行老spec():
    """已发的老 spec 重新 dry-run 必须照旧绿——豁免表和 pytest 用同一份。"""
    spec = {"cover": {"hook": ""}, "push": {},
            "segments": [{"narration": "这一分打了三十八秒。"}], "topbar": {}}
    slug = sorted(RALLY_SECONDS_LEGACY)[0]
    assert not check_spec_wording(spec, slug, None)
    assert check_spec_wording(spec, "fresh-slug", None), (
        "非豁免 slug 也绿——豁免查询多半写反了")
    # 表自检照旧在 test_reel_editorial / test_match_reel（要全库扫描才自检得了）
    assert CLOCK_MINUTE_LEGACY and RALLY_SECONDS_LEGACY


def test_干净的spec一条不报():
    spec = {"cover": {"hook": "决胜盘二比五落后\n五个赛点一个没给"},
            "push": {"summary": "掀翻世界第十六"},
            "segments": [{"narration": "夜里十一点多开球，百分之六十四的一发。"
                                       "他面对七个破发点，救下六个。"}],
            "topbar": {"line1": "ATP1000 辛辛那提 1/4 决赛"}}
    assert check_spec_wording(spec, "fresh-slug", None) == []


def test_出片入口在load_spec之后模式分发之前执法(tmp_path):
    """一个 seat 管 dry-run / check-narration / render 三条路。真调
    enforce_spec_wording：查源码文本只能防「有人把它删了」，防不住
    「它从来没工作过」。"""
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    body = Path("tools/build_match_reel.py").read_text("utf-8")
    seat = body.index("enforce_spec_wording(spec, Path(args.spec))")
    assert body.index("spec = load_spec(Path(args.spec))") < seat
    assert seat < body.index("if args.check_narration:"), (
        "执法要排在模式分发之前——排在某个分支里，别的分支就是空门")

    spec_path = tmp_path / "fresh-model-spec.json"
    spec_path.write_text(json.dumps(_bad_spec(), ensure_ascii=False),
                         encoding="utf-8")
    try:
        reel.enforce_spec_wording(_bad_spec(), spec_path)
    except reel.ReelError as exc:
        assert "措辞不合规矩" in str(exc)
    else:
        raise AssertionError("坏措辞的 spec 没被拦下")
    # 小红书正文也在扫描面里：spec 干净、正文违规，同样要红
    ok_spec = {"cover": {}, "push": {}, "segments": [], "topbar": {}}
    (tmp_path / "fresh-model-spec.xhs.txt").write_text(
        "他一路打进八强。", encoding="utf-8")
    try:
        reel.enforce_spec_wording(ok_spec, spec_path)
    except reel.ReelError as exc:
        assert "强字" in str(exc)
    else:
        raise AssertionError("正文里的强字轮次没被拦下")


def test_模型草稿转正那一刻也要过措辞判据():
    """promote 是模型文案进入可发布池的门；不拦的话要等下一次人类 push 才在
    main CI 上红，而那时已经渲染/发布了。"""
    body = Path("tools/promote_reel_draft.py").read_text("utf-8")
    assert "check_spec_wording" in body
    i = body.index("validate_spec(spec)")
    assert body.index("check_spec_wording", i) > i, (
        "措辞判据要排在 validate_spec 之后的转正路径上")
    assert "xhs_copy(spec)" in body[i:], "转正生成的小红书正文也要一起扫"
