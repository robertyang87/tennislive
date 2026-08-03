#!/usr/bin/env python3
"""三个平台的后台数据，读成同一种东西，再和仓库里的成片对起来。

小红书、抖音、微信视频号导出的表，列名、数值写法、时间格式没有一处相同：

    平台     标题列      时间            时长        比率      体裁
    小红书   笔记标题    2026年07月27日…  20.0        0.142     视频 / 图文
    抖音     作品名称    2026-07-27 …     20.340909   0.000000  1-3min视频 / 图文
    视频号   视频描述    2026/07/27       13.77秒     1.39%     （没有这一列）

给每家写一份脚本是走过的路 —— 第三家还没写就已经在复制粘贴第二家了。这里改成
一层适配：`PLATFORMS` 里声明列名怎么对应到规范字段，其余全部共用（读表、标题
对齐、漏斗、相关性、成片时长）。加第四家只要加一条 `Platform`。

## 各家给的东西不一样，报告按「有什么算什么」

    指标            小红书  抖音  视频号
    曝光 / CTR        ✓      ✓      ✗
    真完播率          ✗      ✓      ✓
    2s跳出 / 5s留存   ✗      ✓      ✗
    主页访问          ✗      ✓      ✗

所以漏斗那一节只有抖音出得来，曝光自检只有小红书和抖音出得来。**缺的那一节
会明说是「这个平台不给这一列」，不是「这个号没有数据」** —— 空结果先自证是
真空，两者在输出里长得一模一样。

## 均观看比例不是完播率

`平均播放时长 ÷ 成片时长` 是个**均值**，答不了「几个人看到了结尾」：一半人
两秒划走、一半人看完，和所有人都看一半，算出来一样。抖音和视频号直接给真
完播率，两边一比就知道它虚在哪：

    视频号   均观看比例中位 9.1%   真完播中位 2.9%   相关性 +0.96   虚高 2.2～6.4 倍
    抖音     均观看比例中位10.4%   真完播中位 2.0%   相关性 不稳     虚高 1.5～8.8 倍

结论是它**够用来排序、不能用来读水平**。小红书压根不给真完播率，所以那边的
真完播率无从得知 —— 空着，别拿另外两家的倍数去填。

## 平台之间不能互相代入

同一条内容在三边差 2～14 倍，而且**排序都不一样**：「大师赛为什么变两周」在
抖音是冠军（3066）、在视频号垫底（216）。人群、推荐机制、自动播放行为都不同。
所以横比那一节只报事实，不给「某平台更好」的结论。

用法：
    python tools/analyze_stats.py 笔记数据.xlsx
    python tools/analyze_stats.py 小红书.xlsx 抖音.xlsx 视频号.csv   # 带横比
    python tools/analyze_stats.py 抖音.xlsx --json out.json
"""

from __future__ import annotations

import csv
import io
import re
import statistics
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mp4_duration import mvhd_seconds  # noqa: E402  （同目录，纯 stdlib）

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# 标题对齐的四个数，都是从真实数据量出来的，别拍脑袋改：
#   0.706  抖音「网球为什么是黄色的」，发文时砍掉了「网球有故事」—— 要收
#   0.611  抖音「11 小时 5 分钟」图文，两个日期的版本只差 0.011 —— 分不清，要挡
#   0.500  抖音「三巨头」，三个候选并列 —— 要挡
#   0.812/0.750  抖音「金满贯」，两版挤在一起，靠发布日期挑中 7.22 那版
MIN_RATIO = 0.70
TIE_WINDOW = 0.08     # 分数差在这以内算并列，改按日期分
MIN_MARGIN = 0.10     # 和并列组之外的次优至少要拉开这么多
DATE_WINDOW = 2       # 发布日期和产物目录日期最多差几天

# 剔除「刚发出去还没跑完分发」的作品，只影响相关性一节。实测：抖音 5s完播率
# vs 播放量，全量 +0.46，剔掉当天发的变 +0.77 —— 新作品会把系数整个压平。
FRESH_HOURS = 24


# ---------------------------------------------------------------- 平台


@dataclass(frozen=True)
class Platform:
    """一个平台的导出表长什么样。加新平台只要加一条这个。"""

    name: str
    title_col: str                       # 也是识别用的列：出现它就认定是这家
    time_col: str
    fields: dict[str, str]               # 规范字段 -> 该平台的列名
    kind_col: str | None = None          # 体裁列；没有就全算视频
    title_carries_body: bool = False     # 标题列里是否跟着整段正文
    time_formats: tuple[str, ...] = ()

    def has(self, canonical: str) -> bool:
        return canonical in self.fields


# 规范字段名，报告一律用这套。某家没有的就不写进 fields，报告会说「不给这一列」。
PLATFORMS = (
    Platform(
        name="小红书", title_col="笔记标题", time_col="首次发布时间", kind_col="体裁",
        time_formats=("%Y年%m月%d日%H时%M分%S秒",),
        fields={
            "plays": "观看量", "exposure": "曝光", "cover_ctr": "封面点击率",
            "avg_watch": "人均观看时长", "likes": "点赞", "comments": "评论",
            "collects": "收藏", "shares": "分享", "follows": "涨粉",
        },
    ),
    Platform(
        name="抖音", title_col="作品名称", time_col="发布时间", kind_col="体裁",
        title_carries_body=True,
        time_formats=("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"),
        fields={
            "plays": "播放量", "cover_ctr": "封面点击率", "avg_watch": "平均播放时长",
            "true_completion": "完播率", "retain_5s": "5s完播率", "bounce_2s": "2s跳出率",
            "likes": "点赞量", "comments": "评论量", "collects": "收藏量",
            "shares": "分享量", "home_visits": "主页访问量", "follows": "粉丝增量",
        },
    ),
    Platform(
        # 抖音后台还有一个「视频数据」视图，只导 6 列：标题列叫`视频名称`（不是
        # `作品名称`），而且**没有真完播率、点赞、涨粉、体裁**。它是留存那三列的
        # 精简版，别和上面那份混为一谈——报告里凡是它给不出的指标都要明说是
        # 「这个视图不给」，不能印成 0。
        name="抖音·视频数据", title_col="视频名称", time_col="发布时间",
        title_carries_body=True,
        time_formats=("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"),
        fields={
            "plays": "播放量", "avg_watch": "平均播放时长",
            "retain_5s": "5s完播率", "bounce_2s": "2s跳出率",
        },
    ),
    Platform(
        # 视频号只给日期不给时刻，所以 `--fresh-hours` 在这家上按天生效。
        name="视频号", title_col="视频描述", time_col="发布时间",
        title_carries_body=True,
        time_formats=("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"),
        fields={
            "plays": "播放量", "avg_watch": "平均播放时长", "true_completion": "完播率",
            "likes": "喜欢", "comments": "评论量", "shares": "分享量",
            "follows": "关注量",
        },
    ),
)

INTERACTION = ("likes", "comments", "collects", "shares")


@dataclass
class Work:
    """一条作品，字段名和平台无关。"""

    platform: Platform
    title_raw: str
    published: datetime | None
    is_photo: bool
    values: dict[str, float | None]
    label: str = ""                      # 对上产物后换成干净的标题
    item: dict | None = field(default=None, repr=False)
    match_note: str = ""

    def get(self, key: str):
        return self.values.get(key)

    @property
    def interaction(self) -> float:
        return sum(self.values.get(k) or 0 for k in INTERACTION)


# ---------------------------------------------------------------- 读表


def _col_index(ref: str) -> int:
    n = 0
    for c in ref:
        if c.isalpha():
            n = n * 26 + (ord(c.upper()) - 64)
    return n - 1


def read_xlsx(path: Path) -> list[list[str]]:
    """xlsx 的第一张表 → 二维字符串表格。只用 stdlib。

    这个仓库没有 openpyxl，为一个分析脚本加依赖不值当。xlsx 就是个 zip：
    共享字符串在 sharedStrings.xml，单元格 t="s" 时存的是它在里面的下标。
    """
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{_NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
        sheets = sorted(n for n in z.namelist()
                        if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not sheets:
            raise SystemExit(f"{path} 里没有工作表")
        root = ElementTree.fromstring(z.read(sheets[0]))

    rows: list[list[str]] = []
    for row in root.iter(f"{_NS}row"):
        cells: dict[int, str] = {}
        for c in row.findall(f"{_NS}c"):
            ref = c.get("r") or ""
            idx = _col_index(ref) if ref else len(cells)
            if c.get("t") == "s":
                v = c.find(f"{_NS}v")
                text = shared[int(v.text)] if v is not None and v.text else ""
            elif c.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{_NS}t"))
            else:
                v = c.find(f"{_NS}v")
                text = v.text if v is not None and v.text else ""
            cells[idx] = text
        rows.append([cells.get(i, "") for i in range(max(cells) + 1 if cells else 0)])
    return rows


def read_csv(path: Path) -> list[list[str]]:
    """CSV。视频号导出带 BOM，用 utf-8-sig 剥掉，否则第一个列名会带个 \\ufeff
    前缀，平台识别当场失败 —— 而报错会说「找不到视频描述列」，看着像导错了表。
    """
    text = path.read_text(encoding="utf-8-sig")
    return [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]


def read_table(path: Path) -> list[list[str]]:
    if path.suffix.lower() in (".csv", ".tsv", ".txt"):
        return read_csv(path)
    return read_xlsx(path)


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def to_number(raw: str) -> float | None:
    """把一格文本读成数。

    三家的写法各不相同，而且**没有一家是纯数字**：抖音拿不到的格子写 `-`，
    视频号的时长写 `13.77秒`、比率写 `1.39%`。统一在这里处理，别让平台适配
    也管解析 —— 否则每加一家就多一份 `.replace('秒','')`。

    `-` 要读成缺失而不是 0：当成 0 会把中位数整个拖垮，而且看不出来。
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in {"-", "--", "—", "/", "N/A"}:
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    val = float(m.group())
    return val / 100 if "%" in s else val


def parse_time(raw: str, formats: tuple[str, ...]) -> datetime | None:
    s = (raw or "").strip()
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def detect(rows: list[list[str]]) -> tuple[Platform, int]:
    """认出这是哪家的表，以及表头在第几行。

    表头行**自己找**，不假定在第 0 行：小红书导出的第一行是「最多导出排序后前
    1000 条笔记」铺满整行的水印。写死行号的话，格式一变就整体错位，而且不报错
    —— 读出来的「标题」会是一串数字，看起来只是「数据怪怪的」。
    """
    for i, row in enumerate(rows[:20]):
        for plat in PLATFORMS:
            if plat.title_col in row:
                return plat, i
    raise SystemExit(
        "认不出这是哪家的导出表。已知的标题列："
        + "、".join(f"{p.name}={p.title_col}" for p in PLATFORMS))


def load(path: Path) -> tuple[Platform, list[Work]]:
    rows = read_table(path)
    plat, at = detect(rows)
    header = rows[at]
    works: list[Work] = []
    for row in rows[at + 1:]:
        rec = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header) if h}
        title = rec.get(plat.title_col, "").strip()
        if not title:
            continue
        kind = rec.get(plat.kind_col, "") if plat.kind_col else ""
        works.append(Work(
            platform=plat,
            title_raw=title,
            published=parse_time(rec.get(plat.time_col, ""), plat.time_formats),
            # 抖音的体裁写「1-3min视频」「3-5min视频」「图文」，小红书写「视频」
            # 「图文」，视频号没有这一列 —— 一律按「含不含『图文』」判。
            is_photo="图文" in kind,
            values={k: to_number(rec.get(col, "")) for k, col in plat.fields.items()},
            label=title.split("\n")[0][:28],
        ))
    return plat, works


# ------------------------------------------------------- 标题 → 成片


def normalize(text: str) -> str:
    """只留字母数字汉字。emoji、`｜`、空格全是装饰，去掉之后剩下的才是内容。"""
    return "".join(c for c in text if unicodedata.category(c)[0] in "LN")


def _dir_date(path: Path) -> date | None:
    for part in path.parts:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", part)
        if m:
            return date(*(int(x) for x in m.groups()))
    return None


def index_output(root: Path) -> list[dict]:
    """扫出所有「已生成的一篇内容」：标题 + 目录日期 + 同目录的成片。

    以 `xiaohongshu.txt` 为锚，它的**第一行就是发文标题** —— 让产物自证，
    不写死映射表。mp4 在同目录下找；找不到不是错（图文本来就没有）。
    """
    items = []
    for txt in sorted(root.rglob("xiaohongshu.txt")):
        try:
            lines = txt.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        title = next((ln.strip() for ln in lines if ln.strip()), "")
        if not title:
            continue
        mp4s = sorted(txt.parent.glob("*.mp4"))
        items.append({"title": title, "norm": normalize(title), "dir": txt.parent,
                      "date": _dir_date(txt.parent), "mp4": mp4s[0] if mp4s else None})
    return items


def match(work: Work, items: list[dict]) -> tuple[dict | None, str]:
    """把一条作品指到一个产物目录上。返回 (命中, 说明)。

    抖音和视频号的标题列里跟着整段正文，所以主判据是**前缀自证**：去掉装饰
    之后，它必然**以**那条内容的标题开头。不用猜标题在第几个空格处结束。
    小红书的标题列只有标题，前缀自证退化成精确匹配，同样成立。

    前缀对不上的（发文时改过标题）走模糊，卡三道：过阈值、并列组按日期分、
    和组外次优拉开差距。**任何一道没过都把原因说出来** —— 不然「没匹配上」
    和「压根没生成过」在输出里长得一模一样。
    """
    norm = normalize(work.title_raw)
    pre = [it for it in items if it["norm"] and norm.startswith(it["norm"])]
    if pre:
        # 命中多个时取最长的：`网球有故事｜11 小时 5 分钟` 比 `网球有故事｜11` 更具体
        best = max(pre, key=lambda it: len(it["norm"]))
        return best, f"前缀自证 {len(best['norm'])} 字"

    # 回退也按前缀比：拿开头**同样长度**的一段去比，而不是整条标题列 —— 那里面
    # 带着正文，长度差十几倍，相似度必然被压到 0.5 上下，好候选和坏候选一起沉底。
    # yellow-ball 就是这么漏掉的（0.52，看着像「真的不像」；按前缀比是 0.71）。
    scored = sorted(((SequenceMatcher(None, norm[:len(it["norm"])], it["norm"]).ratio(), it)
                     for it in items if it["norm"]), key=lambda x: x[0], reverse=True)
    if not scored:
        return None, "output/ 下没有任何 xiaohongshu.txt"
    top, item = scored[0]
    if top < MIN_RATIO:
        return None, f"前缀对不上；最像的「{item['title']}」也只有 {top:.2f}"

    tied = [it for s, it in scored if top - s <= TIE_WINDOW]
    if len(tied) > 1:
        picked = _nearest_by_date(work, tied)
        if picked is None:
            return None, (f"{top:.2f} 有 {len(tied)} 个候选分不出："
                          + " / ".join(it["title"] for it in tied[:3]))
        item = picked
    rest = [s for s, _ in scored if top - s > TIE_WINDOW]
    if rest and top - rest[0] < MIN_MARGIN:
        return None, f"{top:.2f} 和次优 {rest[0]:.2f} 拉不开（要求差 {MIN_MARGIN}）"
    if work.published and item["date"]:
        gap = abs((work.published.date() - item["date"]).days)
        if gap > DATE_WINDOW:
            return None, f"最像的是「{item['title']}」({top:.2f}) 但日期差 {gap} 天"
    return item, f"模糊 {top:.2f}"


def _nearest_by_date(work: Work, cands: list[dict]) -> dict | None:
    """并列候选按「发布日期离产物目录日期最近」挑，一样近就返回 None。

    同一个选题重跑过几版时（金满贯 7.22 / 7.25），分数会挤在一起，这时候
    日期是唯一能分开它们的东西。分不开就老实认输，不是随手挑第一个 ——
    错配比不匹配糟得多，它不出现在「未匹配」一节里，没人会去查。
    """
    if not work.published:
        return None
    dated = [c for c in cands if c["date"]]
    if not dated:
        return None
    gaps = sorted((abs((work.published.date() - c["date"]).days), i, c)
                  for i, c in enumerate(dated))
    if len(gaps) > 1 and gaps[0][0] == gaps[1][0]:
        return None
    return gaps[0][2]


def attach(works: list[Work], items: list[dict]) -> None:
    """给每条作品对齐产物，并把显示名换成干净的标题。

    抖音/视频号的标题列是标题接整段正文，直接截断会把正文头几个字带进表里
    （`…十届温网十个女冠军 同样十届温网，女`）。
    """
    for w in works:
        hit, why = match(w, items)
        w.item, w.match_note = hit, why
        if hit:
            w.label = hit["title"]
        elif w.platform.title_carries_body:
            w.label = w.title_raw.split("\n")[0][:26] + "…"


def duration_of(work: Work) -> float | None:
    if not (work.item and work.item["mp4"]):
        return None
    try:
        return mvhd_seconds(work.item["mp4"].read_bytes())
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- 工具


def median(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def pearson(xs, ys) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return num / den if den else 0.0


def fmt(x, spec="{:.0f}", dash="—") -> str:
    return dash if x is None else spec.format(x)


def width(s) -> int:
    """中文按两格算，不然表格永远对不齐。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def table(rows: list[list[str]], heads: list[str]) -> str:
    cols = list(zip(*([heads] + rows))) if rows else [[h] for h in heads]
    widths = [max(width(c) for c in col) for col in cols]
    out = []
    for i, row in enumerate([heads] + rows):
        cells = []
        for j, c in enumerate(row):
            pad = " " * (widths[j] - width(c))
            cells.append(pad + str(c) if j else str(c) + pad)
        out.append("  ".join(cells))
        if i == 0:
            out.append("  ".join("-" * w for w in widths))
    return "\n".join(out)


def fresh_cutoff(works: list[Work], hours: int) -> datetime | None:
    latest = max((w.published for w in works if w.published), default=None)
    return latest - timedelta(hours=hours) if latest else None
