"""赛后开麦这条线的**成片时长**：谁写、写在哪、存量怎么回填。

来路（2026-08-14 量的）：19 条采访产物的 `render.json` **一条都没有
`film_seconds`**，于是「均观看比例」这类要拿片长当分母的指标，对整条线算不出来
——而它坏起来的样子是「这条线没有数据」，不是报错。

根因有两层，两层都不吭声：

  ① `build_interview_clip.render()` **从不写 `render.json`**。那个文件是工作流
     最后发 Release 那一步才创建的，只放 `video_url` / `video_bytes`。
  ② `main()` 打印的 `spec['end'] - spec['start']` 是**正片**长度，不是成片
     长度——成片前面还有封面、后面还有解读卡和品牌片尾。实测 19 条差
     **+1.0 ~ +20.8 秒**，差多少取决于解读卡口播有多长，**光看 spec 算不出来**。
     读到那一行的人会拿它当片长（我们自己就拿它算过观看比例），而它一直偏短。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKFILL_MARK = "backfilled-ffprobe"


def _tiny_mp4(dest: Path, seconds: float) -> Path:
    """造一条真视频。**判据要真跑 ffprobe**，不是把 `probe_duration` 打桩掉——
    打桩掉的话「量出来是多少」这一半根本没被验过。"""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=black:s=64x64:r=25:d={seconds}",
         "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={seconds}",
         "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k",
         "-ar", "48000", "-ac", "2", str(dest)],
        check=True, capture_output=True, timeout=120)
    return dest


def _spec(slug: str) -> dict:
    return {"slug": slug, "url": "https://example.invalid/x", "start": 10.0,
            "end": 30.0, "zh": [], "en": []}


@pytest.mark.parametrize(
    ("case", "with_outro"),
    [("单段直通", False), ("拼接", True)],
)
def test_采访片两个出口都要写film_seconds(tmp_path, monkeypatch, case, with_outro):
    """**`render()` 有两个 return，两个都要记片长。**

    一个是「只有正片一段」时的直通（`body.replace(out)`），另一个是 concat 之后
    的那个。⚠️ 这个文件里同一个形状**栽过一次**：`build_cover` 委托链上只改了
    一个 return，另一条路悄悄用了默认值，成片当场从 114 秒塌成 12 秒，而日志
    里一个字都没说。所以这条判据把两条路**各真跑一遍**。

    ⚠️ **不查源码文本。** `assert "_record_film_seconds" in source` 只能防
    「有人把它删了」，防不住「它从来没工作过」——本仓库为这句话栽过好几次。
    """
    ffmpeg = subprocess.run(["ffmpeg", "-version"], capture_output=True)
    assert ffmpeg.returncode == 0, "ffmpeg 没装：这条判据要真造一条视频再真量一次"

    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import build_interview_clip as mod

    outdir = tmp_path / "out"
    outdir.mkdir()
    spec = _spec("demo")

    # 只打桩「跑不动的那几件事」：下源片、渲封面/解读卡、跑 ffmpeg。
    # 片长那一段（probe_duration → render.json）一个字都不打桩。
    monkeypatch.setattr(mod, "check_takeaway", lambda spec: None)
    monkeypatch.setattr(mod, "yt_download",
                        lambda *a, **k: _tiny_mp4(outdir / "source.mp4", 1.0))
    monkeypatch.setattr(mod, "_takeaway_segments", lambda *a, **k: [])
    if with_outro:
        monkeypatch.setattr(
            mod, "_build_outro",
            lambda d: _tiny_mp4(d / "_outro.mp4", 3.0))
    else:
        monkeypatch.setattr(mod, "_build_outro", lambda d: None)

    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        """正片那次 ffmpeg 造一条 8 秒的；concat 那次照常真跑。"""
        if cmd[0] == "ffmpeg" and "-filter_complex" in cmd:
            _tiny_mp4(outdir / "_body.mp4", 8.0)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    # 产物里先放一个别的键——**合并写，不覆盖**。工作流之后还会往同一个文件
    # 写 video_url / video_bytes，谁覆盖谁都是静默丢字段。
    (outdir / "render.json").write_text(
        json.dumps({"video_url": "https://example.invalid/v.mp4"}) + "\n",
        encoding="utf-8")

    out = mod.render(spec, outdir / "subs.ass", outdir)

    assert out.is_file(), f"{case}：成片没出来，这条判据的前提不成立"
    data = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    assert "film_seconds" in data, (
        f"{case}那条 return 没写 `film_seconds`——两个出口都要写，"
        "别只改一个（`build_cover` 那次就是这么塌的）")
    assert data["video_url"] == "https://example.invalid/v.mp4", (
        f"{case}：把 render.json 覆盖了，原有的键丢了——要合并写")

    # 真量：拼接那条多一段 3 秒片尾，直通那条只有 8 秒正片。
    expect = 11.0 if with_outro else 8.0
    assert abs(data["film_seconds"] - expect) < 1.0, (
        f"{case}：记的是 {data['film_seconds']}，成片实际约 {expect} 秒——"
        "这个数是拿 ffprobe 读成片量的，对不上就说明量错了东西")

    # ⚠️ 记的必须是**成片**，不是正片。正片是 spec 里那 20 秒，
    # 两者在真实产物上差 +1.0 ~ +20.8 秒。
    raw = spec["end"] - spec["start"]
    assert abs(data["film_seconds"] - raw) > 1.0, (
        f"{case}：记成了正片长度（{raw} 秒）——那正是这条判据要拦的东西")


def test_片长探不到只告警不把整趟render判死(tmp_path, monkeypatch, capsys):
    """**片长是元数据，成片已经渲出来了。**

    为一次 ffprobe 失败把整趟六分钟的 render 判死不划算。但**两条路都要出声**
    ——默默不写和写成功长得一模一样（本仓库「兜底出事的时候不吭声」记了一整
    节）。所以失败时要打一行说清楚原因，并且**不留下半个 `film_seconds`**。
    """
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import build_interview_clip as mod

    outdir = tmp_path / "out"
    outdir.mkdir()
    out = outdir / "demo.mp4"
    out.write_bytes(b"not a video")

    def boom(path):
        raise RuntimeError("moov atom not found")

    monkeypatch.setattr(mod, "probe_duration", boom)
    assert mod._record_film_seconds(out, outdir) is out, "要原样把成片返回去"

    said = capsys.readouterr().out
    assert "film_seconds" in said and "moov atom not found" in said, (
        f"探不到的时候没出声，或者没说原因：{said!r}")
    path = outdir / "render.json"
    if path.is_file():
        assert "film_seconds" not in json.loads(path.read_text(encoding="utf-8")), (
            "探不到却写了个 film_seconds——那比不写更坏")


def test_回填的片长要带标记而且认不对人的宁可空着():
    """**回填的和新片子写的不是一回事，要分得出来。**

    存量 19 条采访 + 8 条 reel 是 2026-08-14 拿 `ffprobe` 直接读
    `render.json` 里那条 Release URL 补上的（只取 moov，不下整片）。方法自证过：
    对三条**渲染器自己写过 `film_seconds`** 的产物重量一遍，差 0.000 秒。

    ⚠️ 不许拿「`video_bytes` ÷ 码率」反推——实测这条线码率跨度 3.6 倍
    （2335~8407 kb/s），反推出来的数看着像片长，其实是编的。

    ⚠️ **按 URL 认领会静默认错人。** `output/2026-07-28/reel/nishikori-shang`
    和 `2026-07-29/…` 指向**同一个** Release tag，而 tag 上现在挂的是 7/29 重渲
    的那一版（Range GET 量到 30185483 字节，7/28 那份产物记的是 35863138）。
    所以那一条**故意不填**，只留一句说明——「认不出来好过认成另一个人」，
    这条线上那个数正要被当成观看比例的分母。
    """
    interviews = sorted((ROOT / "output" / "interviews").glob("*/render.json"))
    reels = sorted(ROOT.glob("output/*/reel/*/render.json"))

    # 判据自己的判据：`output/` 不在 CI 的稀疏检出里，主语没了要能看出来，
    # 而不是变成一盏恒真的绿灯（本仓库为这条栽过一次）。
    if not interviews and not reels:
        pytest.skip("这台机器上没有 output/ 产物（CI 的稀疏检出把它挡在外面）")

    assert interviews, "采访产物一条都没有，但 reel 有——目录写错了？"
    missing = [p for p in interviews
               if "film_seconds" not in json.loads(p.read_text(encoding="utf-8"))]
    assert not missing, (
        f"这几条采访产物还没有 film_seconds：{[p.parent.name for p in missing]}")

    for path in interviews + reels:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("film_seconds_source") != BACKFILL_MARK:
            continue
        assert data.get("film_seconds", 0) > 0, (
            f"{path} 标了回填，却没有 film_seconds")

    # 认不对人的那一条：不许有 film_seconds，但必须留下为什么。
    odd = ROOT / "output" / "2026-07-28" / "reel" / "nishikori-shang" / "render.json"
    if odd.is_file():
        data = json.loads(odd.read_text(encoding="utf-8"))
        assert "film_seconds" not in data, (
            "这条的 Release tag 上挂的是 7/29 重渲那一版，量出来的片长不属于它——"
            "宁可空着，也别写一个属于另一条片子的数")
        assert (data.get("_film_seconds_note") or "").strip(), (
            "空着可以，但要留下判据：为什么这一条填不了。"
            "把一个已知的洞抹平，比留着它糟得多")
