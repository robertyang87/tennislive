"""vibetennis 栏目：登记、spec 合同、标题规则、发布门禁。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "vibetennis"))
sys.path.insert(0, str(ROOT / "tools"))

import importlib  # noqa: E402

# 仓库内的模块（tools/vibetennis/），不是第三方包——按名字现取，免得被当成依赖
common = importlib.import_module("common")
publish_gate = importlib.import_module("publish_gate")

SPECS = sorted((ROOT / "specs/vibetennis").glob("*.json"))


def test_栏目登记在栏目文档里():
    doc = (ROOT / "docs/columns.md").read_text(encoding="utf-8")
    assert "| **vibetennis** |" in doc, "栏目表里没有 vibetennis 那一行"
    assert (ROOT / "docs/vibetennis.md").is_file()
    assert (ROOT / "skills/vibetennis-production/SKILL.md").is_file()


def test_至少有一条spec_而且每条都自洽():
    assert SPECS, "specs/vibetennis/ 是空的"
    for path in SPECS:
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert common.spec_problems(spec, path.stem) == [], path.name
        assert path.with_suffix(".xhs.txt").is_file(), f"{path.name} 缺文案"
        cover = spec["cover"]
        src = cover["script"] if cover.get("layout") == "custom" else cover["portrait"]["image"]
        assert (ROOT / src).is_file(), f"{path.name} 的封面来源 {src} 不在"


def test_spec合同会拦住竖屏和空出处():
    spec = json.loads(SPECS[0].read_text(encoding="utf-8"))
    bad = json.loads(json.dumps(spec))
    bad["film"]["canvas"] = [1080, 1440]
    bad["editorial"]["sources"] = []
    problems = common.spec_problems(bad, spec["slug"])
    assert any("16:9" in p for p in problems)
    assert any("出处" in p for p in problems)


def test_标题规则认得这个栏目():
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.render.copy_title import (  # noqa: PLC0415
        copy_title, make_copy_title, validate_copy_title)

    # 所有者 2026-10-31：vibetennis 按集数命名 EPNN.vibetennis|主题，不写日期
    assert make_copy_title("10.30", "vibetennis", "现场更快", episode=1) == "EP01.vibetennis|现场更快"
    assert make_copy_title("10.31", "vibetennis", "上旋下坠",
                           slug="vibetennis-topspin-magnus-2026") == "EP03.vibetennis|上旋下坠"
    assert copy_title("EP02.vibetennis｜电子司线") == "EP02.vibetennis|电子司线"
    assert validate_copy_title("EP02.vibetennis|电子司线", require_prefix=True)
    with pytest.raises(SystemExit):
        make_copy_title("10.30", "vibetennis", "网球为什么现场更快", episode=1)   # 超 20 字要报错，不许截断
    with pytest.raises(SystemExit):
        validate_copy_title("10.30vibetennis|现场更快", require_prefix=True)   # 旧的日期格式不再认
    with pytest.raises(SystemExit):
        make_copy_title("10.30", "vibetennis", "现场更快", slug="vibetennis-not-registered")
    # 别的栏目照旧是日期
    assert make_copy_title("10.30", "赛场之上", "郑钦文胜").startswith("10.30赛场之上|")


def test_集数表连续且每条spec都登记了():
    table = json.loads((ROOT / "data/vibetennis_episodes.json").read_text(encoding="utf-8"))
    episodes = table["episodes"]
    assert sorted(episodes.values()) == list(range(1, len(episodes) + 1))
    # 语言版（<slug>-en）不单独登记，跟原版同一集
    assert {json.loads(p.read_text(encoding="utf-8")).get("variant_of") or p.stem for p in SPECS} <= set(episodes)


def test_英文版和原版同一集_同一个Release():
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.render.copy_title import make_copy_title, variant_base  # noqa: PLC0415

    assert variant_base("vibetennis-live-faster-2026-en") == "vibetennis-live-faster-2026"
    assert variant_base("vibetennis-live-faster-2026") == "vibetennis-live-faster-2026"
    assert make_copy_title("", "vibetennis", "Live",
                           slug="vibetennis-live-faster-2026-en") == "EP01.vibetennis|Live"
    with pytest.raises(SystemExit):
        make_copy_title("", "vibetennis", "Live", slug="vibetennis-not-registered-en")
    # 取第一条**原版** spec（按文件名排，语言版 `<slug>-en` 可能排在原版前面）
    spec = next(x for x in (json.loads(p.read_text(encoding="utf-8")) for p in SPECS) if not x.get("variant_of"))
    en = json.loads(json.dumps(spec))
    en.update(slug=spec["slug"] + "-en", lang="en", variant_of=spec["slug"])
    assert common.spec_problems(en, en["slug"]) == []
    assert common.release_slug(en) == spec["slug"] and common.release_slug(spec) == spec["slug"]
    bad = dict(en, variant_of="something-else")
    assert any("variant_of" in p for p in common.spec_problems(bad, bad["slug"]))
    assert any("lang" in p for p in common.spec_problems(dict(spec, lang="fr"), spec["slug"]))


def test_每条spec的发布标题和正文都过得了推送那几道闸():
    push_reel = importlib.import_module("push_reel")

    for path in SPECS:
        out = Path("output/2026-10-30/vibetennis") / path.stem
        column, title, body = push_reel.prepare_copy(path.with_suffix(".xhs.txt"), out)
        assert column == "vibetennis"
        assert title.startswith("EP") and ".vibetennis|" in title and len(title) <= 20
        assert body.strip()
        # 所有者 2026-10-31：这一栏必带 #vibe知识大赏，不带两个中国赛季活动 tag
        assert "#vibe知识大赏" in body and "#网球时差" in body
        assert "#网球中国赛季来了" not in body and "#网球时间到" not in body


def test_门禁只认这一栏的路径形状():
    assert common.RENDER_JSON.match("output/2026-10-30/vibetennis/x-y/render.json")
    assert not common.RENDER_JSON.match("output/2026-10-30/reel/x-y/render.json")


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_没有质检凭证就不发(tmp_path):
    repo = _repo(tmp_path)
    slug = "demo-ep"
    out = repo / "output/2026-10-30/vibetennis" / slug
    out.mkdir(parents=True)
    (out / "render.json").write_text("{}", encoding="utf-8")
    (repo / "specs/vibetennis").mkdir(parents=True)
    (repo / f"specs/vibetennis/{slug}.json").write_text('{"push":{"auto":true}}', encoding="utf-8")
    (repo / f"specs/vibetennis/{slug}.xhs.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    with pytest.raises(publish_gate.Skip, match="qc_attestation"):
        publish_gate.wants_auto_push(repo, slug, out.relative_to(repo))


def test_一趟两条一条都不发(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_gate, "wants_auto_push", lambda *a: None)
    with pytest.raises(SystemExit):
        publish_gate.pick(["output/2026-10-30/vibetennis/a/render.json",
                           "output/2026-10-30/vibetennis/b/render.json"], tmp_path)


def _cover_revision_repo(tmp_path: Path, *, parent="a" * 32, extra_rows=()):
    """一条已推过、准备只换封面重推的最小仓库。"""
    import hashlib
    repo = _repo(tmp_path)
    slug = "demo-ep"
    out = repo / "output/2026-10-30/vibetennis" / slug
    out.mkdir(parents=True)
    sha = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
    film = "f" * 64
    (out / "poster.jpg").write_bytes(b"new-cover")
    archived = {"at": "2026-10-30T14:38:29Z", "run": "https://x/runs/1",
                "pushplus_receipt": "a" * 32}
    raw = (json.dumps(archived) + "\n").encode()
    (out / "pushed_original.json").write_bytes(raw)
    rows = [{"key": f"pushplus:vibetennis:{slug}:{film}", "fingerprint": film, "status": "sent",
             **archived}, *extra_rows]
    led = repo / "data/vibetennis_publish_ledger" / f"{slug}.json"
    led.parent.mkdir(parents=True)
    led.write_text(json.dumps({"slug": slug, "channel": "pushplus", "attempts": rows}), encoding="utf-8")
    manifest = {"version": 1, "kind": "cover-correction", "slug": slug, "revision_id": "cover-v2",
                "film_sha256": film, "poster_sha256": sha(b"new-cover"), "parent_receipt": parent,
                "previous_pushed": {"path": "pushed_original.json", "sha256": sha(raw)}}
    (out / "publication_revision.json").write_text(json.dumps(manifest), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    return repo, slug, out.relative_to(repo), film


def test_只换封面的修订单用海报指纹记账(tmp_path):
    repo, slug, out, film = _cover_revision_repo(tmp_path)
    fp = publish_gate.revision_fingerprint(repo, slug, out, film)
    assert fp.startswith("cover-revision:") and fp != film


def test_修订单的父回执不是最近一次已发就不发(tmp_path):
    repo, slug, out, film = _cover_revision_repo(tmp_path, parent="b" * 32)
    with pytest.raises(publish_gate.Skip, match="parent_receipt|归档回执"):
        publish_gate.revision_fingerprint(repo, slug, out, film)


def test_同一张封面发过了就不再发(tmp_path):
    import hashlib
    poster_fp = "cover-revision:" + hashlib.sha256(b"new-cover").hexdigest()
    later = {"key": f"pushplus:vibetennis:demo-ep:{poster_fp}", "fingerprint": poster_fp,
             "status": "sent", "at": "2026-10-30T16:00:00Z", "run": "https://x/runs/2",
             "pushplus_receipt": "c" * 32}
    repo, slug, out, film = _cover_revision_repo(tmp_path, extra_rows=[later])
    with pytest.raises(publish_gate.Skip, match="parent_receipt"):
        publish_gate.revision_fingerprint(repo, slug, out, film)


def test_修订单不许换成片(tmp_path):
    repo, slug, out, _ = _cover_revision_repo(tmp_path)
    with pytest.raises(publish_gate.Skip, match="成片"):
        publish_gate.revision_fingerprint(repo, slug, out, "e" * 64)


def test_推送按钮写横版_别的栏目不变():
    push = importlib.import_module("push")
    from tennislive.render import push_style as ps
    html = f'<p>x</p><a href="u">{ps.VIDEO_BUTTON_TEXT}</a>'
    out = push.landscape_button(html)
    assert "▶ 打开横版成片" in out and "竖版" not in out
    assert ps.VIDEO_BUTTON_TEXT == "▶ 打开竖版成片", "共用模板（其他栏目）的按钮文字不该被改"
    with pytest.raises(SystemExit):
        push.landscape_button("<p>没有按钮</p>")
    en = push.landscape_button(html, "en")
    assert "▶ Watch the video" in en and "竖版" not in en


# ---- 2026-11-03 产线 review 补的三道：配音检查、渲前审片包、背景声铺满 ----
voice_check = importlib.import_module("voice_check")


def test_配音检查的老集豁免只许减():
    assert voice_check.LEGACY <= {"vibetennis-federer-54-percent-2026", "vibetennis-court-speed-2026"}
    qc = importlib.import_module("qc")
    assert qc.VOICE_NO_PROJECT <= {"vibetennis-topspin-magnus-2026"}


def _fake_episode(tmp_path: Path, name: str, lines: list[tuple[str, float, float, str]]) -> Path:
    ep = tmp_path / name
    (ep / "voice").mkdir(parents=True)
    for fid, _, end, _ in lines:
        (ep / "voice" / f"{fid}.mp3").write_bytes(b"\0" * 2000)
        (ep / "voice" / f"{fid}.json").write_text(json.dumps(
            [{"type": "WordBoundary", "off": 0.1, "dur": end - 0.1, "text": "x"}]), encoding="utf-8")
    (ep / "narration.json").write_text(json.dumps({"rate": "+18%", "lines": [
        {"at": at, "text": t, "tts": t, "file": fid} for fid, at, _, t in lines]}, ensure_ascii=False), encoding="utf-8")
    return ep


def test_配音重叠要拦_尾巴静音不算(tmp_path):
    # a 念到 0+2.0=2.0s；b 在 1.9s 开口（差 0.1 在容差内）不拦，c 在 b 念完（1.9+2.0）前 0.5s 开口要拦
    ep = _fake_episode(tmp_path, "vibetennis-new-2026",
                       [("a", 0.0, 2.0, "红土。"), ("b", 1.9, 2.0, "草地。"), ("c", 3.4, 1.0, "硬地。")])
    bad, _ = voice_check.problems(ep)
    assert len(bad) == 1 and bad[0].startswith("c：b 还没念完"), bad


def test_多音字没认领要拦_认领了放行(tmp_path):
    ep = _fake_episode(tmp_path, "vibetennis-new-2026", [("a", 0.0, 2.0, "球贴着地面往前窜。")])
    bad, _ = voice_check.problems(ep)
    assert any("多音字「着」" in b for b in bad), bad
    nar = json.loads((ep / "narration.json").read_text(encoding="utf-8"))
    nar["lines"][0]["poly_ok"] = {"着": "实测成片听过读 zhe"}
    (ep / "narration.json").write_text(json.dumps(nar, ensure_ascii=False), encoding="utf-8")
    assert voice_check.problems(ep)[0] == []


def test_渲前审片包每节每句字幕都有帧():
    sys.path.insert(0, str(ROOT / "tools" / "vibetennis" / "engine"))
    review_pack = importlib.import_module("review_pack")
    tl = json.loads((ROOT / "tools/vibetennis/episodes/vibetennis-court-speed-2026/r3d/timeline.json").read_text())
    labels = {lab for _, lab in review_pack.pick_times(tl, None)}
    for sec in tl["sections"]:
        assert any(lab.split("·")[0] == sec["name"] for lab in labels), sec["name"]
        for key in sec.get("lines") or {}:
            assert f"{sec['name']}·{key}" in labels, (sec["name"], key)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode, reason="没装 ffmpeg")
def test_背景声断了要拦(tmp_path):
    qc = importlib.import_module("qc")
    wav = tmp_path / "bed.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=10,volume=4", "-f", "lavfi",
                    "-i", "sine=f=440:d=10,volume=0.05", "-filter_complex", "[0][1]concat=n=2:v=0:a=1", str(wav)],
                   check=True)
    thin = qc.quiet_stretches(wav, 0, 20)
    assert thin and thin[0][1] >= 19, thin          # 后 10 秒只剩零星声，要报
    assert qc.quiet_stretches(wav, 0, 9) == []      # 前 10 秒正常，不许误报


# ---------- 光晕全局标准（所有者 2026-11-05「所有动效里的光晕都很亮，你要统一复查下，同时设定好一个全局标准」）----------
# 每集 scene.js 要定义 GLOW 常量并用它管泛光、叠加发光和自发光；数值上限见 docs/vibetennis.md「光晕标准」。
# 定标准之前已发的六集挂在这里，只许减不许加。
GLOW_LEGACY = {"vibetennis-live-faster-2026", "vibetennis-electronic-line-calling-2026",   # EP03 的工程没留下 scene.js，不在表里
               "vibetennis-federer-54-percent-2026", "vibetennis-court-speed-2026", "vibetennis-serve-nash-2026"}
GLOW_CAP = {"bloom_strength": 0.25, "bloom_radius": 0.35, "bloom_threshold": 0.92, "k": 0.5, "emissive": 0.35, "emissiveWhite": 0.15}


def _glow_problems(js: str) -> list[str]:
    import re
    bad = []
    m = re.search(r"const GLOW=\{bloom:\[([\d.]+),([\d.]+),([\d.]+)\],\s*k:([\d.]+),\s*emissive:([\d.]+),\s*emissiveWhite:([\d.]+)\}", js)
    if not m:
        return ["没有 `const GLOW={bloom:[strength,radius,threshold], k:…, emissive:…, emissiveWhite:…}`"]
    st, ra, th, k, em, emw = map(float, m.groups())
    if st > GLOW_CAP["bloom_strength"]: bad.append(f"泛光 strength {st} > {GLOW_CAP['bloom_strength']}")
    if ra > GLOW_CAP["bloom_radius"]: bad.append(f"泛光 radius {ra} > {GLOW_CAP['bloom_radius']}")
    if th < GLOW_CAP["bloom_threshold"]: bad.append(f"泛光 threshold {th} < {GLOW_CAP['bloom_threshold']}")
    if k > GLOW_CAP["k"]: bad.append(f"叠加发光系数 k {k} > {GLOW_CAP['k']}")
    if em > GLOW_CAP["emissive"]: bad.append(f"自发光上限 {em} > {GLOW_CAP['emissive']}")
    if emw > GLOW_CAP["emissiveWhite"]: bad.append(f"白色件自发光上限 {emw} > {GLOW_CAP['emissiveWhite']}")
    if "UnrealBloomPass(" in js and not re.search(r"UnrealBloomPass\([^\n;]*?\.\.\.GLOW\.bloom\)", js):
        bad.append("UnrealBloomPass 没用 ...GLOW.bloom")
    for mm in re.finditer(r"emissive:([^,}]+),emissiveIntensity:([\d.]+)", js):
        col, val = mm.group(1).strip(), float(mm.group(2))
        if val <= GLOW_CAP["emissive"]:
            continue
        h = re.fullmatch(r"0x([0-9a-fA-F]{6})", col)
        if h:   # 深色底色的自发光只提亮暗部，不算光晕
            r, g, b = (int(h.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
            if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.15:
                continue
        bad.append(f"自发光 {col} × {val} 超过 {GLOW_CAP['emissive']}（改用 GLOW.emissive）")
    return bad


def test_光晕全局标准_新一集的scene都按GLOW常量来():
    eps = sorted(p for p in (ROOT / "tools/vibetennis/episodes").iterdir() if (p / "r3d/scene.js").is_file())
    assert GLOW_LEGACY <= {p.name for p in eps}, f"豁免表里有不存在的集：{GLOW_LEGACY - {p.name for p in eps}}"
    problems = {p.name: _glow_problems((p / "r3d/scene.js").read_text(encoding="utf-8")) for p in eps if p.name not in GLOW_LEGACY}
    assert problems, "一集都没查到——判据自己哑了"
    bad = {k: v for k, v in problems.items() if v}
    assert not bad, f"光晕超标：{bad}"


def test_光晕判据反向验证():
    good = "const GLOW={bloom:[0.22,0.3,0.93], k:0.5, emissive:0.35, emissiveWhite:0.15}; new UnrealBloomPass(v,...GLOW.bloom); emissive:0x0a1a3a,emissiveIntensity:0.5"
    assert _glow_problems(good) == []
    assert _glow_problems(good.replace("0.22,0.3,0.93", "0.5,0.45,0.88"))
    assert _glow_problems(good.replace("...GLOW.bloom", "0.5,0.45,0.88"))
    assert _glow_problems(good + "; emissive:c,emissiveIntensity:0.8")
    assert _glow_problems(good + "; emissive:0xffffff,emissiveIntensity:0.6")
    assert _glow_problems("nothing")


# ---------- 转场与运镜全局标准（所有者 2026-11-05「动画的转场和运镜要做的丝滑且有吸引力」）----------
def _motion_problems(js: str) -> list[str]:
    import re
    m = re.search(r"const MOVE=\{push:([\d.]+),\s*orbit:([\d.]+),\s*xf:([\d.]+),\s*xfPush:([\d.]+)\}", js)
    if not m:
        return ["没有 `const MOVE={push:…, orbit:…, xf:…, xfPush:…}`"]
    push, orbit, xf, xfp = map(float, m.groups())
    bad = []
    if push <= 0 or orbit <= 0: bad.append("运镜推近／绕转为 0，等于静止机位")
    if xf < 0.4: bad.append(f"交叉溶解 {xf}s 太短（≥0.4）")
    for need in ("findCuts(", "xfPass", "CAMMOVE"):
        if need not in js: bad.append(f"缺 {need}")
    if re.search(r"FX_FLASH=0\.(?:[2-9]|1[3-9])", js): bad.append("闪白 > 0.12")
    return bad


def test_转场运镜全局标准_新一集的scene都按MOVE来():
    eps = sorted(p for p in (ROOT / "tools/vibetennis/episodes").iterdir() if (p / "r3d/scene.js").is_file())
    problems = {p.name: _motion_problems((p / "r3d/scene.js").read_text(encoding="utf-8")) for p in eps if p.name not in GLOW_LEGACY}
    assert problems, "一集都没查到——判据自己哑了"
    bad = {k: v for k, v in problems.items() if v}
    assert not bad, f"转场／运镜不合标准：{bad}"


def test_转场运镜判据反向验证():
    good = "const MOVE={push:0.06, orbit:0.06, xf:0.6, xfPush:0.04}; findCuts(); xfPass; CAMMOVE; FX_FLASH=0.12;"
    assert _motion_problems(good) == []
    assert _motion_problems(good.replace("xf:0.6", "xf:0.2"))
    assert _motion_problems(good.replace("push:0.06", "push:0"))
    assert _motion_problems(good.replace("findCuts();", ""))
    assert _motion_problems(good.replace("FX_FLASH=0.12", "FX_FLASH=0.3"))
