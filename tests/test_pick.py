import torch

from skills.pick import PickSkill, PickPhase


skill = PickSkill()

ee = torch.tensor([0.0, 0.0, 0.0])
obj = torch.tensor([0.5, 0.0, 0.0])
lift = torch.tensor([0.5, 0.0, 0.3])


def step_until_phase(target_phase, ee_position, max_steps=100):
    for _ in range(max_steps):
        target, closed = skill.step(
            ee_position,
            obj,
            lift,
            dt=0.1,
        )

        if skill.phase == target_phase:
            return target, closed

    raise RuntimeError(f"Failed to reach {target_phase}")


print("start:", skill.phase)

step_until_phase(PickPhase.APPROACH_ABOVE, ee)
print("1:", skill.phase)

ee = torch.tensor([0.5, 0.0, 0.1])
step_until_phase(PickPhase.APPROACH_OBJECT, ee)
print("2:", skill.phase)

ee = obj.clone()
step_until_phase(PickPhase.GRASP, ee)
print("3:", skill.phase)

step_until_phase(PickPhase.LIFT, ee)
print("4:", skill.phase)

target, closed = skill.step(ee, obj, lift, dt=0.1)

print("lift target:", target.tolist())
print("gripper closed:", closed)
