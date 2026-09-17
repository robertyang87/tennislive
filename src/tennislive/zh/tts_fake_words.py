"""合成器会念错的「假词」——两条产线共用的一张表。

来路：`voice_NN.words.json` 是合成器**自己报的切词**，`text` 字段就是它认为的
一个词。有些串会被它切成一个**真实存在、但读音不同**的词典词，而渲出来一个
像素都看不出来——只有耳朵和 words.json 知道：

- 「规则书写着」→ `规则 ｜ 书写 ｜ 着`，「书写」念 shūxiě
- 「六行里有五行是同一个名字」→ `六行里 ｜ 有 ｜ 五行 ｜ 是`，「五行」念 wǔxíng
  （金木水火土），而「六行里」念对了（háng）——账号所有者 2026-09-17 听出来的：
  「配音里六行里有五行，其中五行的 tts 读音错了，以后要避免这种情况」

⚠️ 这张表原来只活在 `tests/test_explainer.py` 里，扫描面只有解说片的
`_SCRIPTS`/`_OPENINGS`；赛场之上／网球有故事的 spec 旁白**一个字都不扫**，
于是「五行」从 `--dry-run`、`--check-narration`、全量测试一路绿到推送。
「判据的扫描面，往往比规矩的适用面窄」——这是它的又一个实例。现在两条线读同一张表：
解说片那头照旧在 pytest 里扫脚本，竖版短片那头进 `spec_wording.check_spec_wording`
（`--dry-run` 0.2 秒就红），渲完 `--check-narration` 的切词报告再按 token 对一遍。

**这张表只收「读音真的变了」的、在 words.json 里量到过的串**，不收「重音偏了」
那一档（人名内部切错、单字铺开）——一条天天误报的闸会被人写豁免压掉。

修法只有一条可靠：**把歧义本身去掉**，不是去猜切词器——换句式让那两个字不再相邻。
"""
from __future__ import annotations

#: spec / 脚本里的**文本串** → 为什么错、怎么改。命中即红。
FAKE_WORDS: dict[str, str] = {
    "规则书写": "「书写」念 shūxiě，意思全变——写「规则书里写着」",
    "间接给": "「间」落单念 jiān（「间接」是 jiàn）——把「给」挪走",
    "五行": ("「五行」是个词典词，念 wǔxíng（金木水火土）——别让数字直接顶着「行」，"
             "写「有五个是同一个名字」"),
}

#: 合成器报出来的**token** → 为什么错。渲完读 `voice_NN.words.json` 对一遍用的：
#: 上面那张表按原文扫（拦在渲之前），这张按切词扫（渲完闭环）。两张不一样：
#: 「规则书写着」出问题的 token 是「书写」，不是原文里那四个字。
FAKE_TOKENS: dict[str, str] = {
    "书写": "「规则书写」被切成「规则 ｜ 书写」，念 shūxiě",
    "接给": "「间接给」被切成「间 ｜ 接给」，「间」落单念 jiān",
    "五行": "念成了 wǔxíng（金木水火土），不是「五 行（háng）」",
}


def fake_word_hits(text: str) -> list[tuple[str, str]]:
    """原文里命中的 (串, 为什么)。"""
    return [(pat, why) for pat, why in FAKE_WORDS.items() if pat in (text or "")]


def fake_token_hits(tokens) -> list[tuple[str, str]]:
    """切词报告里命中的 (token, 为什么)。"""
    return [(tok, FAKE_TOKENS[tok]) for tok in tokens if tok in FAKE_TOKENS]
