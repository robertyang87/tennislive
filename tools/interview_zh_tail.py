"""Shared, conservative Chinese subtitle tail check."""

_BAD_TAIL = tuple("的地得和跟与在把被为从对而或让就")


def has_dangling_tail(text: str) -> bool:
    text = text.rstrip()
    # Rybakina US Open QF: 成就 is the complete noun “achievement”, not
    # the dangling adverb 就. Keep the exception lexical and narrow.
    # 对 can complete a result predicate ("没打对"), not only introduce
    # an unfinished prepositional phrase. Do not allow bare 对 or 面对.
    # 得 in 觉得/记得/值得/懂得/晓得 is part of the verb itself, not the
    # structural particle. Tien Laver Cup 2026: "Yeah, I mean, I think" →
    # 「是啊，我想说，我觉得」 was rejected three times and killed the run.
    complete = ("成就", "打对", "做对", "答对", "猜对", "说得对", "做得对", "不对",
                "觉得", "记得", "值得", "懂得", "晓得")
    return text.endswith(_BAD_TAIL) and not text.endswith(complete)
