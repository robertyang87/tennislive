"""措辞判据的单一出处 + 自动链发布前执法（2026-08-26 内容自动化盘点）。

来路：几成几/写秒/报到分/轮次叫法/爱局/要到/盘点主语这批判据原来只活在
pytest 里，而自动出片链（备料 → 提升 → 渲染 → 发布）用 GITHUB_TOKEN 直推
main、**不触发 CI**——模型/自动产的 spec 从生成到发进微信一次都没被扫过。
已经漏过一条（tiafoe-musetti-cincinnati-2026-qf 带着「7点05分」推送，事后
挂豁免表），装闸当天又在 pending 里抓到一条现行（musetti-zheng 的「十六强」）。
⚠️ 轮次那一条 2026-09-01 翻过面：现在拦的是「1/4 决赛 / 1/8 决赛 / 半决赛」，
放行「8 强 / 4 强 / 决赛」，所以这儿的坏样本用的是分数式。

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
    check_interview_copy_wording,
    check_spec_wording,
)


def _bad_spec() -> dict:
    return {
        "cover": {"hook": "他打进1/4决赛"},
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
    for needle in ("几成几", "写成了秒", "报到了分钟", "分数式", "爱局",
                   "要到", "谁在救", "制作规格"):
        assert needle in joined, f"「{needle}」那一类没抓出来：\n{joined}"


def test_文案里不许挂来源注脚():
    """账号所有者 2026-09-03：「文案里不要再出现数据来源及后面的内容」。

    和「不许提中英字幕」是同一族：**溯源是写给仓库里下一个人看的，不是内容**。
    读者不关心我们从哪个 feed 取的数，而它占着正文那 1000 字里的六七十字。

    ⚠️ 来源本身没被取消，只是换了位置——照旧写进 spec 的 `_source` / `_facts` /
    `_claims`，那几栏是注解，`voiced_texts` / `outward_deep` 本来就不扫。

    判据钉四头，缺一头都不够：

    ① **拦得住**，而且两条线都装上了（reel 和 interview 发同一个小红书账号，
       「一条规矩两条线各写一遍必分叉」——所以两个入口用同一个 `SOURCE_FOOTER`）；
    ② **不误伤**「来源」的正当用法——没有冒号的（「信心来源于……」）、
       以及正文中间讲某个数据出处的句子，那是内容不是注脚；
    ③ **注解栏不许被扫到**：`_source` 里写着「数据来源：…」是对的，
       它要是也报红，这条规矩就把溯源本身杀掉了；
    ④ **存量真的清干净了**——零豁免的前提是全库没有命中，
       而不是「我改了几条我记得的」。

    反向验证（三个方向，各红在自己的断言行）：把 `SOURCE_FOOTER` 从
    `check_spec_wording` 拆掉 → ①红；去掉行首锚 `^` → ②红（「信心来源于」
    仍不中，但正文中间的「……来源：」会被抓）；把它加进 `outward_deep`
    扫的面 → ③红。
    """
    from tools.spec_wording import SOURCE_FOOTER  # noqa: PLC0415

    # ① 两条线都拦得住
    for footer in ("数据来源：flashscore、ATP 官方。",
                   "资料来源：美网官方 feed",
                   "来源：维基百科",
                   "素材出处：Tennis TV 官方集锦"):
        caption = f"这场球他赢了。\n\n{footer}\n\n#网球时差 #赛场之上"
        reel = check_spec_wording({"cover": {}, "segments": []},
                                  "not-in-any-legacy", caption)
        assert any("来源注脚" in p for p in reel), f"reel 侧没拦住：{footer}"
        interview = check_interview_copy_wording(
            {"push": {"lead": footer}}, None)
        assert any("来源注脚" in p for p in interview), \
            f"interview 侧没拦住：{footer}"

    # ② 「来源」的正当用法不许误伤
    for ok in ("他的信心来源于那记正手。",
               "这套打法的来源是他少年时的教练。",
               "两个数据对不上，来源不同罢了。"):
        caption = f"{ok}\n\n#网球时差"
        assert not any("来源注脚" in p for p in check_spec_wording(
            {"cover": {}, "segments": []}, "not-in-any-legacy", caption)), \
            f"误伤了正当用法：{ok}"

    # ③ 注解栏是溯源该待的地方，不许被扫到
    with_note = {
        "cover": {},
        "segments": [],
        "_source": "数据来源：flashscore 本场逐分与技术统计。",
        "_facts": ["来源：美网官方 players feed"],
    }
    assert not any("来源注脚" in p for p in
                   check_spec_wording(with_note, "not-in-any-legacy", None)), \
        "把注解栏也扫了——那等于把溯源本身杀掉，而这条规矩只搬位置"

    # ④ 零豁免的前提：全库真的干净
    dirty = [p.name for p in sorted(Path("specs").glob("*/*.xhs.txt"))
             if SOURCE_FOOTER.search(p.read_text(encoding="utf-8"))]
    assert not dirty, (
        f"这条是零豁免的，而这些文案还挂着来源注脚：{dirty}——"
        "要么把它们改掉，要么这条得配一张豁免表（`.xhs.txt` 不进成片、"
        "不参与 qc_attestation 的哈希链，改它不用重渲，所以没有理由攒表）")
    assert len(list(Path("specs").glob("*/*.xhs.txt"))) >= 100, \
        "一份文案都没扫到，第 ④ 头是一盏恒真的绿灯——先证明扫描面还在"


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
            # 顶栏 2026-09-01 进了扫描面（烧在画面上），所以这儿要写新写法——
            # 它顺带充当「N 强不许被误伤」在 topbar 那一面的反面锚点
            "topbar": {"line1": "ATP1000 辛辛那提 8强"}}
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
        "他一路打进1/8决赛。", encoding="utf-8")
    try:
        reel.enforce_spec_wording(ok_spec, spec_path)
    except reel.ReelError as exc:
        assert "分数式" in str(exc)
    else:
        raise AssertionError("正文里的分数式轮次没被拦下")


def _bad_interview_spec() -> dict:
    return {
        "push": {"summary": "他打进1/4决赛后的场上采访",
                 "lead": "中英双语字幕，全程。一发只进了三成四。",
                 "_note": "注解里的爱局不算数"},
        "takeaway": {"close": {
            "point": "十一点十分开球，这一分打了三十八秒",
            "ask": "要到三个破发点还输，怎么看？",
            "_why": "注解不扫"}},
        "cover": {"title": ["爱局收尾之后", "他说了什么？"],
                  "sub": "赛后场上采访",
                  "_why": "注解不扫"},
        "zh": ["他自己说拿到七成的一发。"],  # 引语译文，故意不在扫描面里
    }


def test_采访线转正的措辞判据一次全抓出来():
    problems = check_interview_copy_wording(
        _bad_interview_spec(), "完整视频保留中英字幕。")
    joined = "\n".join(problems)
    for needle in ("几成几", "写成了秒", "报到了分钟", "分数式", "爱局",
                   "要到", "制作规格"):
        assert needle in joined, f"「{needle}」那一类没抓出来：\n{joined}"
    # zh 引语译文故意不在面里：他真说了「七成」只能照实译（见
    # interview_outward_texts 的 docstring）——注解键同理
    assert "七成" not in joined
    assert "注解" not in joined


def test_采访线干净的文案一条不报():
    spec = {"push": {"summary": "伊埃拉赢球后的场上采访",
                     "lead": "辛辛那提，伊埃拉击败对手后的完整场上采访。"},
            "takeaway": {"close": {"point": "赢球后的第一反应",
                                   "ask": "你怎么看这场比赛的表现？"}},
            "cover": {"title": ["她赢球之后", "第一时间说了什么？"]}}
    assert check_interview_copy_wording(
        spec, "她击败对手后在球场内接受了采访。\n\n#网球\n") == []


def test_采访草稿转正那一刻也要过全套措辞判据():
    """原来那儿只拦 BILINGUAL_MENTION 一条——模型/模板写回 push/takeaway 的
    几成几、轮次叫法同样绕过 CI（自动链直推 main）。跳过不炸：草稿留在
    原地等终审，别把一批草稿的提升整个带崩。"""
    body = Path("tools/promote_interview_draft.py").read_text("utf-8")
    assert "check_interview_copy_wording" in body
    i = body.index("spec = promote(draft, opp, details)")
    seat = body.index("check_interview_copy_wording(spec, copy_text)")
    assert i < seat, "措辞判据要跑在 promote 出正式 spec 之后"
    assert seat < body.index("if write:"), "要拦在写盘之前——写完再拦等于没拦"
    block = body[seat:body.index("if write:")]
    assert "skipped.append" in block and "continue" in block, (
        "违规要跳过这一条草稿（等终审），不是抛异常把整批提升带崩")
    assert "BILINGUAL_MENTION.search" not in body, (
        "旧的单条拦截该被全套判据取代——两份并存必分叉")


def test_采访模板产出的文案本身要过全套判据():
    """上一条是源码扫描（防「把规格话术写回模板」），这条真调模板：
    xhs_copy 的产出直接过 check_interview_copy_wording——源码扫描只认
    BILINGUAL 那几个词，模板哪天写进「几成几」「1/4 决赛」之类，只有这条抓得到。"""
    sys.path.insert(0, str(Path("tools").resolve()))
    from promote_interview_draft import xhs_copy  # noqa: PLC0415

    spec = {"match": {"winner": "伊埃拉", "loser": "帕克斯"}}
    assert check_interview_copy_wording({}, xhs_copy(spec)) == []


def test_模型草稿转正那一刻也要过措辞判据():
    """promote 是模型文案进入可发布池的门；不拦的话要等下一次人类 push 才在
    main CI 上红，而那时已经渲染/发布了。"""
    body = Path("tools/promote_reel_draft.py").read_text("utf-8")
    assert "check_spec_wording" in body
    i = body.index("validate_spec(spec)")
    assert body.index("check_spec_wording", i) > i, (
        "措辞判据要排在 validate_spec 之后的转正路径上")
    assert "xhs_copy(spec)" in body[i:], "转正生成的小红书正文也要一起扫"
