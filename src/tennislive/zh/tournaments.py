"""赛事英文名 → 中文名与级别.

起始数据集，由自动整理脚本持续扩充。key 统一小写匹配（包含匹配）。
"""

from __future__ import annotations

# 英文关键词（小写）→ 中文名
TOURNAMENT_ZH: dict[str, str] = {
    "australian open": "澳大利亚网球公开赛",
    "roland garros": "法国网球公开赛",
    "french open": "法国网球公开赛",
    "wimbledon": "温布尔登网球锦标赛",
    "us open": "美国网球公开赛",
    "indian wells": "印第安维尔斯站",
    "bnp paribas open": "印第安维尔斯站",
    "miami open": "迈阿密站",
    "monte carlo": "蒙特卡洛大师赛",
    "monte-carlo": "蒙特卡洛大师赛",
    "madrid open": "马德里站",
    "mutua madrid": "马德里站",
    "italian open": "罗马站",
    "internazionali": "罗马站",
    "rome": "罗马站",
    "canadian open": "加拿大站",
    "national bank open": "加拿大站",
    "cincinnati": "辛辛那提站",
    "shanghai": "上海大师赛",
    "paris masters": "巴黎大师赛",
    "rolex paris": "巴黎大师赛",
    "china open": "中国网球公开赛",
    "wuhan": "武汉网球公开赛",
    "atp finals": "ATP年终总决赛",
    "wta finals": "WTA年终总决赛",
    "united cup": "联合杯",
    "davis cup": "戴维斯杯",
    "billie jean king cup": "比利·简·金杯",
    "laver cup": "拉沃尔杯",
    "next gen": "新生代总决赛",
    "dubai": "迪拜站",
    "doha": "多哈站",
    "qatar": "多哈站",
    "acapulco": "阿卡普尔科站",
    "rio open": "里约站",
    "barcelona": "巴塞罗那站",
    "hamburg": "汉堡站",
    "halle": "哈雷站",
    "queen's club": "女王杯",
    "queens club": "女王杯",
    "stuttgart": "斯图加特站",
    "eastbourne": "伊斯特本站",
    "bastad": "巴斯塔德站",
    "gstaad": "格施塔德站",
    "umag": "乌马格站",
    "kitzbuhel": "基茨比厄尔站",
    "newport": "纽波特站",
    "atlanta": "亚特兰大站",
    "washington": "华盛顿站",
    "los cabos": "洛斯卡沃斯站",
    "winston-salem": "温斯顿-塞勒姆站",
    "chengdu": "成都站",
    "hangzhou": "杭州站",
    "tokyo": "东京站",
    "basel": "巴塞尔站",
    "vienna": "维也纳站",
    "stockholm": "斯德哥尔摩站",
    "antwerp": "安特卫普站",
    "metz": "梅斯站",
    "marseille": "马赛站",
    "rotterdam": "鹿特丹站",
    "montpellier": "蒙彼利埃站",
    "auckland": "奥克兰站",
    "adelaide": "阿德莱德站",
    "brisbane": "布里斯班站",
    "hong kong": "中国香港站",
    "charleston": "查尔斯顿站",
    "strasbourg": "斯特拉斯堡站",
    "nottingham": "诺丁汉站",
    "birmingham": "伯明翰站",
    "bad homburg": "巴特洪堡站",
    "palermo": "巴勒莫站",
    "iasi": "雅西站",
    "prague": "布拉格站",
    "cleveland": "克利夫兰站",
    "monterrey": "蒙特雷站",
    "guadalajara": "瓜达拉哈拉站",
    "ningbo": "宁波站",
    "guangzhou": "广州站",
    "seoul": "首尔站",
    "linz": "林茨站",
    "ostrava": "俄斯特拉发站",
}

# 英文关键词（小写）→ 级别代码（GS / M1000 / W1000 / ATP500 / ATP250 / WTA500 / WTA250 / Finals / TeamCup）
TOURNAMENT_LEVEL: dict[str, str] = {
    "australian open": "GS",
    "roland garros": "GS",
    "french open": "GS",
    "wimbledon": "GS",
    "us open": "GS",
    "indian wells": "M1000",
    "bnp paribas open": "M1000",
    "miami open": "M1000",
    "monte carlo": "M1000",
    "monte-carlo": "M1000",
    "madrid open": "M1000",
    "italian open": "M1000",
    "rome": "M1000",
    "canadian open": "M1000",
    "national bank open": "M1000",
    "cincinnati": "M1000",
    "shanghai": "M1000",
    "paris masters": "M1000",
    "china open": "W1000",
    "wuhan": "W1000",
    "atp finals": "Finals",
    "wta finals": "Finals",
    "united cup": "TeamCup",
    "davis cup": "TeamCup",
    "billie jean king cup": "TeamCup",
    "laver cup": "TeamCup",
}


def tournament_zh(name: str | None) -> str | None:
    """赛事英文名 → 中文名；未识别时原样返回."""
    if not name:
        return None
    key = name.strip().lower()
    for k, v in sorted(TOURNAMENT_ZH.items(), key=lambda kv: -len(kv[0])):
        if k in key:
            return v
    return name


def tournament_level(name: str | None, tour: str | None = None) -> str | None:
    """按赛事名推断级别代码；未识别返回 None."""
    if not name:
        return None
    key = name.strip().lower()
    for k, v in sorted(TOURNAMENT_LEVEL.items(), key=lambda kv: -len(kv[0])):
        if k in key:
            # 综合类赛事按巡回赛区分（如 Miami 对 ATP 是 M1000、对 WTA 是 W1000）
            if v == "M1000" and tour == "WTA":
                return "W1000"
            return v
    return None
