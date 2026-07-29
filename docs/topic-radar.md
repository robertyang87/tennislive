# 选题雷达：把每天的新闻提炼成选题

`flash-radar` 和 `topic-radar` 是两件事，共用同一批扫来的信号：

| | 出什么 | 形状 |
|---|---|---|
| `flash-radar` | 快讯候选 | 一条新闻 → 一张卡，讲「发生了什么」 |
| `topic-radar` | **选题候选** | **新闻钩子 + 底下压着的常青线**，`docs/newshook-topics.md` 那个形状 |

两步都跑在 `news-radar` 工作流里（每天 09:13 / 21:13 北京时间），各推一条微信。

---

## 机器做两件事，人做第三件

1. **聚类**——同一天里几家在报同一件事才算一个新闻点。
2. **对角度**——拿这一簇去撞 `research/topic_radar.ANGLES`，一张人工维护的表。
3. **核实和写稿**——人。**角度是对上的，事实一条都没核。**

### 聚类的判据：共享至少一个专名，且总共享词不少于两个

两个条件都要，各挡一类错：

- 只看专名 → 「Washington」能把一整周的比赛全并成一簇
- 只看词数 → 「breaks」「2026」这种满天飞的虚词凑够两个就成簇

实测两个假阳性，都是只满足一个条件时并出来的：

| 并错的两条 | 共享的是 | 并完撞上 |
|---|---|---|
| `Wimbledon ... breaks attendance record` + `Atmane gains Tiafoe revenge, breaks home hearts` | `breaks` | 屋顶与天气（`rain-free` 里的 rain） |
| `US Open Mixed Doubles entries` + `Shelton on 2026 season` | `2026` | 混双改制 |

**看着像模像样，全是错的。** 加上「必须共享专名」之后两个都不成簇，而真实的
7-25 那簇（Sinner/Djokovic 退赛蒙特利尔，5 家在报）照样成立。

两个配套细节，都是踩出来的：

- **句首那个词也算专名**。一开始为了躲「句首大写不代表专名」把 position 0
  排除了，结果 `Draper withdraws from Washington` 这种最常见的标题形状
  （主语打头）直接失去主判据
- **专名和普通词要用同一把尺切**。原来专名的正则把连字符算进词里
  （`Minaur-Boulter` 是一个 token），普通词的 `_WORD` 会切成两个——两边对不上，
  `proper & shared` 就会莫名其妙地空掉

### 对角度：触发词要在簇里至少两条标题上出现

不是「组里任何一处出现过」。差别很大：一簇里只有第一条带 `mixed` / `doubles`，
按「任何一处」就会判成「混双改制」——而那一簇本身就是并错的，角度再一叠，
错上加错。

**撞不上就不猜。** 没对上的簇进 `unmatched_clusters`，高频词进 `unmatched_terms`
——那是「该往 `ANGLES` 里补什么」的线索，不是失败。

⚠️ **那份清单的排序必须是确定的。** 第一版用 `Counter.most_common`，而在计数
全部相同时它按插入顺序返回，插入顺序又来自遍历 `set`——字符串的 set 顺序取决于
`PYTHONHASHSEED`，每个进程都不一样。本地过、CI 红就是这么来的；更糟的是这份
清单本来是给人看「该补什么角度」的，**每次随机取八个等于没写**。现在按
`(-次数, 词)` 排，并且不报聚类用的拼接词（`ballkidsquad` 这种人读起来是噪点）。
判据见 `test_该补什么角度那份清单必须是确定的`——拿四个不同的 `PYTHONHASHSEED`
各跑一遍，结果必须一模一样。

---

## 舆论热度：三个能查的证据，不是打分模型

| 证据 | 从哪来 | 权重 |
|---|---|---|
| `outlets` 几家在报 | 簇里不同来源的家数 | ×10，最重 |
| `days_running` 连着第几天 | 读昨天的 `topic_radar_queue.json` | ×6 |
| `trend_hits` 撞上几条大众热搜 | Google 每日热搜（4 个地区） | ×3，封顶 3 条 |

**热搜只当加成**。那一路是大众热搜，足球运动员和流行歌手都在里面，撞上说明
这件事溢出了网球圈；但它也最容易误配，不能靠它单独把一条没人报的东西顶上来。
对法是**拿专名取交集**，不是拿整句去 `in`——用整句会把 `open` 这种词配上一切。

---

## 媒体源：现状与缺口（2026-07-29 实测）

最近 5 天各源实际产出：

| 源 | 5 天合计 | 零产天数 |
|---|---|---|
| Google 热搜 US / HK / GB / AU | 各 50 | 0 |
| Top media（`tennis when:1d`） | 46 | 0 |
| ATP Tour | 43 | 0 |
| WTA | 16 | 0 |
| US Open | 2 | 3/5 |
| Wimbledon / Roland-Garros / Australian Open | **0** | **5/5** |

**三个大满贯零产是真空，而且是季节性的，不是查询坏了。** 直接打 Google News
的 RSS 验过：四个 `site:` 查询都返回 100 条，但最新一条分别是温网 **7/10**、
法网 **7/12**、澳网 **7/13**——赛季外它们就不发稿了，被 48 小时的新鲜度闸门
正常挡掉。**不用修**。

### 真正的缺口：一条中文源都没有

这个号的读者在中文平台上，而「是不是舆论热点」现在完全由英文媒体的家数决定。
微博热搜、虎扑、中文体育门户一条都没接——**中文那边炸了而英文没报的事，这套
现在一点都看不见**（郑钦文相关的讨论尤其明显）。

补哪些、怎么抓（有的没有公开 RSS），是需要定的事，不是我能替谁定的。

其他可以考虑的英文源：Tennis Majors、Ubitennis、Tennis365、Reddit r/tennis
（后者本身就是舆论热度的代理指标）。

---

## 用法

```bash
tennislive topic-radar --outdir output            # 默认 5 条候选，2 家在报算数
tennislive topic-radar --min-sources 3            # 收紧：三家在报才算
tennislive topic-radar --persist-days 3           # 往前看三天判断连续性
```

产物 `output/<日期>/topic_radar/topic_radar_queue.json` 自带诊断：
`news_signals` / `trend_signals` / `count` / `unmatched_clusters` / `unmatched_terms`
——**一条候选都没有时，能自己回答是「今天没热点」还是「热点都没撞上角度」**。
