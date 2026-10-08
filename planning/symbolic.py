"""A three-state, one-cube planning baseline using preconditions and effects."""

from collections import deque
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Goal:
    action: str
    object: str
    target: str | None = None

    def __post_init__(self):
        if self.action not in ("pick", "place") or self.object != "red_cube":
            raise ValueError("Supported goals are pick/place for red_cube.")
        expected_target = "green_platform" if self.action == "place" else None
        if self.target != expected_target:
            raise ValueError("Place requires green_platform; pick has no target.")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class WorldState:
    """The cube has one support/location; a held cube implies an occupied gripper."""

    cube_location: str

    def __post_init__(self):
        if self.cube_location not in ("table", "gripper", "green_platform"):
            raise ValueError("Unknown cube location in this planning domain.")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SkillCall:
    skill: str
    object: str
    target: str | None = None

    def __post_init__(self):
        Goal(self.skill, self.object, self.target)

    def to_dict(self):
        return asdict(self)


def goal_satisfied(goal: Goal, state: WorldState) -> bool:
    expected = "gripper" if goal.action == "pick" else "green_platform"
    return state.cube_location == expected


def apply_skill(state: WorldState, call: SkillCall) -> WorldState:
    """Predict an operator effect; the executor calls this only after physical verification."""
    if call.skill == "pick":
        if state.cube_location == "gripper":
            raise ValueError("Pick requires an empty gripper and a supported cube.")
        return WorldState("gripper")
    if state.cube_location != "gripper":
        raise ValueError("Place requires holding red_cube.")
    return WorldState("green_platform")


def plan_goal(goal: Goal, initial_state: WorldState) -> list[SkillCall]:
    """Find the shortest valid skill sequence in this deliberately small domain."""
    operators = (SkillCall("pick", "red_cube"), SkillCall("place", "red_cube", "green_platform"))
    frontier = deque([(initial_state, [])])
    visited = {initial_state}
    while frontier:
        state, plan = frontier.popleft()
        if goal_satisfied(goal, state):
            return plan
        for operator in operators:
            try:
                successor = apply_skill(state, operator)
            except ValueError:
                continue
            if successor not in visited:
                visited.add(successor)
                frontier.append((successor, plan + [operator]))
    raise ValueError("No plan reaches the requested goal from the given state.")
