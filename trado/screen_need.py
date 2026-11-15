"""Decide whether a spoken question is about the screen, so a screenshot is only sent when it can help.

The rule leans cautious: when in doubt, the screenshot IS sent. It skips one only when the question is clearly general
knowledge (for example "What is a SIP?") or an obvious follow-up to the previous answer. Say "look at my screen" and it
is always sent. TRADO_SCREEN_MODE=always turns the rule off.
"""

import re

# Words that mean "I'm talking about what is on the screen".
_ABOUT_THE_SCREEN = re.compile(
    r"\b(?:screen|screenshot|page|window|tab|website|chart|graph|candles?|candlesticks?|button|field|box|form|menu|"
    r"dropdown|icon|link|toolbar|panel|dashboard|screener|watchlist|table|"
    r"look|looks|looking|see|seeing|show|showing|shown|display|displayed|visible|highlight|highlighted|"
    r"select|selected|click|tap|point|pointing|here|these|those|this|above|below)\b"
    r"|\bwhere (?:is|are)\b|\bwhich (?:button|option|field|tab|menu|one)\b|\bon the (?:left|right)\b|\bat the (?:top|bottom)\b"
    # parts of a table or list, colours and labels: things you can only mean by looking
    r"|\b(?:row|rows|column|columns|cell|cells|label|labelled|caption|written|says|reads|greyed|grayed|disabled|"
    r"red|green|blue|yellow|orange|purple|grey|gray)\b"
    r"|\b(?:first|second|third|fourth|fifth|last|next|previous) (?:one|row|column|item|option|line|number|value|tab|entry)\b"
    r"|\b(?:next to|beside|near the|under the|over there)\b|(?<!is )(?<!are )\bthere\b"
    # live or personal numbers can only come from the screen
    r"|\b(?:current|currently|right now|latest|live|real-time|real time|so far)\b"
    r"|\bmy (?:balance|holdings?|portfolio|positions?|orders?|profit|loss|p&l|pnl|margin|funds?|watchlist|account|"
    r"statement|returns?|investments?|stocks?|shares?)\b",
    re.I,
)
# "that" and "it" usually mean the previous answer once there is a conversation, and the screen when there isn't.
_THAT_OR_IT = re.compile(r"\b(?:that|it)\b", re.I)
# Question shapes that are general knowledge.
_GENERAL = re.compile(
    r"^\W*(?:(?:and|so|ok|okay|now|then|also|but)\W+)*"
    r"(?:what(?:'s|s| is| are| was| were| does| do| did)\b|how (?:does|do|is|are|can|to|much|many|long|often)\b|"
    r"why (?:is|are|do|does|did)\b|explain\b|define\b|describe\b|tell me (?:about|what|how|why)\b|"
    r"can you (?:explain|tell|define)\b|could you (?:explain|tell)\b|difference\b|meaning\b|who\b|when\b|which\b|"
    r"(?:is|are) (?:a|an|the|there|all)\b|should\b|will\b|give me\b|"
    r"(?:do|does|can|could|would|did) (?:i|you|we|people|investors|a|an|the|every|it)\b|what if\b|if i\b)",
    re.I,
)


def needs_screenshot(question: str, has_history: bool = False) -> bool:
    """True if a screenshot should be sent with this question."""
    text = question.strip()
    if not text:
        return True
    if _ABOUT_THE_SCREEN.search(text):
        return True
    if _THAT_OR_IT.search(text) and not has_history:
        return True  # "what does that mean?" with no earlier answer can only mean something on the screen
    if _GENERAL.match(text):
        return False
    return not (has_history and len(text.split()) <= 12)  # a short follow-up with no screen words
