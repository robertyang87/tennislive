"""段与段之间的转场动画库：写 spec 时按名字挑一个，渲染时直接套用。

账号所有者 2026-10-27：「多准备一些转场动画作为过渡效果，后续做视频需要的时候
直接套用」。

### 怎么用

剪辑片（赛场之上、网球有故事的剪辑片，`tools/build_match_reel.py`）在某一段上写

    "transition": "slide_left"

意思是**接进这一段的那个接缝**用这个动画；不写就是 `dissolve`（原来那条溶解）。
片尾那一刀照旧溶解。名字只认 `PRESETS` 里的，写错 `--dry-run` 就红。

### 为什么时长不让改

每个接缝都是 `build_match_reel.SEG_FADE`（0.18 秒），动画只换**形状**不换长度：
part 多切的溶解底料、旁白 adelay、字幕 cue、现场声 `acrossfade`、死球后的 ghost
检查，全按这 0.18 秒记账（见 `dissolve_filtergraph` 的长度账）。改成每个接缝
各自一个时长，要动的不是这里，是那一整本账。0.18 秒在 60 fps 上是 11 帧，
推、甩、圈开都看得清（2026-10-27 逐帧量过，见 `docs/transition-presets.md`）。

### 为什么不收 `fadeblack` / `fadewhite` / `zoomin` / `pixelize`

账号所有者的老规矩：「接缝画面的时候有轻微的闪烁」——**中间一帧黑都不许有**
（`design_tokens.MOTION["video_dissolve_s"]`）。`fadeblack` / `fadewhite` 就是
淡到黑/白；`zoomin` 在 0.18 秒里把前一画面放到满屏一块纯色（实测中段整幅
单色），观感和闪一下一样；`pixelize` 是马赛克，不合这个号的质感。
判据 `tests/test_transitions.py::test_每个转场中间都不闪黑不闪成一块纯色`
真跑 ffmpeg 逐帧量，谁要加新的预设，先过这一条。
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class Preset:
    xfade: str   # ffmpeg xfade 的 transition 名（6.1 起都有）
    zh: str      # 中文名
    use: str     # 什么时候用


DEFAULT = "dissolve"

PRESETS: Mapping[str, Preset] = MappingProxyType({
    "dissolve": Preset("fade", "溶解", "默认；同一场球里两个回合之间、不想让人注意到剪辑的地方"),
    "slide_left": Preset("slideleft", "左推", "时间往前走：下一盘、下一场、下一年"),
    "slide_right": Preset("slideright", "右推", "倒回去：插叙一段更早的比赛"),
    "slide_up": Preset("slideup", "上推", "从比赛画面推到数据卡、字卡"),
    "slide_down": Preset("slidedown", "下推", "从字卡落回比赛画面"),
    "smooth_left": Preset("smoothleft", "柔推", "比左推更软的推进，情绪段之间"),
    "whip": Preset("hblur", "快甩", "同一场里跳到下一个关键分，带一下速度感"),
    "iris": Preset("circleopen", "圈开", "揭晓：赛点、结果、捧杯那一下"),
    "iris_close": Preset("circleclose", "圈收", "收束：一段故事讲完，收进下一段"),
    "clock": Preset("radial", "时钟扫", "时间流逝：伤停、空白期、几个月之后"),
    "memory": Preset("fadegrays", "褪色回忆", "切进历史画面：当年那场、多年以前"),
    "diagonal": Preset("diagtl", "斜切", "两个人、两条线对照着讲"),
    "reveal_left": Preset("wipeleft", "擦出", "干净利落的换场，换赛事、换人物"),
})


def validate(name: object) -> str:
    """spec 里写的名字 → 合法预设名；不认识就报错，把能用的列出来。"""
    if name is None:
        return DEFAULT
    if not isinstance(name, str) or name not in PRESETS:
        menu = "、".join(f"{k}（{p.zh}）" for k, p in PRESETS.items())
        raise ValueError(f"转场 `{name!r}` 不在动画库里。能用的：{menu}")
    return name


def xfade_transition(name: str) -> str:
    """预设名 → ffmpeg `xfade=transition=` 的值。"""
    return PRESETS[validate(name)].xfade


def xfade_names() -> frozenset[str]:
    """库里所有 ffmpeg transition 名——拼接图的识别器只认这几个。"""
    return frozenset(p.xfade for p in PRESETS.values())
