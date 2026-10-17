"""电影感出片选项（全部 opt-in，spec 不写就和原来逐字节一致）。

账号所有者 2026-10-17：「加一些出片工具」——调色、颗粒暗角、预告片式片头片尾卡、
接缝转场、分轨音频、低清放大锐化、反应镜头推近。**不做慢放、定格**：比赛的分
一律原速（同日明令禁止），所以这里没有任何变速入口。

spec 形状（都可省）::

    "cinematic": {
      "grade": "teal_orange" | "moody" | "neutral",   # 调色预设，整片统一
      "grade_strength": 0.0~1.0,                       # 默认 1.0
      "grain": 0.0~1.0, "vignette": 0.0~1.0,           # 默认 0
      "match": {"源键": {"exposure": -0.3~0.3, "temperature": 3000~9000,
                         "saturation": 0.6~1.4}},      # 逐源先拉齐曝光/白平衡
      "stems": true                                    # 另出 narration/original/mix 三条 WAV
    }
    段落："transition_in": "dissolve"(默认) | "cut" | "flash" | "whip"
          "push_in": 1.0~1.15   # 慢推镜：段内从 1.0 匀速推到这个倍数（Ken Burns）

只作用于**比赛画面段**（cut_segment 那条链）：封面、章节卡、片尾、角标、字幕
都不调色、不加颗粒——字和品牌色不能被 LUT 染。
"""
from __future__ import annotations

import re

#: 调色预设：一条 ffmpeg 滤镜链（只用 BtbN/沙箱 ffmpeg 都有的内建滤镜）。
#: strength 用 `mix` 不了（单链），所以按强度线性缩放各参数，见 `look_filter`。
PRESETS: dict[str, dict] = {
    # 阴影偏青、高光偏橙，略加对比——体育宣传片最常见的那一档
    "teal_orange": {"rs": -0.06, "bs": 0.08, "rh": 0.07, "bh": -0.07,
                    "contrast": 1.08, "saturation": 1.06, "gamma": 0.98},
    # 压暗、去饱和、高对比，偏冷
    "moody": {"rs": -0.03, "bs": 0.05, "rh": 0.02, "bh": -0.01,
              "contrast": 1.14, "saturation": 0.88, "gamma": 0.94},
    # 只做逐源拉齐，不加风格
    "neutral": {"rs": 0, "bs": 0, "rh": 0, "bh": 0,
                "contrast": 1.0, "saturation": 1.0, "gamma": 1.0},
}

#: 接缝转场 → xfade 的 transition 写法。时长一律沿用 SEG_FADE（长度账不变）。
#: cut 用 custom 表达式在溶解窗口正中硬切：前一段多播的那 SEG_FADE/2 秒是它
#: 自己的自然延续（tail），所以不会提前切掉一分或一句解说。
TRANSITIONS: dict[str, str] = {
    "dissolve": "fade",
    "cut": "custom:expr='if(gte(P\\,0.5)\\,A\\,B)'",
    "flash": "fadewhite",
    "whip": "hblur",
}

PUSH_MAX = 1.15
_RANGES = {"exposure": (-0.3, 0.3), "temperature": (3000, 9000), "saturation": (0.6, 1.4)}


class CinematicError(ValueError):
    pass


def config(spec: dict | None) -> dict:
    """校验并返回 `spec.cinematic`；没写就是 {}。"""
    raw = (spec or {}).get("cinematic")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CinematicError("cinematic 要写成对象")
    unknown = set(raw) - {"grade", "grade_strength", "grain", "vignette", "match", "stems"}
    if unknown:
        raise CinematicError(f"cinematic 不认识的键：{sorted(unknown)}")
    grade = raw.get("grade")
    if grade is not None and grade not in PRESETS:
        raise CinematicError(f"cinematic.grade 只认 {sorted(PRESETS)}，拿到 {grade!r}")
    for key in ("grade_strength", "grain", "vignette"):
        v = raw.get(key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                              or not 0 <= v <= 1):
            raise CinematicError(f"cinematic.{key} 要是 0~1 的数")
    match = raw.get("match") or {}
    if not isinstance(match, dict):
        raise CinematicError("cinematic.match 要写成 {源键: {...}}")
    srcs = set(((spec or {}).get("sources") or {}))
    for key, m in match.items():
        if srcs and key not in srcs:
            raise CinematicError(f"cinematic.match 的 {key} 不在 sources 里")
        if not isinstance(m, dict) or set(m) - set(_RANGES):
            raise CinematicError(f"cinematic.match.{key} 只认 {sorted(_RANGES)}")
        for f, (lo, hi) in _RANGES.items():
            v = m.get(f)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                                  or not lo <= v <= hi):
                raise CinematicError(f"cinematic.match.{key}.{f} 要在 {lo}~{hi}")
    if "stems" in raw and not isinstance(raw["stems"], bool):
        raise CinematicError("cinematic.stems 要写 true/false")
    return raw


def source_match_filter(cfg: dict, key: str | None) -> str:
    """逐源拉齐（曝光/白平衡/饱和度），带尾逗号；没认领就是空串。"""
    m = ((cfg or {}).get("match") or {}).get(key or "") or {}
    parts = []
    if m.get("temperature") is not None:
        parts.append(f"colortemperature=temperature={int(m['temperature'])}")
    eq = []
    if m.get("exposure"):
        eq.append(f"brightness={float(m['exposure']):.3f}")
    if m.get("saturation") is not None and float(m["saturation"]) != 1.0:
        eq.append(f"saturation={float(m['saturation']):.3f}")
    if eq:
        parts.append("eq=" + ":".join(eq))
    return "".join(p + "," for p in parts)


def look_filter(cfg: dict) -> str:
    """整片统一的调色＋暗角＋颗粒，带前导逗号；什么都没开就是空串。"""
    if not cfg:
        return ""
    parts = []
    grade = cfg.get("grade")
    if grade:
        k = float(cfg.get("grade_strength", 1.0))
        p = PRESETS[grade]
        lerp = lambda a, n: 1 + (a - 1) * k if n else a * k  # noqa: E731
        if any(p[x] for x in ("rs", "bs", "rh", "bh")) and k:
            parts.append("colorbalance=" + ":".join(
                f"{x}={p[x] * k:.3f}" for x in ("rs", "bs", "rh", "bh")))
        c, s, g = (lerp(p["contrast"], 1), lerp(p["saturation"], 1), lerp(p["gamma"], 1))
        if (c, s, g) != (1.0, 1.0, 1.0):
            parts.append(f"eq=contrast={c:.3f}:saturation={s:.3f}:gamma={g:.3f}")
    v = float(cfg.get("vignette") or 0)
    if v:
        # angle 越大越暗：0.2→PI/9 左右，1.0→PI/3.2
        parts.append(f"vignette=angle={0.25 + 0.73 * v:.3f}")
    gr = float(cfg.get("grain") or 0)
    if gr:
        parts.append(f"noise=c0s={max(1, round(14 * gr))}:c0f=t+u")
    return "".join("," + p for p in parts)


def push_filter(push: float, seconds: float, w: int, h: int) -> str:
    """慢推镜（带前导逗号）：段内从 1.0 匀速放大到 `push`，中心不变，输出仍是 w×h。

    只推近、不变速——帧率和时长原样，分和解说都是原速。
    """
    if not push or push <= 1.0:
        return ""
    rate = (push - 1.0) / max(seconds, 0.1)
    return (f",scale=w='trunc({w}*(1+{rate:.5f}*t)/2)*2':h=-2:eval=frame:flags=lanczos,"
            f"crop={w}:{h}")


def seg_transition(s: dict, i: int) -> str:
    v = s.get("transition_in", "dissolve")
    if v not in TRANSITIONS:
        raise CinematicError(f"第 {i + 1} 段 transition_in 只认 {sorted(TRANSITIONS)}，拿到 {v!r}")
    return v


def seg_push(s: dict, i: int) -> float:
    v = s.get("push_in")
    if v is None:
        return 1.0
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 1.0 <= v <= PUSH_MAX:
        raise CinematicError(f"第 {i + 1} 段 push_in 要在 1.0~{PUSH_MAX}")
    if v > 1.0 and (s.get("track") or s.get("score_inset") or s.get("square_pan")
                    or s.get("image") or s.get("title_card") or s.get("stat_card")):
        raise CinematicError(f"第 {i + 1} 段写了 push_in，但它只给普通比赛画面段（反应镜头）用")
    return float(v)


def footage_ratio(spec: dict, official: set[str] | None = None) -> dict:
    """片段里比赛画面的占比。章节卡/预告片卡/数据卡/图片段**不算画面**。

    `official` 是官方源键集合；不给就按 `sources` 里没被 `_unofficial` 认领的算。
    """
    segs = spec.get("segments") or []
    unofficial = set((spec.get("_unofficial") or {}))
    total = foot = off = 0.0
    for s in segs:
        if s.get("seconds") is not None and not s.get("source"):
            length = float(s["seconds"])
        else:
            length = float(s.get("seconds") or (float(s.get("end", 0)) - float(s.get("start", 0))))
        total += length
        if s.get("image") or s.get("title_card") or s.get("stat_card"):
            continue
        foot += length
        key = s.get("source")
        if (official is not None and key in official) or (official is None and key not in unofficial):
            off += length
    return {"total": round(total, 2), "footage": round(foot, 2), "official": round(off, 2),
            "footage_pct": round(100 * foot / total, 1) if total else 0.0,
            "official_pct": round(100 * off / total, 1) if total else 0.0}


_XFADE_RE = "|".join(re.escape(t) for t in TRANSITIONS.values())
