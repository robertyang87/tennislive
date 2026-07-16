"""轮次、场地、级别等术语的中文映射."""

from __future__ import annotations

# 轮次：key 统一用小写做包含匹配
ROUND_ZH: dict[str, str] = {
    "final": "决赛",
    "semifinal": "半决赛",
    "semi-final": "半决赛",
    "semifinals": "半决赛",
    "quarterfinal": "四分之一决赛",
    "quarter-final": "四分之一决赛",
    "quarterfinals": "四分之一决赛",
    "round of 128": "第一轮",
    "round of 64": "64强赛",
    "round of 32": "32强赛",
    "round of 16": "16强赛",
    "1st round": "第一轮",
    "2nd round": "第二轮",
    "3rd round": "第三轮",
    "4th round": "第四轮",
    "first round": "第一轮",
    "second round": "第二轮",
    "third round": "第三轮",
    "fourth round": "第四轮",
    "round 1": "第一轮",
    "round 2": "第二轮",
    "round 3": "第三轮",
    "round 4": "第四轮",
    "qualifying": "资格赛",
    "qualification": "资格赛",
    "round robin": "小组赛",
    "group stage": "小组赛",
    "playoff": "附加赛",
    "3rd place": "季军赛",
}

# 特殊轮次的精确别名（缩写）
ROUND_ABBR_ZH: dict[str, str] = {
    "f": "决赛",
    "sf": "半决赛",
    "qf": "四分之一决赛",
    "r16": "16强赛",
    "r32": "32强赛",
    "r64": "64强赛",
    "r128": "第一轮",
    "rr": "小组赛",
    "q1": "资格赛首轮",
    "q2": "资格赛次轮",
    "q3": "资格赛决胜轮",
}

SURFACE_ZH: dict[str, str] = {
    "hard": "硬地",
    "clay": "红土",
    "grass": "草地",
    "carpet": "地毯",
    "indoor": "室内硬地",
}

LEVEL_ZH: dict[str, str] = {
    "GS": "大满贯",
    "M1000": "ATP 1000大师赛",
    "W1000": "WTA 1000",
    "ATP500": "ATP 500",
    "ATP250": "ATP 250",
    "WTA500": "WTA 500",
    "WTA250": "WTA 250",
    "Finals": "年终总决赛",
    "TeamCup": "团体赛",
}

# 项目（单双打）
DISCIPLINE_ZH: dict[str, str] = {
    "men's singles": "男单",
    "women's singles": "女单",
    "men's doubles": "男双",
    "women's doubles": "女双",
    "mixed doubles": "混双",
    "mens singles": "男单",
    "womens singles": "女单",
    "mens doubles": "男双",
    "womens doubles": "女双",
    "singles": "单打",
    "doubles": "双打",
}


def round_zh(round_name: str | None) -> str | None:
    """轮次英文名 → 中文；未识别时原样返回."""
    if not round_name:
        return None
    key = round_name.strip().lower()
    if key in ROUND_ABBR_ZH:
        return ROUND_ABBR_ZH[key]
    # 轮次可能内嵌在类似 "Men's Singles - Round of 16" 的字符串中
    for k, v in sorted(ROUND_ZH.items(), key=lambda kv: -len(kv[0])):
        if k in key:
            return v
    return round_name


def discipline_zh(discipline: str | None) -> str | None:
    if not discipline:
        return None
    key = discipline.strip().lower()
    for k, v in sorted(DISCIPLINE_ZH.items(), key=lambda kv: -len(kv[0])):
        if k in key:
            return v
    return discipline
