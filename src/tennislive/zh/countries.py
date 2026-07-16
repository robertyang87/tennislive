"""国家/地区：IOC 三字码 → (中文名, ISO2 用于旗帜 emoji).

网球数据源常给 IOC 三字码（如 SRB、ESP），部分源给 ISO2（RS）或英文全名
（Italy），lookup 函数对三种形式都兼容。
"""

from __future__ import annotations

# IOC 三字码 → (中文名, ISO 3166-1 alpha-2)；ISO2 为 None 表示不显示旗帜
IOC: dict[str, tuple[str, str | None]] = {
    "CHN": ("中国", "CN"),
    "TPE": ("中华台北", None),
    "HKG": ("中国香港", "HK"),
    "MAC": ("中国澳门", "MO"),
    "JPN": ("日本", "JP"),
    "KOR": ("韩国", "KR"),
    "IND": ("印度", "IN"),
    "THA": ("泰国", "TH"),
    "INA": ("印度尼西亚", "ID"),
    "PHI": ("菲律宾", "PH"),
    "VIE": ("越南", "VN"),
    "KAZ": ("哈萨克斯坦", "KZ"),
    "UZB": ("乌兹别克斯坦", "UZ"),
    "ISR": ("以色列", "IL"),
    "LBN": ("黎巴嫩", "LB"),
    "QAT": ("卡塔尔", "QA"),
    "UAE": ("阿联酋", "AE"),
    "KSA": ("沙特阿拉伯", "SA"),
    "SRB": ("塞尔维亚", "RS"),
    "ESP": ("西班牙", "ES"),
    "ITA": ("意大利", "IT"),
    "FRA": ("法国", "FR"),
    "GER": ("德国", "DE"),
    "GBR": ("英国", "GB"),
    "SUI": ("瑞士", "CH"),
    "AUT": ("奥地利", "AT"),
    "NED": ("荷兰", "NL"),
    "BEL": ("比利时", "BE"),
    "DEN": ("丹麦", "DK"),
    "SWE": ("瑞典", "SE"),
    "NOR": ("挪威", "NO"),
    "FIN": ("芬兰", "FI"),
    "POL": ("波兰", "PL"),
    "CZE": ("捷克", "CZ"),
    "SVK": ("斯洛伐克", "SK"),
    "HUN": ("匈牙利", "HU"),
    "ROU": ("罗马尼亚", "RO"),
    "BUL": ("保加利亚", "BG"),
    "GRE": ("希腊", "GR"),
    "CRO": ("克罗地亚", "HR"),
    "SLO": ("斯洛文尼亚", "SI"),
    "BIH": ("波黑", "BA"),
    "MNE": ("黑山", "ME"),
    "MKD": ("北马其顿", "MK"),
    "ALB": ("阿尔巴尼亚", "AL"),
    "POR": ("葡萄牙", "PT"),
    "RUS": ("俄罗斯", "RU"),
    "BLR": ("白俄罗斯", "BY"),
    "UKR": ("乌克兰", "UA"),
    "MDA": ("摩尔多瓦", "MD"),
    "GEO": ("格鲁吉亚", "GE"),
    "ARM": ("亚美尼亚", "AM"),
    "AZE": ("阿塞拜疆", "AZ"),
    "LAT": ("拉脱维亚", "LV"),
    "LTU": ("立陶宛", "LT"),
    "EST": ("爱沙尼亚", "EE"),
    "CYP": ("塞浦路斯", "CY"),
    "TUR": ("土耳其", "TR"),
    "IRL": ("爱尔兰", "IE"),
    "ISL": ("冰岛", "IS"),
    "LUX": ("卢森堡", "LU"),
    "MON": ("摩纳哥", "MC"),
    "AND": ("安道尔", "AD"),
    "USA": ("美国", "US"),
    "CAN": ("加拿大", "CA"),
    "MEX": ("墨西哥", "MX"),
    "BRA": ("巴西", "BR"),
    "ARG": ("阿根廷", "AR"),
    "CHI": ("智利", "CL"),
    "COL": ("哥伦比亚", "CO"),
    "PER": ("秘鲁", "PE"),
    "ECU": ("厄瓜多尔", "EC"),
    "URU": ("乌拉圭", "UY"),
    "PAR": ("巴拉圭", "PY"),
    "BOL": ("玻利维亚", "BO"),
    "VEN": ("委内瑞拉", "VE"),
    "DOM": ("多米尼加", "DO"),
    "PUR": ("波多黎各", "PR"),
    "BAR": ("巴巴多斯", "BB"),
    "AUS": ("澳大利亚", "AU"),
    "NZL": ("新西兰", "NZ"),
    "RSA": ("南非", "ZA"),
    "EGY": ("埃及", "EG"),
    "MAR": ("摩洛哥", "MA"),
    "TUN": ("突尼斯", "TN"),
    "ALG": ("阿尔及利亚", "DZ"),
    "KEN": ("肯尼亚", "KE"),
    "NGR": ("尼日利亚", "NG"),
    "ZIM": ("津巴布韦", "ZW"),
    "KOS": ("科索沃", "XK"),
    "MLT": ("马耳他", "MT"),
    "CUB": ("古巴", "CU"),
    "JAM": ("牙买加", "JM"),
    "TTO": ("特立尼达和多巴哥", "TT"),
    "BAH": ("巴哈马", "BS"),
    "CRC": ("哥斯达黎加", "CR"),
    "GUA": ("危地马拉", "GT"),
    "ESA": ("萨尔瓦多", "SV"),
    "PAN": ("巴拿马", "PA"),
    "PAK": ("巴基斯坦", "PK"),
    "SRI": ("斯里兰卡", "LK"),
    "BAN": ("孟加拉国", "BD"),
    "MAS": ("马来西亚", "MY"),
    "SGP": ("新加坡", "SG"),
    "BRN": ("巴林", "BH"),
    "IRI": ("伊朗", "IR"),
    # 非 IOC 的数据源变体（ESPN 旗帜图用 rom 表示罗马尼亚等）
    "ROM": ("罗马尼亚", "RO"),
    "GRC": ("希腊", "GR"),
    "DEU": ("德国", "DE"),
    "NLD": ("荷兰", "NL"),
    "CHE": ("瑞士", "CH"),
    "DNK": ("丹麦", "DK"),
    "PRT": ("葡萄牙", "PT"),
    "HRV": ("克罗地亚", "HR"),
    "SVN": ("斯洛文尼亚", "SI"),
    "BGR": ("保加利亚", "BG"),
}

# ISO2 → IOC（自动生成，用于兼容给 ISO2 的数据源）
_ISO2_TO_IOC: dict[str, str] = {
    iso2: ioc for ioc, (_, iso2) in IOC.items() if iso2
}
# 台湾地区数据源常用 "TW"
_ISO2_TO_IOC.setdefault("TW", "TPE")

# 英文全名 → IOC（兼容 ESPN flag.alt 等给全名的情况）
_EN_TO_IOC: dict[str, str] = {
    "china": "CHN",
    "chinese taipei": "TPE",
    "taiwan": "TPE",
    "hong kong": "HKG",
    "hong kong, china": "HKG",
    "japan": "JPN",
    "south korea": "KOR",
    "korea": "KOR",
    "india": "IND",
    "thailand": "THA",
    "indonesia": "INA",
    "kazakhstan": "KAZ",
    "uzbekistan": "UZB",
    "israel": "ISR",
    "qatar": "QAT",
    "united arab emirates": "UAE",
    "saudi arabia": "KSA",
    "serbia": "SRB",
    "spain": "ESP",
    "italy": "ITA",
    "france": "FRA",
    "germany": "GER",
    "great britain": "GBR",
    "united kingdom": "GBR",
    "switzerland": "SUI",
    "austria": "AUT",
    "netherlands": "NED",
    "belgium": "BEL",
    "denmark": "DEN",
    "sweden": "SWE",
    "norway": "NOR",
    "finland": "FIN",
    "poland": "POL",
    "czech republic": "CZE",
    "czechia": "CZE",
    "slovakia": "SVK",
    "hungary": "HUN",
    "romania": "ROU",
    "bulgaria": "BUL",
    "greece": "GRE",
    "croatia": "CRO",
    "slovenia": "SLO",
    "bosnia and herzegovina": "BIH",
    "montenegro": "MNE",
    "north macedonia": "MKD",
    "portugal": "POR",
    "russia": "RUS",
    "belarus": "BLR",
    "ukraine": "UKR",
    "moldova": "MDA",
    "georgia": "GEO",
    "armenia": "ARM",
    "azerbaijan": "AZE",
    "latvia": "LAT",
    "lithuania": "LTU",
    "estonia": "EST",
    "cyprus": "CYP",
    "turkey": "TUR",
    "turkiye": "TUR",
    "ireland": "IRL",
    "monaco": "MON",
    "united states": "USA",
    "usa": "USA",
    "canada": "CAN",
    "mexico": "MEX",
    "brazil": "BRA",
    "argentina": "ARG",
    "chile": "CHI",
    "colombia": "COL",
    "peru": "PER",
    "ecuador": "ECU",
    "uruguay": "URU",
    "venezuela": "VEN",
    "dominican republic": "DOM",
    "puerto rico": "PUR",
    "australia": "AUS",
    "new zealand": "NZL",
    "south africa": "RSA",
    "egypt": "EGY",
    "morocco": "MAR",
    "tunisia": "TUN",
}


def _resolve_ioc(code_or_name: str | None) -> str | None:
    if not code_or_name:
        return None
    s = code_or_name.strip()
    if len(s) == 3 and s.upper() in IOC:
        return s.upper()
    if len(s) == 2:
        return _ISO2_TO_IOC.get(s.upper())
    return _EN_TO_IOC.get(s.lower())


def country_zh(code_or_name: str | None) -> str | None:
    """IOC/ISO2/英文名 → 中文国名；未识别返回原值."""
    ioc = _resolve_ioc(code_or_name)
    if ioc:
        return IOC[ioc][0]
    return code_or_name


def _iso2_flag(iso2: str) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


def country_flag(code_or_name: str | None) -> str:
    """IOC/ISO2/英文名 → 旗帜 emoji；未识别或不适用返回空串."""
    ioc = _resolve_ioc(code_or_name)
    if ioc:
        iso2 = IOC[ioc][1]
        return _iso2_flag(iso2) if iso2 else ""
    s = (code_or_name or "").strip()
    if len(s) == 2 and s.isalpha():
        return _iso2_flag(s)
    return ""
