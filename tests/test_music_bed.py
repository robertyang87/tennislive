"""配乐（`spec.music`）：铺在现场声底下、被旁白闪避、授权必填。

来路：账号所有者 2026-08-27 定「网球有故事」的标准时点名「**还有背景音乐**」。
在这之前这条线是**明令不加**的（`docs/columns.md` /
`docs/copy-pipeline-spec.md` / `docs/short-video-benchmark-strategy.md` 三处），
而那条老规矩不是随便定的——2026-08-06 那次平台判罚点名「素材简单增加标题、
字幕或简易配音」，把音乐划出去当时是对的。

所以**翻的是「加不加」，不是「靠什么撑住这条片子」**，判据都钉在这一句上：

  · 音乐进的是压缩器**主路**，和现场声一起被旁白压下去（不是另铺一层）
  · 音乐要**量出来**比现场声低 `MUSIC_UNDER_BED_DB`（不是照着 gain 猜）
  · `silent_source` 的片子一律不许配乐（没有现场声时音乐就成了唯一的底）
  · 授权四件套缺一条当场报错

⚠️ 前两条**必须真跑一次 ffmpeg**。查源码里有没有 `[mus]` 只能防「有人把它
删了」，防不住「它从来没工作过」——这个仓库为这句话栽过好几次。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("tools").resolve()))
import build_match_reel as reel  # noqa: E402


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def _mean_db(path: Path, start: float | None = None,
             length: float | None = None, band: str = "") -> float:
    """这一段的平均响度。给了 start/length 就只量那一窗。

    `band` 是一条前置滤镜。量闪避的时候必须用它：成片里**旁白自己也在**，
    直接量总电平会得出「旁白一进来更响了」——那是真的，可它不回答
    「底层被压下去没有」。所以把旁白那个频段滤掉，只量底层。
    """
    args = ["ffmpeg", "-hide_banner"]
    if start is not None:
        args += ["-ss", str(start)]
    args += ["-i", str(path)]
    if length is not None:
        args += ["-t", str(length)]
    chain = f"{band},volumedetect" if band else "volumedetect"
    args += ["-vn", "-af", chain, "-f", "null", os.devnull]
    out = subprocess.run(args, capture_output=True, text=True).stderr
    found = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
    assert found, f"量不出响度：{out[-300:]}"
    return float(found.group(1))


@pytest.fixture()
def ffmpeg() -> None:
    # 缺 ffmpeg 要红，不许 skip——一条常年跳过的检查和常年红是同一个毛病。
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"


def _make_bed(tmp: Path, seconds: float = 16.0) -> Path:
    """一段有画面有现场声的「片子」。现场声用粉噪，像球场底噪。"""
    bed = tmp / "bed.mp4"
    _ff("-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=25:duration={seconds}",
        "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.3:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(bed))
    return bed


def _make_music(tmp: Path, seconds: float = 30.0, amp: float = 0.4) -> Path:
    music = tmp / "music.m4a"
    _ff("-f", "lavfi",
        "-i", f"sine=frequency=220:duration={seconds}",
        "-af", f"volume={amp}", "-c:a", "aac", str(music))
    return music


def test_配乐铺在现场声底下而且和现场声一起被旁白闪避(tmp_path, ffmpeg):
    """真跑一次混音，量三件事——三件缺一件这条判据都会变成恒真的绿灯。

    ① **音乐真的进了成片**：同一条现场声，配了乐要比没配响。
    ② **它被旁白闪避**：旁白那几秒的电平要明显低于没人说话那几秒。
    ③ **闪避行为没被音乐改掉**：加音乐前后，「有旁白」和「没旁白」之间的
       落差要基本一样——`sidechaincompress` 的动态只看 sidechain（旁白），
       往主路加一条音轨不该动它。这一条是这次改动**唯一**可能悄悄弄坏的
       东西，而它在成片上听不出来。
    """
    bed = _make_bed(tmp_path)
    music = _make_music(tmp_path)
    voice = tmp_path / "voice.m4a"
    # 旁白落在 4~9 秒；0~4 和 11~16 秒没人说话
    # 三路各占一个频段，量的时候才分得开：现场声粉噪（宽带）、音乐 220Hz、
    # 旁白 3000Hz。旁白挑得这么远是为了下面那条 `lowpass` 滤得干净。
    _ff("-f", "lavfi", "-i", "sine=frequency=3000:duration=5",
        "-c:a", "aac", str(voice))
    #: 只量底层（现场声 + 音乐），把旁白那 3000Hz 滤掉
    low = "lowpass=f=600,lowpass=f=600,lowpass=f=600,lowpass=f=600"
    vfilter = ["[1:a]adelay=4000|4000[v0]"]

    plain, withmus = tmp_path / "plain.m4a", tmp_path / "withmus.m4a"
    _ff("-i", str(bed), "-i", str(voice), "-filter_complex",
        reel.duck_filtergraph(vfilter, ["[v0]"]),
        "-map", "0:v:0", "-map", "[out]", "-c:v", "copy", "-c:a", "aac",
        "-ar", reel.AUDIO_RATE, "-shortest", str(plain))

    # ⚠️ 淡入淡出的窗口要**避开量的那两窗**：默认淡出从 `片长−4s` 起，
    # 也就是 12s——第一版正好量在 12~15s，量到的是音乐正在淡出的那一段，
    # 于是「音乐没进去」和「量错了地方」长得一模一样。
    chain = reel.music_filter({"gain": 0.9, "fade_in": 1.0, "fade_out": 1.0},
                              2, 16.0)
    _ff("-i", str(bed), "-i", str(voice), "-i", str(music), "-filter_complex",
        reel.duck_filtergraph(vfilter, ["[v0]"], chain),
        "-map", "0:v:0", "-map", "[out]", "-c:v", "copy", "-c:a", "aac",
        "-ar", reel.AUDIO_RATE, "-shortest", str(withmus))

    # ① 音乐真的进去了（挑没人说话的那一窗比，免得被旁白盖住）
    quiet_plain = _mean_db(plain, 10.5, 3.5, low)
    quiet_music = _mean_db(withmus, 10.5, 3.5, low)
    assert quiet_music > quiet_plain + 0.8, (
        f"配了乐 {quiet_music:.1f} dB vs 没配 {quiet_plain:.1f} dB"
        "——音乐没进成片，或者被压到听不见了")

    # ② 旁白那几秒，底层（现场声+音乐）被压下去了
    talk_music = _mean_db(withmus, 5.5, 2.5, low)
    assert quiet_music - talk_music > 2.0, (
        f"没人说话 {quiet_music:.1f} dB、旁白进来 {talk_music:.1f} dB，"
        "落差不到 2 dB——闪避没生效，音乐一路压在旁白上")

    # ③ 闪避的**落差**不该因为多了一条音乐就变掉
    talk_plain = _mean_db(plain, 5.5, 2.5, low)
    assert abs((quiet_music - talk_music) - (quiet_plain - talk_plain)) < 3.0, (
        f"闪避落差：没配乐 {quiet_plain - talk_plain:.1f} dB、"
        f"配了乐 {quiet_music - talk_music:.1f} dB——差太多，"
        "说明音乐接错了地方（多半接进了 sidechain，而不是主路）")


def test_配乐不许混进旁白那一路的amix计数(tmp_path, ffmpeg):
    """`filters` 的长度就是旁白 amix 的输入数。把音乐链塞进去，
    ffmpeg 只会报一句「找不到输入」——而那句话指向的是完全错的方向。

    所以音乐走**单独的参数**，判据钉在滤镜图本身：旁白那一路的 amix
    输入数不许因为配了乐而变。
    """
    vf = ["[1:a]adelay=0|0[v0]", "[2:a]adelay=0|0[v1]"]
    plain = reel.duck_filtergraph(vf, ["[v0]", "[v1]"])
    withmus = reel.duck_filtergraph(vf, ["[v0]", "[v1]"],
                                    reel.music_filter({}, 3, 10.0))
    assert "[v0][v1]amix=inputs=2:" in plain
    assert "[v0][v1]amix=inputs=2:" in withmus, (
        "配了乐之后旁白那一路的 amix 输入数变了——音乐混进 filters 了")
    # 而且音乐真的接在压缩器的**主路**上
    assert "[ambient][vk]sidechaincompress" in withmus
    assert "[bed][mus]amix" in withmus


def test_配乐比现场声还响要当场报错并给出该调到多少(tmp_path, ffmpeg):
    """这道闸**量两条真音轨**，不看 gain。

    为什么不能看 gain：两条轨各自的母带响度差得动十几 dB，同一个 0.09
    配一首 −24 dB 的钢琴和一首 −9 dB 的合成器完全是两回事。
    """
    bed = _make_bed(tmp_path, 6.0)
    loud = tmp_path / "loud.m4a"
    _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=8",
        "-c:a", "aac", str(loud))

    bad, line = reel.music_level_problem({"file": str(loud), "gain": 1.0}, bed)
    assert bad, f"一首和现场声一样响的曲子没被拦下来：{line}"
    assert "低" in bad and "gain" in bad
    # 报错要给出**该调到多少**，不是只说不行
    want = re.search(r"调到 ([\d.]+)", bad)
    assert want, f"报错里没有建议值：{bad}"
    ok, line2 = reel.music_level_problem(
        {"file": str(loud), "gain": float(want.group(1)) * 0.9}, bed)
    assert not ok, f"照它给的建议值调下去还是不合格：{line2}"

    # **合格也要出声**——「压得够低」和「这一步根本没跑」在成片上长得一样
    assert "现场声" in line2 and "dB" in line2


def test_没有现场声的片子不许配乐():
    """`silent_source` + 配乐 = 音乐成了整条片子唯一的底，而那正是
    2026-08-06 平台判罚点名的那一句。这是**合规闸不是品味闸**。"""
    spec = {
        "silent_source": "宣传片母带没有现场声",
        "music": {"file": "assets/music/road-in-the-forest.mp3",
                  "title": "x", "artist": "y", "license": "CC0 1.0",
                  "source": "https://example.com/a"},
    }
    bad = reel.music_problem(spec)
    assert "silent_source" in bad and "不许再配乐" in bad
    # 反过来：没有 silent_source 的同一块 music 要过
    assert not reel.music_problem({"music": spec["music"]})


@pytest.mark.parametrize("missing", reel.MUSIC_CREDIT_FIELDS)
def test_配乐的授权四件套缺一条就报错(missing):
    """一首说不清出处的曲子发出去，赔上的是整个账号。
    **不许写 unknown 糊过去**——四件套是硬的。"""
    music = {"file": "assets/music/road-in-the-forest.mp3",
             "title": "Road In The Forest", "artist": "Andrewkn",
             "license": "CC0 1.0",
             "source": "https://freesound.org/people/Andrewkn/sounds/439553"}
    assert not reel.music_problem({"music": music}), "四件套齐了反而报错"
    music.pop(missing)
    bad = reel.music_problem({"music": music})
    assert missing in bad, f"少了 {missing} 却没报出来：{bad!r}"


def test_配乐比片子短要报错不许悄悄循环(tmp_path, ffmpeg):
    """循环会在接缝上留一道听得见的跳，而这条线连**画面**接缝都要求溶解。
    所以宁可报错让人换一首，也不自动循环。"""
    short = tmp_path / "short.m4a"
    _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=6",
        "-c:a", "aac", str(short))
    music = {"file": str(short), "title": "t", "artist": "a",
             "license": "CC0 1.0", "source": "https://example.com/x"}
    assert not reel.music_problem({"music": music}), "只查形状时不该管时长"
    bad = reel.music_problem({"music": music}, film_seconds=30.0)
    assert "只有" in bad and "循环" in bad, bad
    assert not reel.music_problem({"music": music}, film_seconds=5.0)


def test_仓库里那首配乐的旁证要和字节对得上():
    """旁证里的 sha256/bytes 必须是**这一份文件**的。

    这条拦的是「换了曲子忘了改旁证」——而那正是最难查的一种：
    成片里放的是 A，仓库里的授权写的是 B。
    """
    import hashlib  # noqa: PLC0415
    import json  # noqa: PLC0415

    for mp3 in sorted(Path("assets/music").glob("*.mp3")):
        proof_path = mp3.with_suffix(mp3.suffix + ".json")
        assert proof_path.is_file(), f"{mp3} 没有旁证——说不清出处的曲子不许留在仓库里"
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        blob = mp3.read_bytes()
        assert proof["bytes"] == len(blob), f"{mp3} 的旁证 bytes 对不上"
        assert proof["sha256"] == hashlib.sha256(blob).hexdigest(), (
            f"{mp3} 的旁证 sha256 对不上——旁证说的不是这一份文件")
        for key in reel.MUSIC_CREDIT_FIELDS:
            assert str(proof.get(key) or "").strip(), f"{mp3} 的旁证缺 {key}"


def test_翻过面的那条不加背景音乐不许自己回来():
    """2026-08-27 之前三处文档都写着「不加背景音乐」，账号所有者当天点名
    「还有背景音乐」把它翻了面。

    **钉两头，缺一头都是恒真的绿灯**：

    ① 文档里不许再出现**裸的**「不加背景音乐」——记教训的那句（划掉的、
       引着当年原话的）不算，那正是本仓库反复栽的「判据被自己的注释误伤」。
    ② `spec.music` 这条路必须还活着。只钉 ①，把整套配乐删掉照样绿。
    """
    for doc in sorted(Path("docs").glob("*.md")):
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if "不加背景音乐" not in line:
                continue
            assert "~~" in line or "2026-08-27" in line, (
                f"{doc}:{lineno} 还写着裸的「不加背景音乐」——那条规矩"
                f"2026-08-27 翻面了：{line.strip()}")

    assert "music" in reel._REAL_FIELDS["spec"], "`music` 掉出真字段表了"
    assert callable(reel.music_problem) and callable(reel.music_filter)
    assert reel.MUSIC_UNDER_BED_DB > 0, "低于现场声多少 dB 这道闸没了"


def test_配乐从中间起用要把跳过的那一截减掉(tmp_path, ffmpeg):
    """`start_at` 是「从曲子的第几秒开始用」。**能用的长度要减掉它**——
    从第 20 秒起用一首 30 秒的曲子，只剩 10 秒。

    第一版忘了减，于是一首「够长」的曲子会在片子中途断掉而这道闸说没问题：
    `amix` 的 `dropout_transition=0` 只保证音乐没了的时候现场声不会突然提音，
    **它不会告诉你音乐没了**。又一次「兜底出事的时候不吭声」。
    """
    track = tmp_path / "m.m4a"
    _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=30",
        "-c:a", "aac", str(track))
    base = {"file": str(track), "title": "t", "artist": "a",
            "license": "CC0 1.0", "source": "https://example.com/x"}

    # 从头用：30 秒够 25 秒的片子
    assert not reel.music_problem({"music": base}, film_seconds=25.0)
    # 从第 20 秒起用：只剩 10 秒，25 秒的片子不够
    bad = reel.music_problem({"music": {**base, "start_at": 20}}, film_seconds=25.0)
    assert "只剩" in bad and "20" in bad, bad
    # 而 8 秒的片子够
    assert not reel.music_problem({"music": {**base, "start_at": 20}}, film_seconds=8.0)
    # start_at 也要是个合法的数
    assert "不能是负数" in reel.music_problem({"music": {**base, "start_at": -1}})
    assert "不是数字" in reel.music_problem({"music": {**base, "start_at": "早点"}})


def test_整屏证据卡的底边不许压到字幕上(tmp_path):
    """卡是**居中**铺进画布的，字幕是**上锚**的——两个数各管各的，于是够高的卡
    会直接盖住字幕。

    ⚠️ **这是一整类，不是一次手滑**：卡一旦被**高度**卡住（细长的竖图），
    铺出来必然是 1267 高、底边 1353，而字幕在 1284。**任何竖图证据卡都会压字幕**。

    来路：`wawrinka-farewell-story` 第一版拿那篇告别帖的整屏截图
    （1132×1788）当证据卡，渲出来「最后一句是——永远感激，永远纽约」这行字幕
    **正好压在时间戳行上**——旁白引的那句证据，被引它的那行字盖住了。
    **四道本地闸一道都没响**：dry-run 只看形状、check-narration 只量长度、
    预览工具跳过整屏证据段（它没有源片窗口）、check_reel_landed 量画布和响度。
    只有把成片拉回来抽帧才看得见——所以这条判据是那次返工换来的。
    """
    from PIL import Image  # noqa: PLC0415

    def card(w: int, h: int) -> str:
        p = tmp_path / f"c{w}x{h}.png"
        Image.new("RGB", (w, h), (250, 250, 250)).save(p)
        return str(p)

    # 高得被 88% 那道高度卡住 → 底边恒 1353，压在 1284 的字幕上
    bad = reel.evidence_card_overlaps_subtitle(
        {"segments": [{"image": card(1132, 1788), "seconds": 7, "narration": "x"}]})
    assert "字幕会压在卡上" in bad and "1353" in bad
    assert "裁矮" in bad, "报错没说出路"
    assert "subtitle_top" in bad, "报错没拦住「改字幕位置」那条歪路"

    # 裁矮之后过
    assert not reel.evidence_card_overlaps_subtitle(
        {"segments": [{"image": card(1132, 845), "seconds": 7, "narration": "x"}]})
    # 宽图本来就不会撞
    assert not reel.evidence_card_overlaps_subtitle(
        {"segments": [{"image": card(1944, 684), "seconds": 5, "narration": "x"}]})
    # 没有 image 的段一概不管
    assert not reel.evidence_card_overlaps_subtitle(
        {"segments": [{"start": 1, "end": 5, "narration": "x"}]})


def test_仓库里每一张证据卡都躲开了字幕():
    """装闸那天扫过 `specs/`：11 张证据卡零命中，所以这条闸**没有豁免表**。

    这一条是那句话的判据——哪天有人加了一张压字幕的卡，它会当场红，
    而不是等成片渲出来、拉回本地、抽帧才看见。
    """
    import json  # noqa: PLC0415

    checked = 0
    for spec_path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        cards = [s for s in (spec.get("segments") or [])
                 if isinstance(s, dict) and s.get("image")]
        if not cards:
            continue
        checked += len(cards)
        bad = reel.evidence_card_overlaps_subtitle(spec)
        assert not bad, f"{spec_path.name}：{bad}"
    # 判据自己的判据：一张都没扫到就说明主语没了（图挪走了/字段改名了）
    assert checked >= 10, f"只校到 {checked} 张证据卡，这条判据多半已经落空了"
