# 「推广费」：500/250 唯一能买人的那条规则 —— 选题调研

> 2026-09-16 查。账号所有者定的选题：辛纳去北京、阿卡去东京，同周同级别，
> 讲这条规则本身。**片子里一次都不断言谁拿了钱**（见下「不许写的话」）。

## 一、规则原文（一手，两版都拉了）

**2026 版第一章 1.16 Promotional Fees**（2024 版是 **1.15**，节号变了是因为
2026 在前面插了一节 `1.15 Special Events - Exhibitions`）：

> A. Except as expressly permitted in subsection B below, a player shall not
> accept money or anything of value that is given from any source, directly or
> indirectly, to influence or assure his competing in any ATP Tour tournament,
> or ATP Challenger Tour tournaments, other than prize money unless authorized
> by ATP.
>
> B. **ATP Tour 500 and ATP Tour 250 tournaments have the option to offer fees
> for promotional services.** No other ATP Tour or ATP Challenger Tour
> tournament owner, operator, sponsor or agent is permitted to offer, give or
> pay money or anything of value, nor shall the tournament permit any other
> person or entity to offer, give or pay money or anything of value to a player,
> directly or indirectly, to influence or assure a player's competing in a
> tournament, other than prize money, unless authorized to do so by ATP.

⭐ **2024 与 2026 逐字相同，828 字符对 828 字符**（抹平 PDF 断词连字符后做的
SequenceMatcher，零个 opcode 不是 equal）。罚则金额也完全一致。
——CLAUDE.md「判历史事件要用当年那本规则书 / 跨年份要两本都拉」，这次比出来的
结论是**没改**，但这个结论是量出来的，不是假设的。

⚠️ **规则书里没有「appearance fee（出场费）」这个词**——2024 与 2026 全本各 0 处。
正式名字是 **Promotional Fees（推广费）/ fees for promotional services（推广服务费）**。
所有人都叫它出场费，规则书偏偏不这么叫。

## 二、罚则与执法（2026 版第八章 The Code · C. Promotional Fees）

第八章那一版措辞更宽，多一个词：`to influence or assure **or entice**`（引诱）。

**罚球员**（Prohibited Promotional Fees）：

| 级别 | 罚款上限 |
|---|---|
| 挑战赛 | $20,000 |
| ATP 250 | $30,000 |
| ATP 500 | $40,000 |
| **ATP 大师赛 1000** | **$60,000** |

外加**追缴该笔款项的价值**，并可停赛最多三年；**连续违规罚款上限每次翻倍（+100%）**。

⭐ 这张表本身就是一屏：**罚得最狠的是大师赛——因为那一级本来就一分都不许给。**

**罚赛事**：罚款最高 **$100,000** ＋ 追缴该笔补偿的金额或价值 ＋ **终止会籍** ＋
没收此前已付给 ATP 的全部款项。

**查账权**：ATP CEO 或规则与竞赛高级副总裁认为某站可能违规时，**赛事方必须应要求
交出其掌握的全部相关记录的查阅权和复印件**；没有记录的，要出具**详述事实的宣誓书**。
拒不提供，罚最高 $100,000 ＋ 终止会籍。

⭐ 落点：**罚则精确到万位、还有查账权和宣誓书——说明这事真会被查；可给了多少，
从不披露。**

## 三、这一周的事实

- **2026-09-30 至 10-06**，辛纳在**北京**（中网，ATP500），阿卡在**东京**
  （日本公开赛，ATP500）——**同一周、同一级别、两个城市**
- 北京前十来了 7 个：辛纳（卫冕冠军、世界第一）、兹维列夫、德约
- 东京：阿卡卫冕，还有谢尔顿、弗里茨、穆塞蒂、鲁德等
- 德约时隔 11 年重返中网，六进六冠 29 胜 0 负（另一条选题，这条片子里最多一句带过）

## 四、⛔ 不许写的话（这条是这次选题的全部风险）

**不能说辛纳/阿卡「走的是出场费」。** 查下来：

- **没有任何一手报道**把出场费和这两人这两站连起来
- 流传的数字（费德勒约 110 万、纳达尔/德约约 90 万一站）全部出自网球博客和论坛，
  措辞是 rumored / estimated，**找不到一手出处**
- 中文只找到一篇旧深度稿一句「有少数顶尖球员被东京的高额出场费所吸引」——
  **泛指、不点名、不是今年**
- 出场费 rarely disclosed 是常态

**而且有个说得通的竞技解释，我连它都没排除**：阿卡 2024 在北京夺冠、**2025 改去
东京并夺冠**、2026 回东京是**卫冕**；他本人公开说过「我想去一个不同的地方，一个
我从来没打过的球场」。
——CLAUDE.md「『排除了 A 和 B』不等于『就是 C』」正是这个形状。

**片子的主语是规则，不是这两个人。** 他们只是那一周同时出现在两个城市的事实。

## 五、取数踩的坑（下次别重走）

- ⚠️ **CLAUDE.md 里「ATP 规则书 WebFetch 403、带浏览器 UA 的 curl 能过」已经过期**：
  现在 atptour.com 整站是 **Cloudflare 挑战**（返回 `<title>Just a moment...`），
  四种请求头、无头 Chromium 都过不去
- ⚠️ 无头 Chromium 第一次报 `ERR_CERT_AUTHORITY_INVALID`，真因是**代理 CA 没进
  NSS 库**（`/root/.pki/nssdb` 里一张证书都没有）。修法：
  `apt-get install -y libnss3-tools`，把 `/root/.ccr/ca-bundle.crt` 拆开，
  自签根（issuer == subject）逐张 `certutil -A -t "C,,"` 导入。装完 cert 错消失，
  **但 Cloudflare 照样挡**——这两件事是两个问题，别混
- ⭐ **能走通的是 Wayback**：
  `https://web.archive.org/cdx/search/cdx?url=atptour.com/-/media/files/rulebook/2026*&output=text&fl=timestamp,original,statuscode,length&collapse=urlkey`
  列出全部快照，再用 `https://web.archive.org/web/<ts>id_/<原始 URL>` 取原始 PDF。
  2026 全本（27apr26）、第一章、以及**两份 `26rulebook-changes_*.pdf` 改动说明**都在
- ⚠️ archive.org 第一次返回 **429 限流**，长得和「没有」一模一样——歇几分钟再来
- ⚠️ ITF 站上镜像着一份 **2024** 版 ATP 规则书
  （`itftennis.com/media/11845/2024-rulebook-atp-update.pdf`），没有 Cloudflare，
  200 直出；但只有 2024 那一年
- ⚠️ 比 PDF 抽出来的条文前**必须抹平断词连字符**（`-\n`），否则
  `promotional services` 在 2026 版只数得出 1 处、2024 版数出多处，
  看起来像改了规则，其实只是换行位置不同
