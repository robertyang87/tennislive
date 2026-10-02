"""2026-09-28 返工审计里的八道小闸：每一道单拿出来都不大，每一道都各烧掉过一整趟 render
或者一次重推（`rework_audit_0928`，82 趟失败 run ＋ 25 次推送后重推）。

| # | 闸 | 来路 |
|---|---|---|
| 1 | 章节卡超 18 字在 `--dry-run` 就红 | china-open-withdrawals（run 36296202661）、asiad-2026-men-draw（run 36296693320） |
| 2 | 「写过源片末尾」容差从 +0.05s 收成 0 | hu-kopriva-chengdu-2026-r1（run 35949569743） |
| 3 | 误差带里的旁白要拿真 TTS 认账（09-28 会话：没账只报，量过装不下才红） | zverev-deminaur-laver-cup-2026 第 9 段（run 36257658569） |
| 4 | 蒙版先缩成裁框尺寸再 alphamerge | safiullin-bu-hangzhou-2026-qf（run 36323549463，424×108 对 424×109） |
| 5 | 已知带片尾板的源，话音后空太久，手写采访红 | alcaraz-fritz-interview（1b0b65ee5）、tien-cobolli（9ae8918fb）——⚠️ 这两条是自动 spec，这道闸只报、拦不住（归出片那一趟的 `end_card_problem`） |
| 6 | 钩子「送××进决赛」不算赛果；「N号种子」只报 | bucsa-noskova（872c6dab6）；bu-majchrzak（61e62b8a5） |
| 7 | 多源 `_no_probe_why` 要带宽高帧率 | sinner-beijing-withdrawal-2026（run 36133328467） |
| 8 | 开着回贴、probe 没量板，手写红 | prozorova-eala（run 36020126044）、alcaraz-mensik-doubles（run 36197683115） |

每一道：手写 spec 硬、自动 spec 只报、已发的冻进豁免表（只许减、自带自检）。
⚠️ 第 3 道例外（2026-09-28 会话决定，时效第一）：**没账只报**，只有量过、装不下才红——
specs/reels 下 316 条能解析的 spec 里 305 条落在误差带里，没账就红等于每条新片子多一趟 runner；
render 编码之前那道真 TTS 旁白闸兜底。冻结表 `legacy_narration_unchecked.json` 随之删掉。
"""
from __future__ import annotations

import inspect
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_match_reel as reel  # noqa: E402
import probe_board as pb  # noqa: E402
import probe_sources as ps  # noqa: E402
import render_title_card as tc  # noqa: E402
import taste_gates as T  # noqa: E402
import taste_gates_extra as TX  # noqa: E402
from interview_tail import END_BOARD_SOURCES, end_board_source, quiet_tail_problem  # noqa: E402

REELS = sorted((ROOT / "specs" / "reels").glob("*.json"))
WORKFLOW = ROOT / ".github" / "workflows" / "match-reel.yml"
AUTO = {"status": "ready_for_render"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _segments(spec: dict):
    urls = reel.spec_sources(spec)
    return reel.parse_segments(spec, urls, next(iter(urls)))


def _disk_probes() -> dict[str, dict]:
    probes: dict[str, dict] = {}
    for path in sorted((ROOT / "output").glob("*/reel/*/probe.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        probes[data.get("url")] = data
    return probes


# ═══════════════════════════ ① 章节卡字数 ═══════════════════════════

#: china-open-withdrawals-story-2026 在 ca2d4829a 上的第 2 段——run 36296202661 红在
#: render_title_card，dry-run 当时 exit 0。
CHINA_OPEN_CARD = "至少14人退出女单\n9月30日正赛开打"


def test_章节卡超字数在dry_run就红_和render里是同一个函数(monkeypatch):
    assert len(CHINA_OPEN_CARD) == tc.MAX_CHARS + 1
    spec = {"segments": [{"title_card": CHINA_OPEN_CARD, "seconds": 2.0}]}
    with pytest.raises(reel.ReelError, match="最多 18 个字"):
        reel._normalize_title_card_segments(spec)
    ok = {"segments": [{"title_card": CHINA_OPEN_CARD[:tc.MAX_CHARS], "seconds": 2.0}]}
    reel._normalize_title_card_segments(ok)
    assert ok["segments"][0]["image"].startswith(reel.TITLE_CARD_PREFIX)
    # render 那一刻（build）和 dry-run 走的是同一个 length_problem——写两份必分叉
    calls = []
    real = tc.length_problem
    monkeypatch.setattr(tc, "length_problem", lambda t: calls.append(t) or real(t))
    with pytest.raises(SystemExit):
        tc.build(CHINA_OPEN_CARD)
    with pytest.raises(reel.ReelError):
        reel._normalize_title_card_segments(
            {"segments": [{"title_card": CHINA_OPEN_CARD, "seconds": 2.0}]})
    assert calls == [CHINA_OPEN_CARD, CHINA_OPEN_CARD], calls


def test_全库章节卡都装得下():
    bad = []
    for path in REELS:
        for i, seg in enumerate(_load(path).get("segments") or []):
            if isinstance(seg, dict) and seg.get("title_card") \
                    and tc.length_problem(str(seg["title_card"])):
                bad.append(f"{path.stem} 第 {i + 1} 段")
    assert not bad, bad


# ═══════════════════════════ ② 写过源片末尾：容差 0 ═══════════════════════════

def _seg(start: float, end: float, source: str = ""):
    return reel.parse_segments({"source_url": "u", "segments": [
        {"start": start, "end": end, "narration": "一句。"}]}, {"": "u"}, "")[0]


def test_写过源片末尾_容差是0_hu_kopriva那一趟():
    """hu-kopriva-chengdu-2026-r1（466450041）末段 139.1–143.4，ttv 源片 probe 报 143.56：
    143.4＋0.18＝143.58，超出 0.02s，老容差 +0.05 放行，render 报「分段比要求的短」。"""
    assert reel.segments_over_source_end([_seg(139.1, 143.4)], {"": 143.56})
    # 正好贴住末尾的放行（浮点）
    assert not reel.segments_over_source_end([_seg(139.1, 143.56 - reel.SEG_FADE)],
                                             {"": 143.56})
    # 第一版「减一帧」会误伤的那一档：已推送、落在源片最后一帧里照样渲出来的段
    # （chengdu-ng-kouame 第 38 段 cf73af107、eala-ruse 第 22 段 5f589d63f——spec 和
    # render.json 同一个提交落的），容差 0 放行
    for end, limit in ((122.5, 122.69424), (183.7, 183.902041), (258.0, 258.218333)):
        assert not reel.segments_over_source_end([_seg(end - 4.0, end)], {"": limit}), end
    assert reel.segments_over_source_end([_seg(139.1, 143.4)], {"": 143.57}), "超 0.01s 也红"


def test_写过源片末尾只有两个参数_不要帧率也不要豁免表():
    """容差 0 不需要帧率、也不需要「减一帧之前已发的」豁免表（2026-09-28 修正轮）。"""
    assert list(inspect.signature(reel.segments_over_source_end).parameters) == [
        "segments", "durations"]
    assert not (ROOT / "data" / "legacy_source_end_frame.json").exists()


# ═══════════════════════════ ③ 误差带里的旁白认真 TTS 的账 ═══════════════════════════

#: zverev-deminaur-laver-cup-2026 在 4a2eb32c4 上的第 9 段（146.0–157.9，画面 11.9s）；
#: runner 上真 TTS 实测 12.10s，render 红（run 36257658569）。⚠️ 那一趟没有 Azure 钥匙
#: （render 步 env 两项都空、日志「[配音] 没有 Azure」），12.10s 是 edge-tts 量的。
ZVEREV_SEG9 = ("十比九，轮到德米纳尔的赛点。一个很长的回合，他被兹维列夫左右调动，"
               "一次次滑到角上把球救回来。最后一拍，兹维列夫没打进。")


def _zverev_spec(**extra) -> tuple[dict, list]:
    spec = {"slug": "zz-new-laver-cup-2026", "source_url": "u",
            "segments": [{"start": 146.0, "end": 157.9, "narration": ZVEREV_SEG9}], **extra}
    return spec, _segments(spec)


def _tight(segments) -> list[int]:
    return [i for i, _s, room in reel.narration_estimates(segments)
            if -reel.SPEECH_EST_ERR <= room < reel.SPEECH_EST_ERR]


def test_误差带里的段没量过真TTS_只报不拦_命令现成():
    """2026-09-28 会话决定：没账**只报**（带两行现成命令），不再红——几乎每条新片子都落在
    误差带里，红就是正常路径上多一趟 runner；render 编码之前那道真 TTS 旁白闸兜底。"""
    spec, segs = _zverev_spec()
    tight = _tight(segs)
    assert tight == [0], "zverev-deminaur 第 9 段离线估落在误差带里——这正是那一趟没去量的原因"
    hard, soft, ok = reel.narration_check_findings(spec, segs, tight, record={}, env={})
    assert not hard and len(soft) == 1 and not ok, (hard, soft)
    assert "render --check-narration --spec specs/reels/zz-new-laver-cup-2026.json" in soft[0]
    assert "-f mode=narration -f slug=zz-new-laver-cup-2026" in soft[0]
    assert "不拦" in soft[0] and "render 编码之前" in soft[0]
    # 修正轮 2：runner 那一行排前面、叮嘱别在 main 上跑；不再说「本地能连 edge-tts 就行」
    assert soft[0].index("gh workflow run") < soft[0].index("render --check-narration")
    assert "别在 main 上跑" in soft[0] and "能连 edge-tts" not in soft[0]
    assert "Azure 实测" not in soft[0], "那一趟没有 Azure，12.10s 是 edge-tts 量的"


def test_量过真TTS的账按旁白指纹认():
    spec, segs = _zverev_spec()
    fp = reel.narration_fingerprint(segs[0])
    # 装得下：放行，还要报出来认过账
    hard, soft, ok = reel.narration_check_findings(
        spec, segs, [0], record={fp: {"segment": 1, "spoken": 11.5}}, env={})
    assert not hard and ok, (hard, ok)
    # runner 那一趟（edge-tts）的真数 12.10 > 11.9 + 0.12：量过、装不下，手写的照样红
    hard, soft, ok = reel.narration_check_findings(
        spec, segs, [0], record={fp: {"segment": 1, "spoken": 12.10}}, env={})
    assert len(hard) == 1 and "超出" in hard[0], hard
    # 改一个字，指纹变了，老账不认——按「没量过」只报
    spec2, segs2 = _zverev_spec()
    segs2[0].narration += "！"
    hard, soft, _ok = reel.narration_check_findings(
        spec2, segs2, [0], record={fp: {"segment": 1, "spoken": 11.5}}, env={})
    assert not hard and soft and "没有这几段" in soft[0]


def test_误差带那道闸_没账任何一趟都只报_量过装不下只在手写的render趟红():
    spec, segs = _zverev_spec()
    fp = reel.narration_fingerprint(segs[0])
    over = {fp: {"segment": 1, "spoken": 12.10}}
    for mode in ("render", "narration", "cover"):
        hard, soft, _ok = reel.narration_check_findings(
            spec, segs, [0], record={}, env={"REEL_DRY_RUN_FOR": mode})
        assert not hard and soft, mode
        hard, soft, _ok = reel.narration_check_findings(
            spec, segs, [0], record=over, env={"REEL_DRY_RUN_FOR": mode})
        assert bool(hard) == (mode == "render") and bool(soft) == (mode != "render"), mode
    spec, segs = _zverev_spec(_production=AUTO)
    hard, soft, _ok = reel.narration_check_findings(spec, segs, [0], record=over, env={})
    assert not hard and soft and "自动产的 spec 只报" in soft[0]
    hard, soft, _ok = reel.narration_check_findings(spec, segs, [0], record={}, env={})
    assert not hard and soft and "自动产的 spec 只报" in soft[0]
    assert "legacy" not in inspect.signature(reel.narration_check_findings).parameters


def test_check_narration落账_dry_run读回来(tmp_path, monkeypatch):
    monkeypatch.setattr(reel, "NARRATION_CHECKS_DIR", tmp_path)
    spec, segs = _zverev_spec()
    path = reel.write_narration_record(spec["slug"], segs, {0: 11.4}, voice="v", rate="+6%",
                                       backend="azure")
    assert path.parent == tmp_path and path.name == "zz-new-laver-cup-2026.json"
    record = reel.load_narration_record(spec["slug"])
    assert record[reel.narration_fingerprint(segs[0])]["spoken"] == 11.4
    hard, _soft, ok = reel.narration_check_findings(spec, segs, [0], env={})
    assert not hard and ok


def test_账本量的不是出片那一套_整份不认(tmp_path, monkeypatch):
    """修正轮（2026-09-28）：第一版账上记了后端／音色／语速却从来不比。现在文件头要和出片那一趟
    对得上——**出片那一趟**按出片那台机器算（`render_tts_setup`，修正轮 2），由 `--dry-run` 传进来。"""
    monkeypatch.setattr(reel, "NARRATION_CHECKS_DIR", tmp_path)
    spec, segs = _zverev_spec()
    voice, rate = "zh-CN-YunjianNeural", "+6%"
    edge, azure = ("edge-tts", ["", ""]), ("azure", ["", ""])

    def verdict(**kw):
        return reel.narration_check_findings(spec, segs, [0], env={}, **kw)

    def refused(**kw) -> str:
        """账被整份不认 → 按「没量过」只报（09-28 起不红），返回那一句；认了返回空串。"""
        hard, soft, ok = verdict(**kw)
        assert not hard, hard
        return "" if ok else soft[0]

    reel.write_narration_record(spec["slug"], segs, {0: 11.4}, voice=voice, rate=rate,
                                backend="edge-tts")
    # 没有 Azure 的 runner（run 36257658569 那一种）：出片走 edge-tts，edge-tts 的账就认
    assert not refused(tts=edge, voice=voice, rate=rate)
    # 出片那台有 Azure：edge-tts 的账不认
    why = refused(tts=azure, voice=voice, rate=rate)
    assert "TTS 后端" in why and "'edge-tts'" in why and "整份不认" in why, why
    assert not refused(), "没给 tts 就不比后端（全库扫描走这条：CI 上没有 Azure，不替 runner 判）"
    reel.write_narration_record(spec["slug"], segs, {0: 11.4}, voice="zh-CN-YunxiNeural",
                                rate=rate, backend="azure")
    assert "音色" in refused(tts=azure, voice=voice, rate=rate)
    assert not refused(), "没给音色语速就不比这两样（全库扫描走这条）"
    reel.write_narration_record(spec["slug"], segs, {0: 11.4}, voice=voice, rate="+0%",
                                backend="azure")
    assert "语速" in refused(tts=azure, voice=voice, rate=rate)
    # 栏目基调变了（表改了，或者 spec 换了栏目）：老账不认
    reel.write_narration_record(spec["slug"], segs, {0: 11.4}, voice=voice, rate=rate,
                                backend="azure")
    assert not refused(tts=azure, voice=voice, rate=rate)
    assert "栏目基调" in refused(tts=("azure", ["excited", "1.2"]), voice=voice, rate=rate)
    reel.write_narration_record(spec["slug"], segs, {0: 11.4}, voice=voice, rate=rate,
                                backend="azure", base_style=("excited", "1.2"))
    assert not refused(tts=("azure", ["excited", "1.2"]), voice=voice, rate=rate), \
        "按新基调重量过就认"


def _fake_azure(monkeypatch, *, on: bool) -> None:
    """让 `azure_tts.available()` 答 on：钥匙＋SDK 都在（假模块），或者两把钥匙都没有。"""
    import types  # noqa: PLC0415
    az = reel.azure_tts
    monkeypatch.setenv(az._ENV_BACKEND, "")    # 登记原值：apply_tts_backend 会写它，测完还原
    if on:
        monkeypatch.setenv(az._ENV_KEY, "k")
        monkeypatch.setenv(az._ENV_REGION, "eastus")
        for name in ("azure", "azure.cognitiveservices", "azure.cognitiveservices.speech"):
            monkeypatch.setitem(sys.modules, name, sys.modules.get(name) or types.ModuleType(name))
    else:
        monkeypatch.delenv(az._ENV_KEY, raising=False)
        monkeypatch.delenv(az._ENV_REGION, raising=False)
    assert az.available() is on, "前提没立住"


@pytest.mark.parametrize("azure_on", [False, True])
def test_出片那台机器的TTS和apply_tts_backend是同一个判法(monkeypatch, capsys, azure_on):
    """修正轮 2：dry-run 的期望值必须和出片那一趟**同一个判法**——render 用
    `apply_tts_backend`＋`column_base_style` 定后端和基调，`--check-narration` 把这两个记进账头，
    `--dry-run` 拿 `render_tts_setup` 去比。两边分叉，就是上一版那个死循环。"""
    monkeypatch.setitem(reel.azure_tts.COLUMN_BASE_STYLE, "赛场之上", ("excited", "1.2"))
    for spec in ({"slug": "a", "cover": {"eyebrow": "赛场之上"}},
                 {"slug": "b", "cover": {"eyebrow": "网球有故事"}},
                 {"slug": "c", "cover": {"eyebrow": "赛场之上"}, "tts_backend": "edge",
                  "_tts_backend_why": "x"}):
        _fake_azure(monkeypatch, on=azure_on)
        want = reel.render_tts_setup(spec)
        got = (reel.apply_tts_backend(spec), list(reel.column_base_style(spec)))
        assert want == got, (spec, want, got)
    capsys.readouterr()


def test_runner的dry_run和render挂同一对Azure钥匙():
    """修正轮 2：dry-run 步不挂钥匙，`available()` 在那一步恒答否，和 render 步答的不是一件事。
    SDK 也要在 dry-run 之前装好（「装依赖」那一步，render／cover／narration 三档）。"""
    yml = WORKFLOW.read_text(encoding="utf-8")

    def step(name: str) -> str:
        body = yml[yml.index(f"- name: {name}"):]
        return body[:body.index("\n      - name:")]

    def azure_env(body: str) -> list[str]:
        return sorted(ln.strip() for ln in body.splitlines() if "AZURE_SPEECH_" in ln
                      and "${{" in ln)

    dry, render = step("dry-run — 先把 spec 的形状错拦在编码之前"), step("render — 出成片")
    assert azure_env(render) and azure_env(dry) == azure_env(render), azure_env(dry)
    assert azure_env(step("narration — 只查旁白装不装得下")) == azure_env(render)
    assert yml.index("- name: 装依赖") < yml.index("- name: dry-run — 先把 spec 的形状错拦在编码之前")
    deps = step("装依赖")
    narration_deps = deps[deps.index('= "narration" ]'):deps.index('= "reattest" ]')]
    assert "azure-cognitiveservices-speech" in narration_deps
    assert "pip install -q azure-cognitiveservices-speech" in deps.split('= "probe" ]')[1]


def test_runner三步传同一对音色语速():
    """修正轮 3：账头里的音色／语速是 narration 那一步拿表单值量的、render 那一步拿表单值合成的，
    dry-run 那一步原来不传，`narration_record_mismatch` 就恒拿 CLI 默认值去比——表单上换一把嗓子，
    narration 量的账在 dry-run 眼里永远「音色对不上」。三步只认 `build_match_reel.py render`
    那条命令本身（续行拼起来、不看注释），别被注释里提到的参数名满足。"""
    yml = WORKFLOW.read_text(encoding="utf-8")

    def command(name: str) -> str:
        body = yml[yml.index(f"- name: {name}"):]
        body = body[:body.index("\n      - name:")]
        lines = body.splitlines()
        start = next(i for i, ln in enumerate(lines)
                     if ln.strip().startswith("python tools/build_match_reel.py render"))
        cmd = []
        for ln in lines[start:]:
            cmd.append(ln.strip().rstrip("\\"))
            if not ln.rstrip().endswith("\\"):
                break
        return " ".join(cmd)

    def pair(cmd: str) -> tuple[list[str], list[str]]:
        return (re.findall(r'--voice\s+"([^"]*)"', cmd), re.findall(r'--rate\s+"([^"]*)"', cmd))

    got = {name: pair(command(name)) for name in (
        "dry-run — 先把 spec 的形状错拦在编码之前",
        "narration — 只查旁白装不装得下",
        "render — 出成片")}
    want = (["${{ github.event.inputs.voice }}"], ["${{ github.event.inputs.rate }}"])
    assert all(v == want for v in got.values()), got
    assert "--dry-run" in command("dry-run — 先把 spec 的形状错拦在编码之前")


def test_check_narration落账带上合成用的基调():
    src = inspect.getsource(reel.main)
    check = src[src.index("if args.check_narration:"):]
    check = check[:check.index("if args.dry_run:")]
    assert "base_style = column_base_style(spec)" in check
    assert "*base_style)" in check and "base_style=base_style" in check
    dry = src[src.index("n_hard, n_soft, n_ok = narration_check_findings("):]
    assert "voice=args.voice, rate=args.rate" in dry[:300]
    assert "tts=render_tts_setup(spec)" in dry[:300], "账头要和出片那台机器比（修正轮 2）"


def test_check_narration落账排在任何return之前():
    """装不下（`over`）也要落账——真时长没错，改画面长度不用重量。wp/silence-hard 在这个分支里
    加了自己的 `return 1` 条件，合并时这条钉住落账的位置。"""
    src = inspect.getsource(reel.main)
    check = src[src.index("if args.check_narration:"):]
    check = check[:check.index("if args.dry_run:")]
    # 认的是**代码行**里的 return（注释里也写着「任何一个 `return 1` 之前」，别被它误伤）
    returns = [m.start() for m in re.finditer(r"^\s*return 1\s*$", check, re.M)]
    assert "write_narration_record(" in check and returns
    assert check.index("write_narration_record(") < min(returns)


def test_误差带那道闸接在dry_run里_check_narration落账():
    src = inspect.getsource(reel.main)
    dry = src[src.index("if sure:"):]
    dry = dry[:dry.index("density_hint = ")]
    assert "narration_check_findings(" in dry and "return 1" in dry.split("if n_hard:")[1]
    check = src[src.index("if args.check_narration:"):]
    check = check[:check.index("if args.dry_run:")]
    assert "write_narration_record(" in check
    # render 的旁白闸和认账用同一个容差
    assert "NARRATION_OVER_TOL" in inspect.getsource(reel.narration_overruns)
    # runner 的 mode=narration 把账提交回分支（沙箱连不上 edge-tts）
    yml = WORKFLOW.read_text(encoding="utf-8")
    step = yml[yml.index("- name: narration — 只查旁白装不装得下"):]
    step = step[:step.index("\n      - name:")]
    assert "data/narration_checks/" in step and "push_with_rebase_retry" in step
    assert "exit $rc" in step, "装不下（rc=1）的那一趟也要落账，然后照样红"
    # 修正轮 2：main 上跑的那一趟不提交（main 的提交不过 CI；账和 spec 走同一个 PR）
    guard = step[step.index('REC="data/narration_checks/'):]
    assert '[ "${{ github.ref_name }}" = "main" ]' in guard
    assert guard.index('= "main" ]') < guard.index("git commit"), "判 main 要排在提交之前"
    assert guard.index('= "main" ]') < guard.index("elif [ -f \"$REC\" ]")


#: 复审（修正轮 2）拿来复现死循环的那条：分支上 dry-run 绿、没写 `tts_backend`。
E2E_SLUG = "alcaraz-fritz-laver-cup-2026"


def _e2e_setup(tmp_path, monkeypatch, capsys):
    """把 E2E_SLUG 抄一份、误差带里第一段改一个字（这版旁白没有账），账本目录指到空的 tmp，
    两把 Azure 钥匙都空（run 36257658569 那台 runner）。返回 `run(*flags) -> (rc, stdout)`，
    跑的是真 `main()`；只把合成和量时长打桩（沙箱连不上 TTS）。"""
    src = ROOT / "specs" / "reels" / f"{E2E_SLUG}.json"
    spec = _load(src)
    # This fixture targets TTS accounting. Its publishing hook must independently
    # fit the mandatory date+column prefix, including the widest 12.28 date.
    spec.setdefault("push", {})["summary"] = "阿尔卡拉斯险胜弗里茨"
    assert "tts_backend" not in spec
    tight = _tight(_segments(spec))
    assert tight, "前提：这条有落在误差带里的段"
    seg = spec["segments"][tight[0]]
    assert seg["narration"].endswith("。")
    seg["narration"] = seg["narration"][:-1] + "！"          # 改一个字：这版旁白没量过
    work = tmp_path / "specs"
    work.mkdir()
    spec_path = work / src.name
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    copy = src.with_suffix(".xhs.txt")
    if copy.is_file():
        shutil.copy(copy, spec_path.with_suffix(".xhs.txt"))
    monkeypatch.setattr(reel, "NARRATION_CHECKS_DIR", tmp_path / "checks")
    _fake_azure(monkeypatch, on=False)
    monkeypatch.setenv("REEL_DRY_RUN_FOR", "render")

    # 合成和量时长打桩（沙箱连不上 TTS），其余全走 main() 自己那几行：
    # apply_tts_backend → validate_spec → column_base_style → synthesize → write_narration_record
    based: list[tuple] = []

    def synthesize(segments, outdir, voice, rate, *base):
        based.append(base)
        return [(Path(outdir) / f"voice_{i:02d}.mp3", []) for i in range(len(segments))]

    lengths = {i: s.length for i, s in enumerate(reel.validate_spec(json.loads(
        spec_path.read_text(encoding="utf-8"))))}
    monkeypatch.setattr(reel, "synthesize", synthesize)
    monkeypatch.setattr(reel, "probe_duration",
                        lambda path: lengths[int(Path(path).stem.split("_")[1])] - 0.4)
    monkeypatch.setattr(reel, "_word_splits", lambda *a: [])
    monkeypatch.setattr(reel, "prosody_report", lambda *a: [])
    monkeypatch.setattr(reel, "synth_outro", lambda outdir, v, r: (Path(outdir) / "o.mp3", []))
    monkeypatch.setattr(reel, "outro_length", lambda path: 3.0)

    def run(*flags: str) -> tuple[int, str]:
        capsys.readouterr()
        monkeypatch.setattr(sys, "argv", ["build_match_reel.py", "render", *flags,
                                          "--spec", str(spec_path),
                                          "--outdir", str(tmp_path / "out")])
        rc = reel.main()
        return rc, capsys.readouterr().out

    return run, based


def test_没有Azure的runner_量账之后dry_run认账_一条路走通(tmp_path, monkeypatch, capsys):
    """修正轮 2：把 run 36257658569 那台 runner 的状态（两把钥匙都空）整条回放一遍——
    改一个旁白字 → `--check-narration`（真 `main()`，只把合成和量时长打桩）落账 →
    `--dry-run`（真 `main()`，REEL_DRY_RUN_FOR=render）认这份账、exit 0。
    上一版按 spec 推「azure」，量完报「整份不认」、叫你再去量，量完还是不认。"""
    run, based = _e2e_setup(tmp_path, monkeypatch, capsys)
    rc, out = run("--dry-run")
    assert "没有这几段**现在这版旁白**" in out, "前提：改了字、还没量"
    rc, out = run("--check-narration")
    assert rc == 0, out[-2000:]
    assert based == [("", "")], "没有 Azure：不套栏目基调"
    head = json.loads((tmp_path / "checks" / f"{E2E_SLUG}.json").read_text(encoding="utf-8"))
    assert head["backend"] == "edge-tts" and head["base_style"] == ["", ""]
    rc, out = run("--dry-run")
    assert "整份不认" not in out and "没有这几段**现在这版旁白**" not in out, out[-3000:]
    assert "误差带里这几段已经拿真 TTS 量过" in out
    assert rc == 0, out[-3000:]


@pytest.mark.parametrize("mode", ["render", "cover", "narration"])
def test_新的手写spec误差带里没账_dry_run照样过_只报带命令(tmp_path, monkeypatch, capsys, mode):
    """2026-09-28 会话决定（时效第一：别往正常路径上加一趟 runner）：手写 spec 误差带里的段
    没有真 TTS 的账，**哪一趟的 dry-run 都 exit 0**，印一句带两行补账命令的提示。
    第一版在 mode=render 上 exit 1——每条新片子都得先多拨一趟 mode=narration。"""
    run, _based = _e2e_setup(tmp_path, monkeypatch, capsys)
    monkeypatch.setenv("REEL_DRY_RUN_FOR", mode)
    assert not (tmp_path / "checks").exists(), "前提：一份账都没有"
    rc, out = run("--dry-run")
    assert "没有这几段**现在这版旁白**" in out, out[-3000:]
    notice = out[out.index("[估旁白] 只报（不拦）"):]
    assert f"-f mode=narration -f slug={E2E_SLUG}" in notice
    assert "render --check-narration --spec" in notice
    assert "[估旁白] **过不去**" not in out
    assert rc == 0, out[-3000:]


def test_旁白没账的冻结表跟着那道闸一起删了():
    """没账不红了，冻结表冻的那道闸就不存在了：文件、读它的函数都不许再回来。"""
    assert not (ROOT / "data" / "legacy_narration_unchecked.json").exists()
    assert not hasattr(reel, "legacy_narration_unchecked")
    assert not hasattr(reel, "LEGACY_NARRATION_UNCHECKED_PATH")


# ═══════════════════════════ ④ alphamerge：蒙版缩成裁框尺寸 ═══════════════════════════

@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="没有 ffmpeg")
def test_蒙版和裁框差一行也能alphamerge(tmp_path):
    """safiullin-bu-hangzhou-2026-qf：蒙版 424×108、裁框 424×109，ffmpeg 当场拒掉
    （run 36323549463）。真跑一遍 ffmpeg：缩过的能过，老写法（不缩）照样拒——两头都钉。"""
    mask = tmp_path / "mask.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=white:s=424x108:d=0.2:r=25", "-pix_fmt", "gray",
                    "-c:v", "ffv1", str(mask)], check=True)
    x0, y0, x1, y1 = 98, 920, 522, 1029                   # 424×109
    bw, sh = 566, 146

    def run(patch: str) -> subprocess.CompletedProcess:
        graph = "[0:v]split=2[m][wb];" + patch + "[m][b]overlay=0:800[v]"
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "testsrc=s=1920x1080:d=0.2:r=25", "-filter_complex", graph, "-map", "[v]",
             "-frames:v", "3", "-f", "null", "-"], capture_output=True, text=True)

    good = run(reel.masked_board_patch(x0, y0, x1, y1, str(mask), bw, sh))
    assert good.returncode == 0, good.stderr[-600:]
    old = (f"[wb]crop={x1 - x0}:{y1 - y0}:{x0}:{y0},format=rgb24[bc];"
           f"movie='{reel._escape(mask)}':dec_threads=1,format=gray[mask];"
           f"[bc][mask]alphamerge,scale={bw}:{sh}:flags=lanczos[b];")
    assert run(old).returncode != 0, "老写法居然过了——那这条判据就没钉住那次失败"


def test_两处回贴都走同一个蒙版滤镜():
    src = inspect.getsource(reel)
    assert src.count("[bc][mask]alphamerge") == 1, "蒙版滤镜只许有 masked_board_patch 一份"
    assert src.count("masked_board_patch(x0, y0, x1, y1, seg.score_inset_mask, bw, sh)") == 2


# ═══════════════════════════ ⑤ 采访：已知带片尾板的源 ═══════════════════════════

def _interview(**extra) -> dict:
    return {"slug": "zz-new-laver-cup-interview", "start": 0.0, "end": 286.7,
            "url": "https://www.youtube.com/watch?v=zz",
            "source_verification": {"source": "Laver Cup"}, **extra}


#: alcaraz-fritz-laver-cup-2026-interview 第一版：end 286.7，最后一句「Carlos Alcaraz.」
#: 之后 283.7 起是拉沃尔杯片尾板（1b0b65ee5 的 `_end_why`）。
SPANS = [(270.0, 271.0, "and"), (282.9, 283.5, "Alcaraz.")]


def test_已知带片尾板的源_话音后空太久_手写的红():
    red, note = quiet_tail_problem(_interview(), SPANS, auto=False, legacy=frozenset())
    assert red and not note and "Laver Cup" in red and "_end_why" in red, (red, note)
    tv = _interview(source_verification={}, url="https://www.tennistv.com/videos/1/x")
    assert end_board_source(tv) == "Tennis TV"
    assert quiet_tail_problem(tv, SPANS, auto=False, legacy=frozenset())[0]
    # 认领、自动、冻着的、别家源：只报
    for spec, kw in ((_interview(_end_why="看过：那三秒是全场起立"), {"auto": False}),
                     (_interview(_end_board_ok="板上有他要的话"), {"auto": False}),
                     (_interview(), {"auto": True}),
                     (_interview(source_verification={"source": "US Open"}), {"auto": False})):
        red, _note = quiet_tail_problem(spec, SPANS, legacy=frozenset(), **kw)
        assert red is None, spec
    red, note = quiet_tail_problem(_interview(), SPANS, auto=False,
                                   legacy=frozenset({"zz-new-laver-cup-interview"}))
    assert red is None and "legacy" in note
    # 话音一落就收的（≤1.5 秒）不报
    assert quiet_tail_problem(_interview(end=284.5), SPANS, auto=False,
                              legacy=frozenset()) == (None, None)
    assert set(END_BOARD_SOURCES) == {"Laver Cup", "Tennis TV"}


def _caption_cache(root: Path, slug: str, words: str, start_ms: int) -> None:
    """合成一份 `cap_asr.json3`（每个词一个事件，带词长）。"""
    (root / slug).mkdir(parents=True)
    events = [{"tStartMs": start_ms + 400 * i, "dDurationMs": 300, "segs": [{"utf8": w}]}
              for i, w in enumerate(words.split())]
    (root / slug / "cap_asr.json3").write_text(json.dumps({"events": events}), encoding="utf-8")


def test_采访预检把片尾板这一条接成红(tmp_path, monkeypatch):
    """走 `interview_preflight.subtitle_findings` 真实那条路（字幕缓存 → `quiet_tail_problem`
    → 红／提示），不是查源码里有没有 `problems.append`（修正轮：那样写，把红改成提示照样绿）。"""
    import interview_preflight as ip  # noqa: PLC0415
    slug = "zz-new-laver-cup-2026-interview"
    _caption_cache(tmp_path, slug, "It was a great match today and I am really happy "
                   "with the level I played Thank you all", 270000)
    monkeypatch.setattr(ip, "OUTPUT", tmp_path)
    spec = {"slug": slug, "url": "https://www.youtube.com/watch?v=zzzzzzzzzzz",
            "start": 269.5, "end": 286.7, "asr_model": "large-v3",
            "source_verification": {"source": "Laver Cup"}}
    problems, notes = ip.subtitle_findings(spec)
    assert [p for p in problems if p.startswith("片尾板：")], (problems, notes)
    # 自动链写的、没人核过的（来路那两条的形状）：只报
    problems, notes = ip.subtitle_findings(dict(spec, transcript_verification="auto_pending"))
    assert not [p for p in problems if "片尾板" in p], problems
    assert any("自动 spec 只报" in n for n in notes), notes
    # 话音一落就收（≤1.5 秒）：红和提示都没有
    problems, notes = ip.subtitle_findings(dict(spec, end=277.9))
    assert not [p for p in problems + notes if "片尾板" in p or "`end` 还要再往后" in p]


def _interview_specs() -> dict[str, dict]:
    out = {}
    for path in sorted((ROOT / "specs" / "interviews").glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        spec = _load(path)
        out[str(spec.get("slug") or path.stem)] = spec
    return out


def _tail_verdict(spec: dict, legacy: frozenset):
    import interview_preflight as ip  # noqa: PLC0415
    from interview_tail import cache_word_spans  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as td:
        if not ip._materialize_captions(str(spec.get("slug")), Path(td)):
            return None
        return quiet_tail_problem(spec, cache_word_spans(Path(td), spec), legacy=legacy)


def test_片尾板那条的豁免表只许减_全库零误报():
    from interview_spec_gates import legacy  # noqa: PLC0415
    frozen = legacy("end_board_quiet_tail")
    assert frozen, "豁免表读不到"
    specs = _interview_specs()
    if not (ROOT / "output" / "interviews").is_dir():
        pytest.skip("这个检出里没有 output/interviews（字幕缓存）")
    stale = [s for s in frozen if s not in specs
             or not ((_tail_verdict(specs[s], frozenset()) or (None,))[0])]
    assert not stale, f"这些已经不红了，从 legacy_interview_gates.json 删掉：{stale}"
    assert len(frozen) <= 2
    bad = [slug for slug, spec in specs.items()
           if ((_tail_verdict(spec, frozen) or (None,))[0])]
    assert not bad, bad


# ═══════════════════════════ ⑥ 钩子：送别人进决赛不算赛果 ═══════════════════════════

def test_送别人进决赛不算交代赛果():
    """账号所有者 2026-09-25 看 bucsa-noskova「首盘5比2被追平／直落两盘送捷克进决赛」：
    「封面钩子文案没交代赛果啊」（872c6dab6）。"""
    assert not T.has_match_result("直落两盘送捷克进决赛")
    assert not T.has_match_result("77分钟送德国晋级")
    assert T.has_match_result("2比0胜布克沙进决赛"), "改好的那版"
    for line in ("这次送走卫冕冠军", "卫冕冠军被她送走", "首轮送走2024冠军",
                 "淘汰头号种子送中国队进决赛", "直落两盘进半决赛", "直落两盘"):
        assert T.has_match_result(line), line
    # 「送」后面不是被送进去的那一方——第一版把这些本来说了结果的行一起拿掉了（修正轮）
    for line in ("送出8记ACE挺进决赛", "连送三个双误还是进了决赛", "连送双误还是进了决赛",
                 "送别恩师后首进决赛", "靠对手送分挺进决赛", "送给对手8个破发点仍挺进决赛"):
        assert T.has_match_result(line), line
    assert not T.has_match_result("直落两盘送捷克共和国队进决赛")
    spec = _load(ROOT / "specs" / "reels" / "bucsa-noskova-bjk-cup-2026-sf.json")
    spec["cover"] = dict(spec["cover"], hook="首盘5比2被追平\n直落两盘送捷克进决赛")
    spec["cover"].pop("_hook_shape_why", None)
    assert T.hook_result_problem(spec, legacy={}), "被否的那版必须红"
    spec["cover"]["hook"] = "首盘5比2被追平\n2比0胜布克沙进决赛"
    assert T.hook_result_problem(spec, legacy={}) is None


def test_钩子里的N号种子只报不拦_那句话只有会话转述():
    """账号所有者 09-26 那句（「封面别说淘汰八号种子，说挺进 8 强」）只以会话转述的形式留在
    61e62b8a5 的提交说明里——同一段里另一句抽帧的话，CLAUDE.md 记的原话和提交说明的
    转述不一样，说明这一段是转述。按 09-27 他选的口径，转述出来的规则只进清单自查，
    不做闸（`tennis-owner-taste`「〔推断·只自查，永不做成闸〕」）。钩子本身照结果闸判。"""
    spec = {"slug": "zz-seed", "cover": {"eyebrow": "赛场之上",
                                         "hook": "只差一分被拖进决胜盘\n他还是淘汰了八号种子"}}
    assert T.hook_result_problem(spec, legacy={}) is None
    assert T.hook_jargon_problem(spec, legacy={}) is None
    assert TX.hook_identity_note(spec), "只报的那条还在"


# ═══════════════════════════ ⑦ 多源认领要带宽高帧率 ═══════════════════════════

def _two_sources(claim) -> dict:
    return {"slug": "zz-new-withdrawal-story", "sources": {"main": "M", "xvid": "X"},
            "segments": [{"source": "main", "start": 1.0, "end": 5.0, "narration": "一句。"},
                         {"source": "xvid", "start": 1.0, "end": 5.0, "narration": "又一句。"}],
            "_no_probe_why": claim}


MAIN_PROBE = {"M": {"url": "M", "width": 1920, "height": 1080, "fps": "25/1", "fps_value": 25.0}}


def test_多源认领不带宽高帧率_手写的红_带了几何照跑():
    """sinner-beijing-withdrawal-2026（97ebe27a2）的 xvid 480×852 没 probe：认领一句话
    就把几何预演整层关掉，render 下完源片才红（run 36133328467）。"""
    hard, _soft = ps.coverage_findings(_two_sources({"xvid": "X 上的视频，probe 不了"}),
                                       MAIN_PROBE, legacy={}, env={})
    assert len(hard) == 1 and "没写宽高帧率" in hard[0], hard
    geo = {"xvid": {"why": "X 上的视频，probe 不了", "width": 480, "height": 852, "fps": "30/1"}}
    spec = _two_sources(geo)
    hard, soft = ps.coverage_findings(spec, MAIN_PROBE, legacy={}, env={})
    assert not hard and any("已认领" in s for s in soft)
    g_hard, _ = ps.geometry_findings(spec, MAIN_PROBE, reel.check_sources_match, reel.ReelError)
    assert g_hard and "check_sources_match" in g_hard[0], "几何预演要拿认领的宽高照跑"
    same = _two_sources({"xvid": dict(geo["xvid"], width=1920, height=1080, fps="25/1")})
    assert ps.geometry_findings(same, MAIN_PROBE, reel.check_sources_match, reel.ReelError) \
        == ([], [])
    # 自动 spec、单源：只报／不要求
    auto = dict(_two_sources({"xvid": "probe 不了"}), _production=AUTO)
    assert ps.coverage_findings(auto, MAIN_PROBE, legacy={}, env={})[0] == []
    single = {"slug": "zz-one", "source_url": "Y", "_no_probe_why": {"": "probe 不了"},
              "segments": [{"start": 1.0, "end": 5.0, "narration": "一句。"}]}
    assert ps.coverage_findings(single, {}, legacy={}, env={})[0] == []
    # 写坏的几何不算写了
    for bad in ({"why": "x", "width": "宽", "height": 852, "fps": "30/1"},
                {"why": "x", "width": 480, "height": 852}):
        assert ps.claimed_geometry(bad) is None


def test_每条源都没probe_全靠认领时几何预演照跑(monkeypatch, capsys):
    """修正轮（2026-09-28）：`probe_dry_run` 在「一份 probe.json 都没认领上」那一步早退，
    几何预演排在它后面——多源全都没 probe、全靠带宽高帧率的认领时，认领的数一次都没用上。"""
    main = {"why": "私有录屏", "width": 1920, "height": 1080, "fps": "25/1"}
    xvid = {"why": "X 上的视频，probe 不了", "width": 480, "height": 852, "fps": "30/1"}
    spec = _two_sources({"main": main, "xvid": xvid})
    monkeypatch.setattr(reel, "probes_for_spec", lambda _spec: ({}, ["main", "xvid"]))
    assert reel.probe_dry_run(spec, _segments(spec)) is True
    out = capsys.readouterr().out
    assert "一份 probe.json 都没认领上" in out and "check_sources_match" in out, out
    same = _two_sources({"main": main, "xvid": dict(xvid, width=1920, height=1080, fps="25/1")})
    assert reel.probe_dry_run(same, _segments(same)) is False, capsys.readouterr().out


# ═══════════════════════════ ⑧ 开着回贴、probe 没量板 ═══════════════════════════

def test_开着回贴而probe没量板_手写的红_命令带url和框():
    spec = {"slug": "zz-new-singapore-2026-r2", "topbar": {"line1": "2026 WTA500 新加坡 1/8决赛"},
            "cover": {"eyebrow": "赛场之上"}, "scorebox": [90, 870, 550, 980],
            "source_url": "https://www.youtube.com/watch?v=zz",
            "segments": [{"start": 5.0, "end": 9.0, "score_inset": True, "narration": "一句。"}]}
    segs = _segments(spec)
    probe = {"url": spec["source_url"], "duration": 600.0, "clip_from": 120.0}
    hard, _soft = pb.board_findings(spec, segs, {spec["source_url"]: probe},
                                    {"": spec["source_url"]}, profile="wta", tail=reel.SEG_FADE)
    assert len(hard) == 1, hard
    assert ("mode=probe -f slug=zz-new-singapore-2026-r2 -f url=https://www.youtube.com/watch?v=zz"
            in hard[0] and "-f clip_from=120.0" in hard[0]
            and "-f scorebox=90,870,550,980" in hard[0]), hard[0]


def test_没量板的豁免表只许减():
    legacy = pb.legacy_board_unprobed()
    assert legacy, "豁免表读不到"
    specs = {str(_load(p).get("slug") or p.stem): _load(p) for p in REELS}
    probes = _disk_probes()
    stale = []
    for slug, keys in legacy.items():
        spec = specs.get(slug)
        if spec is None or (spec.get("_production") or {}).get("status") == "ready_for_render":
            stale.append(f"{slug}（spec 没了／是自动 spec）")
            continue
        urls = reel.spec_sources(spec)
        segs = _segments(spec)
        for key in keys:
            if key not in urls or not any(s.source == key and s.score_inset for s in segs):
                stale.append(f"{slug}/{key}（源没了或回贴关了）")
            elif probes and (probes.get(urls[key]) or {}).get("board"):
                stale.append(f"{slug}/{key}（已经重跑过 probe，有 board 了）")
    assert not stale, "从 data/legacy_board_unprobed.json 删掉：" + "、".join(stale)
    assert len(legacy) <= 78 and sum(map(len, legacy.values())) <= 84


def test_豁免表外的手写spec开着回贴的源都量过板():
    probes = _disk_probes()
    if not probes:
        pytest.skip("这个检出里没有 output/*/reel/*/probe.json")
    bad = []
    for path in REELS:
        spec = _load(path)
        try:
            segs = _segments(spec)
            profile = reel.scoreboard_profile(spec, segs)
        except reel.ReelError:
            continue
        urls = reel.spec_sources(spec)
        hard, _soft = pb.board_findings(spec, segs, {u: probes[u] for u in urls.values()
                                                     if u in probes},
                                        urls, profile=profile, tail=reel.SEG_FADE)
        bad += [f"{path.stem}: {h.strip()[:90]}" for h in hard if "早于逐帧量板" in h]
    assert not bad, "\n".join(bad)


def test_全库写过源片末尾零误报():
    probes = _disk_probes()
    if not probes:
        pytest.skip("这个检出里没有 output/*/reel/*/probe.json")
    bad = []
    for path in REELS:
        spec = _load(path)
        try:
            segs = _segments(spec)
        except reel.ReelError:
            continue
        urls = reel.spec_sources(spec)
        over = reel.segments_over_source_end(
            segs,
            {s.source: (float(p["duration"]) if (p := probes.get(urls.get(s.source, "")))
                        and p.get("duration") else None) for s in segs})
        bad += [f"{path.stem}: {line.strip()[:80]}" for line in over]
    assert not bad, "\n".join(bad)


def test_自动spec和手写spec的区分用的是同一个口径():
    """八道闸里「自动 spec」全认 `_production.status == ready_for_render`（采访线认
    `taste_gates.interview_is_auto`），别哪一道自己发明一个。"""
    assert re.search(r'_production.*ready_for_render', inspect.getsource(
        reel.narration_check_findings))
    assert "ready_for_render" in inspect.getsource(pb.board_findings)
    assert "is_auto(spec)" in inspect.getsource(ps.coverage_findings)
