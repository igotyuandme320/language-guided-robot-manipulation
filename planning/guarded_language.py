"""Conservative literal checks for this two-action demo, not general semantics."""

from dataclasses import dataclass
import re
import unicodedata

from .language import parse_instruction
from .llm import RejectedInstruction, infer_goal
from .symbolic import Goal


@dataclass(frozen=True)
class RequestHints:
    placement_requested: bool


def check_request(instruction: str) -> RequestHints:
    """Require explicit scene names and reject a limited list of contradictions."""
    if not instruction.strip() or len(instruction) > 512:
        raise RejectedInstruction("Instruction must contain 1–512 characters.")
    text = unicodedata.normalize("NFKC", instruction).casefold().replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    if re.search(r"\b(?:not|never|without|don't|dont|cannot|can't)\b|不|别|勿|禁止|无需", text):
        raise RejectedInstruction("Negated or action-forbidding requests are unsupported.")
    if re.search(r"\b(?:blue|yellow|orange|purple|black|white)\b|蓝色|黄色|黑色|白色|紫色", text):
        raise RejectedInstruction("An unsupported color/entity is named.")
    if re.search(r"\bgreen (?:cube|block)\b|\bred (?:platform|target)\b|绿色(?:小)?方块|红色平台", text):
        raise RejectedInstruction("The named object or destination is not in this scene.")
    if re.search(r"\b(?:roll|throw|push|rotate|open|close|drawer|stack|swap)\b|推|滚|扔|旋转|抽屉|堆叠", text):
        raise RejectedInstruction("An unsupported action or object is named.")
    if re.search(r"\b(?:hand|give|pass)\s+(?:it|(?:the )?red (?:cube|block)|me|you)\b|\bhandover\b|\bhand over\b|递给|交给", text):
        raise RejectedInstruction("Handover is not a supported skill.")
    if re.search(r"\b(?:door|if|unless|until)\b|如果|除非|直到|开门|关门|门打开", text):
        raise RejectedInstruction("Conditional execution and door observations are unsupported.")
    if re.search(r"\b(?:beside|near|under|behind|between)\b|旁边|下面|附近|后面", text):
        raise RejectedInstruction("Only placement on the green platform is supported.")
    if not re.search(r"\bred (?:small |little )?(?:cube|block)\b|红色(?:小)?方块", text):
        raise RejectedInstruction("Name the red cube explicitly; references are not resolved.")
    placement = bool(re.search(r"\b(?:put|place|move|transfer|relocate)\b|放|搬|移", text))
    pick = bool(re.search(r"\b(?:pick|lift|grab|hold|take|raise)\b|拿|抓|举|提", text))
    if not (placement or pick):
        raise RejectedInstruction("No supported pick or place action is explicit.")
    if placement and not re.search(r"\bgreen (?:platform|target)\b|绿色平台", text):
        raise RejectedInstruction("Name the green platform explicitly for placement.")
    if placement and re.search(r"\b(?:keep|continue)\b.*\b(?:holding|hold|gripping)\b|(?:继续|一直|保持).*(?:握|抓|拿|夹)", text):
        raise RejectedInstruction("The place skill releases the cube; continued holding is unsupported.")
    if placement and re.search(r"\b(?:edge|corner)\b|边缘|角落", text):
        raise RejectedInstruction("The place skill targets the platform center, not an edge or corner.")
    return RequestHints(placement_requested=placement)


def check_goal(hints: RequestHints, goal: Goal) -> Goal:
    """Reject a conflicting model action; never rewrite its proposed goal."""
    expected_action = "place" if hints.placement_requested else "pick"
    if goal.action != expected_action:
        raise RejectedInstruction(f"Proposed action {goal.action!r} conflicts with explicit {expected_action!r} request.")
    return goal


def infer_guarded(instruction: str, timeout: float = 120.0) -> tuple[Goal, dict]:
    """Known templates use rules; other requests require a valid model proposal."""
    hints = check_request(instruction)
    try:
        goal = parse_instruction(instruction)
    except ValueError:
        goal, metadata = infer_goal(instruction, timeout)
        return check_goal(hints, goal), {"backend": "guarded", "source": "llm", "model": metadata}
    return check_goal(hints, goal), {"backend": "guarded", "source": "rules"}
