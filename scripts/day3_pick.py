"""Day 3: pick the red cube, optionally place it on the green platform.

Run from IsaacLab with uv run --no-sync python <this file> --viz kit --livestream 2.
Success is measured from the cube's observed pose, not from the skill phase.
"""

import argparse
import math
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Pick a red cube and optionally place it using Panda differential IK.")
parser.add_argument("--max_steps", type=int, help="Attempt timeout: default 3000 for pick, 6000 with --place.")
parser.add_argument("--place", action="store_true", help="After a verified lift, place the cube on the green platform.")
parser.add_argument("--cube_x", type=float, default=0.5, help="Initial cube x position in meters.")
parser.add_argument("--cube_y", type=float, default=0.0, help="Initial cube y position in meters.")
parser.add_argument("--screenshot", type=Path, help="Save the viewport after verified task success.")
parser.add_argument("--keep_open", action="store_true", help="Hold the final arm pose until the app is closed.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if args_cli.max_steps is None:
    args_cli.max_steps = 6000 if args_cli.place else 3000
if args_cli.max_steps <= 0:
    parser.error("--max_steps must be positive")
if not (math.isfinite(args_cli.cube_x) and math.isfinite(args_cli.cube_y)):
    parser.error("cube positions must be finite")
if not (0.35 <= args_cli.cube_x <= 0.65 and -0.15 <= args_cli.cube_y <= 0.15):
    parser.error("cube position must be inside the allowed tabletop region: x=[0.35,0.65], y=[-0.15,0.15]")

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch

import isaaclab.sim as sim_utils
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.scene import InteractiveScene
from isaaclab.sim import SimulationContext
from isaaclab.utils import replace
from isaaclab.utils.math import matrix_from_quat, quat_apply, quat_inv, subtract_frame_transforms
from isaaclab_assets import FRANKA_PANDA_HIGH_PD_CFG

from demo_utils import save_screenshot
from scenes.manipulation import CUBE_SIZE, PLATFORM_HEIGHT, ManipulationSceneCfg
from skills.pick import PickPhase, PickSkill
from skills.place import PlacePhase, PlaceSkill


def main():
    """Connect the pick state machine to IK and the Panda's finger drive."""
    sim = SimulationContext(sim_utils.SimulationCfg(dt=0.01, render_interval=4, device=args_cli.device))
    sim.set_camera_view((2.0, 1.8, 1.7), (0.35, 0.0, 0.3))
    cfg = ManipulationSceneCfg(num_envs=1, env_spacing=2.0)
    cfg.robot = replace(FRANKA_PANDA_HIGH_PD_CFG, prim_path="{ENV_REGEX_NS}/Robot")
    cfg.cube.init_state.pos = (args_cli.cube_x, args_cli.cube_y, CUBE_SIZE / 2 + 0.005)
    scene = InteractiveScene(cfg)
    sim.reset()

    robot, cube = scene["robot"], scene["cube"]
    arm_ids, _ = robot.find_joints("panda_joint[1-7]")
    finger_ids, _ = robot.find_joints("panda_finger_joint1")
    hand_ids, _ = robot.find_bodies("panda_hand")
    hand_id = hand_ids[0]
    jacobian_id = hand_id - 1 if robot.is_fixed_base else hand_id
    jacobian_joint_ids = [j + robot.num_base_dofs for j in arm_ids]
    joint_pos = robot.data.default_joint_pos.torch.clone()
    robot.write_joint_position_to_sim_index(position=joint_pos)
    robot.write_joint_velocity_to_sim_index(velocity=robot.data.default_joint_vel.torch.clone())
    scene.reset()
    robot.actuators.target_command.set_position_index(value=joint_pos)

    dt = sim.get_physics_dt()
    # Let the cube settle before measuring its starting height.
    for _ in range(60):
        scene.write_data_to_sim()
        sim.step()
        scene.update(dt)
    initial_cube_position = cube.data.root_pos_w.torch[0].clone()
    lift_position = initial_cube_position.clone()
    lift_position[2] += 0.20
    skill = PickSkill(position_threshold=0.01)
    place_skill = None
    destination = scene.env_origins[0] + torch.tensor(cfg.platform.init_state.pos, device=sim.device)
    destination[2] += PLATFORM_HEIGHT / 2 + CUBE_SIZE / 2
    ik = DifferentialIKController(
        DifferentialIKControllerCfg(command_type="pose", use_relative_mode=False, ik_method="dls"),
        num_envs=1,
        device=sim.device,
    )
    # Panda hand origin is above the grasp point; use the official IK TCP offset.
    tcp_offset = torch.tensor([[0.0, 0.0, 0.107]], device=sim.device)
    downward = torch.tensor([[0.0, 1.0, 0.0, 0.0]], device=sim.device)  # XYZW
    finger_command = torch.full((1, 1), 0.04, device=sim.device)
    stable_time = 0.0
    success = False
    reached_step = 0
    pick_rise = 0.0
    print(f"[INFO] Starting cube position: {initial_cube_position.tolist()}", flush=True)

    with torch.inference_mode():
        for step in range(args_cli.max_steps):
            if not simulation_app.is_running():
                break
            hand_pose = robot.data.body_pose_w.torch[:, hand_id]
            root_pose = robot.data.root_pose_w.torch
            lever_w = quat_apply(hand_pose[:, 3:7], tcp_offset)
            tcp_w = hand_pose[:, :3] + lever_w
            tcp_b, tcp_quat_b = subtract_frame_transforms(
                root_pose[:, :3], root_pose[:, 3:7], tcp_w, hand_pose[:, 3:7],
            )
            active_skill = skill if place_skill is None else place_skill
            phase = active_skill.phase
            if place_skill is None:
                target_w, closed = skill.step(tcp_w[0], cube.data.root_pos_w.torch[0], lift_position, dt)
            else:
                target_w, closed = place_skill.step(tcp_w[0], destination, dt)
            desired_quat_w = hand_pose[:, 3:7] if phase == PickPhase.REST else downward
            target_b, desired_quat_b = subtract_frame_transforms(
                root_pose[:, :3], root_pose[:, 3:7], target_w[None, :], desired_quat_w,
            )
            ik.set_command(torch.cat((target_b, desired_quat_b), dim=-1))

            jacobian = robot.data.body_link_jacobian_w.torch[:, jacobian_id, :, jacobian_joint_ids].clone()
            jacobian[:, :3] += torch.linalg.cross(jacobian[:, 3:], lever_w[:, :, None], dim=1)
            world_to_base = matrix_from_quat(quat_inv(root_pose[:, 3:7]))
            jacobian[:, :3] = torch.bmm(world_to_base, jacobian[:, :3])
            jacobian[:, 3:] = torch.bmm(world_to_base, jacobian[:, 3:])
            current_joints = robot.data.joint_pos.torch[:, arm_ids]
            desired_joints = ik.compute(tcp_b, tcp_quat_b, jacobian, current_joints)
            # Limit each target update so an IK jump does not snap the arm.
            desired_joints = current_joints + (desired_joints - current_joints).clamp(-0.03, 0.03)
            limits = robot.data.soft_joint_pos_limits.torch[:, arm_ids]
            desired_joints = torch.maximum(torch.minimum(desired_joints, limits[:, :, 1]), limits[:, :, 0])
            robot.actuators.target_command.set_position_index(value=desired_joints, joint_ids=arm_ids)
            finger_command.fill_(0.0 if closed else 0.04)
            # The second finger is a passive mimic joint on the current Panda asset.
            robot.actuators.target_command.set_position_index(value=finger_command, joint_ids=finger_ids)
            scene.write_data_to_sim()
            sim.step()
            scene.update(dt)
            if active_skill.phase != phase:
                print(f"[PHASE] {step * dt:.2f}s: {phase.name} -> {active_skill.phase.name}", flush=True)
            if step % 200 == 0:
                print(
                    f"[STATE] step={step}, phase={active_skill.phase.name}, "
                    f"cube_z={cube.data.root_pos_w.torch[0, 2].item():.4f}", flush=True,
                )

            # Observe after stepping; a phase transition alone is not a successful grasp.
            observed_cube = cube.data.root_pos_w.torch[0]
            hand_after = robot.data.body_pose_w.torch[:, hand_id]
            tcp_after = hand_after[:, :3] + quat_apply(hand_after[:, 3:7], tcp_offset)
            if not torch.isfinite(observed_cube).all() or not torch.isfinite(tcp_after).all():
                raise RuntimeError("Non-finite simulation state during pick.")
            if place_skill is None:
                verified = (
                    skill.phase == PickPhase.LIFT
                    and observed_cube[2].item() >= initial_cube_position[2].item() + 0.10
                    and torch.linalg.norm(observed_cube - tcp_after[0]).item() < 0.05
                    and torch.linalg.norm(tcp_after[0] - lift_position).item() < 0.015
                )
            else:
                velocity = cube.data.root_vel_w.torch[0]
                verified = (
                    place_skill.phase == PlacePhase.DONE
                    and torch.linalg.norm(observed_cube[:2] - destination[:2]).item() < 0.04
                    and abs(observed_cube[2].item() - destination[2].item()) < 0.008
                    and torch.isfinite(velocity).all().item()
                    and torch.linalg.norm(velocity[:3]).item() < 0.01
                    and torch.linalg.norm(velocity[3:]).item() < 0.1
                    and tcp_after[0, 2].item() > destination[2].item() + 0.10
                )
            stable_time = stable_time + dt if verified else 0.0
            if stable_time >= 0.5:
                if place_skill is None:
                    pick_rise = observed_cube[2].item() - initial_cube_position[2].item()
                    print(f"[CHECK] Pick verified: cube_rise={pick_rise:.4f}m; hold={stable_time:.2f}s", flush=True)
                    if args_cli.place:
                        place_skill = PlaceSkill()
                        stable_time = 0.0
                        print(f"[INFO] Placing at {destination.tolist()}", flush=True)
                        continue
                success = True
                reached_step = step + 1
                break

    if not success:
        failed_phase = skill.phase.name if place_skill is None else place_skill.phase.name
        task = "Pick/place" if args_cli.place else "Pick"
        raise RuntimeError(
            f"{task} failed within {args_cli.max_steps} steps or was interrupted: phase={failed_phase}, "
            f"cube={cube.data.root_pos_w.torch[0].tolist()}"
        )
    final_cube = cube.data.root_pos_w.torch[0]
    print(
        f"[SUCCESS] task={'pick_place' if args_cli.place else 'pick'}; "
        f"cube_rise={pick_rise:.4f}m; stable_hold={stable_time:.2f}s; "
        f"steps={reached_step}; cube={final_cube.tolist()}", flush=True,
    )
    if args_cli.screenshot:
        save_screenshot(args_cli.screenshot, simulation_app)
    if args_cli.keep_open:
        print("[INFO] Holding the final arm pose; close the app or press Ctrl+C to stop.", flush=True)
        while simulation_app.is_running():
            scene.write_data_to_sim()
            sim.step()
            scene.update(dt)


if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.", flush=True)
        exit_code = 130
    except Exception:
        traceback.print_exc()
        exit_code = 1
    finally:
        simulation_app.close(exit_code=exit_code)
