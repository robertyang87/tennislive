"""AI 生成合成内容的显式标识——所有发布线共用这一处。

**来路（2026-08-14）**：《人工智能生成合成内容标识办法》2025-09-01 已经生效，
《互联网信息服务深度合成管理规定》同样适用。这个号的旁白**全部是合成语音**
（edge-tts / Azure / MiniMax），竖版封面的人物是 AI 抠图（rembg
`isnet-general-use`）——而扫下来 specs、渲染路径、推送正文、`xhs.txt`
**一个字的声明都没有**。这个账号 2026-08-06 已经被视频号处理过一次
（「二次创作信息增量不足」），带着未声明的合成管线属于「可能直接导致停摆」
那一类风险，所以这一条不是排期问题。

三个决定，每个都是判据不是口味：

- **放在正文末尾，不放开头。** 正文最贵的是前几行（本仓库「最硬的那个事实
  放第 ① 屏」量过：看到结尾的人只有 2~3%，而 2 秒跳出就走掉近三成），标识
  抢开头等于拿最贵的那块地放一句谁都不为它点进来的话。办法要求的是**显式、
  可感知**，没有要求它排第一。
- **插在末尾那串 tag **之前**。** `push_reel.cut_at_tags` 的判据是「最后一个
  `#` 标签所在的行就是终点，后面的一概不发」——标识写在 tag 后面会被它整段
  砍掉，**而且不吭声**（那正是 `cut_at_tags` 存在的理由）。写在 tag 之前，
  它既是正文的最后一段，又天然活得下来。
- **措辞里留着「AI 生成」这四个字**（办法和 GB 45438-2025 用的就是这个词）。
  这四个字撞上 `knowledge_visual_qa.FORBIDDEN_PRODUCTION_LABELS`——那张表本来
  拦的是「生产脚手架的字漏到卡片上」，净效果却是**把合规标识要用的词主动挡在
  画面之外**。那道闸没有删，只是遮掉标识本身再扫（见
  `knowledge_visual_qa._production_label_hit`）。

⚠️ **标识加在「发」的那一步，不加在「写」的那一步**——和
`drop_dead_copy_button` 那道闸是同一个形状（本仓库为「闸装在渲的那一步」栽过
一次，见 CLAUDE.md「第四次，方向反过来了」）。理由有两个：
`specs/reels/<slug>.xhs.txt` 是**手写**的，指望每份都记得写一行等于没有标识；
而所有的出口（复制页、微信正文、公众号图片消息）都要先把文案切成
标题 + 正文，**那个切法就是这条线唯一的收口**。判据因此可以自己推导，
不用维护一张会过期的名单：见 `test_把文案切成标题正文的路径都要带AI标识`。

⚠️ **措辞里的「（如有）」不是含糊，是准确。** 这一份文本三条线共用：竖版短片
和解说片有合成旁白，知识帖和内容雷达是图文帖、根本没有旁白。写死「本片旁白
为合成语音」对图文帖是一句**假话**，而本仓库对「一句站不住的话赔上整个号的
可信度」有过明确判据（CLAUDE.md「第一是精准，第二是引爆。顺序不能倒」）。
"""

from __future__ import annotations

from .hashtags import hashtag_count

# 正文末尾那一行。措辞的三个约束都写在模块 docstring 里：
# ① 「AI 生成」四个字照办法的原词写，别改成「AI 辅助生成」——那不含「AI 生成」
#    这个子串，`FORBIDDEN_PRODUCTION_LABELS` 那道闸就再也验不到，收窄它的判据
#    会变成一条恒真的绿灯；
# ② 「旁白」是主要事实（这个号的旁白全部是合成语音），排在画面前面；
# ③ 45 字，插进去连空行一共 47 字位——小红书正文 1000 字那道硬闸是平台定的，
#    标识占掉的每一个字都从正文的预算里出，所以它必须短。
AI_DISCLOSURE = "⚙️ AI 生成合成内容标识：旁白（如有）为 AI 合成语音，部分画面经 AI 工具处理。"

# 插进正文时占掉的字数（含它前面那个空行）。`push_reel.split_copy` 拿它把
# 1000 字的平台上限折算成「正文本身还能写多少」，报错里也要印出来——不然作者
# 看到的是一个对不上自己文案长度的数字。
DISCLOSURE_COST = len(AI_DISCLOSURE) + 2


def has_ai_disclosure(text: str) -> bool:
    """这段文案里已经有标识了吗。

    **幂等靠它**：标识加在每一个出口上（复制页一处、微信正文一处），而
    `push_reel` 的两个 stage 会让同一段文字先后过两次——不判一下就会印两遍，
    而「同一段印两遍」正是这条推送线修过的老毛病。
    """
    return AI_DISCLOSURE in text


def with_ai_disclosure(text: str) -> str:
    """把标识插进正文末尾——在末尾那串 tag **之前**。

    为什么不是直接 append：`cut_at_tags` 会把最后一个 tag 行之后的一切砍掉，
    append 上去的标识**会被安静地吃掉**。而 tag 本来就是小红书文案的收尾，
    标识排在它前面，读起来也正是「正文的最后一段」。

    空文案原样返回：没有正文就没有要标识的内容，而 `push_reel.main` 对空文案
    本来就会当场报错。这里凭空造一段只会让那道闸看起来通过了。
    """
    if not text.strip() or has_ai_disclosure(text):
        return text
    lines = text.rstrip().splitlines()
    # 末尾那串 tag 的第一行在哪儿：从最后一个带 tag 的行往回走，
    # 一路吃掉 tag 行和它们中间的空行。判据和 `cut_at_tags` 是同一个
    # （「最后一个 `#` 标签所在的行就是终点」），别另立一套。
    last = max((i for i, line in enumerate(lines) if hashtag_count(line)), default=-1)
    first = len(lines)
    if last >= 0:
        first = last
        while first - 1 >= 0 and (
            not lines[first - 1].strip() or hashtag_count(lines[first - 1])
        ):
            first -= 1
    head = "\n".join(lines[:first]).rstrip()
    tail = "\n".join(lines[first:]).strip()
    return "\n\n".join(part for part in (head, AI_DISCLOSURE, tail) if part)


def mask_ai_disclosure(text: str) -> str:
    """扫「有没有不该出现的词」之前，先把标识本身遮掉。

    和译名那条判据一个手法（「先把文中所有规范名遮掉，再找剩下的近似串」）：
    标识里写着「AI 生成」，而那正是某些扫描器要拦的词。不遮就会把**合规动作**
    判成**违规内容**——扩大化的判据不吭声，它只会让下一个人把标识删掉。

    只遮**这一整句**，不遮里面的任何片段：判据宁可窄，不可宽。谁把标识拆成
    几个元素分开渲，遮不住是对的——那时候它本来就该被人看一眼。
    """
    return text.replace(" ".join(AI_DISCLOSURE.split()), " ").replace(
        AI_DISCLOSURE, " "
    )
