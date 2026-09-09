"""Shared, conservative Chinese subtitle tail check."""

_BAD_TAIL = tuple("的地得和跟与在把被为从对而或让就")


def has_dangling_tail(text: str) -> bool:
    text = text.rstrip()
    # Rybakina US Open QF: 成就 is the complete noun “achievement”, not
    # the dangling adverb 就. Keep the exception lexical and narrow.
    return text.endswith(_BAD_TAIL) and not text.endswith("成就")
