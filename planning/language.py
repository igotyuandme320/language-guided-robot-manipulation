"""Strict English/Chinese command templates, a baseline before any LLM adapter."""

import re
import unicodedata

from .symbolic import Goal

_PICK_PATTERNS = (
    r"(?:please )?(?:pick(?: up)?|lift|grab) (?:the )?red (?:cube|block)",
    r"(?:请)?(?:拿起|抓起)红色方块",
)
_PLACE_PATTERNS = (
    r"(?:please )?(?:put|place) (?:the )?red (?:cube|block) (?:on|onto) (?:the )?green (?:platform|target)",
    r"(?:请)?(?:把|将)?红色方块(?:放到|放在)绿色平台(?:上)?",
)


def parse_instruction(instruction: str) -> Goal:
    """Match the whole request so unknown qualifiers or extra actions are rejected."""
    text = unicodedata.normalize("NFKC", instruction).casefold().strip().rstrip(".!。！")
    text = re.sub(r"\s+", " ", text).strip()
    if any(re.fullmatch(pattern, text) for pattern in _PICK_PATTERNS):
        return Goal("pick", "red_cube")
    if any(re.fullmatch(pattern, text) for pattern in _PLACE_PATTERNS):
        return Goal("place", "red_cube", "green_platform")
    raise ValueError(
        "Unsupported instruction. Try 'pick up the red cube' or "
        "'put the red cube on the green platform' (拿起红色方块 / 把红色方块放到绿色平台上)."
    )
