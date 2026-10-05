"""Current global editorial time wording and match-footage defaults."""
import re

DAYPARTS = ("夜里", "凌晨", "清晨", "早上", "上午", "中午", "下午", "傍晚", "晚上", "深夜", "夜场")
NATURAL_TIME_RULE = "全栏目使用已核实的北京时间日期和自然时段，不强制具体小时或分钟"


def has_time_period(text: str) -> bool:
    return any(word in text for word in DAYPARTS) or bool(
        re.search(r"[一二三四五六七八九十两〇零百\d]+\s*[点时]", text))


def opening_context_problem(text: str) -> str | None:
    if "北京时间" not in text:
        return "没有北京时间口径"
    if not re.search(r"月[一二三四五六七八九十\d]+[号日]", text):
        return "没有比赛日期"
    if not has_time_period(text):
        return "没有已核实的开球时段"
    return None


def match_footage_problem(spec: dict) -> str | None:
    column = (spec.get("cover") or {}).get("eyebrow") or spec.get("_column") or spec.get("column")
    if column != "赛场之上":
        return None
    photos = [i + 1 for i, seg in enumerate(spec.get("segments") or [])
              if seg.get("image") and not (seg.get("stat_card") or seg.get("title_card"))]
    if photos:
        return (f"赛场之上正片默认使用比赛视频，不插入照片/任意静图：段 {photos}。"
                "需要数据卡或章节卡时使用 stat_card/title_card 的原生入口；特殊照片方案须另行确认。")
    return None
