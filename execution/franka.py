"""Shared physical execution for the Day 3 and Day 4 entrypoints.

Import only after AppLauncher starts Isaac Sim. Symbolic effects are committed
only after the cube passes the corresponding physical success check.
"""

import json
import math

import torch

import isaaclab.sim as sim_utils
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.scene import InteractiveScene
from isaaclab.sim import SimulationContext
from isaaclab.utils import replace
from isaaclab.utils.math import matrix_from_quat, quat_apply, quat_inv, subtract_frame_transforms
from isaaclab_assets import FRANKA_PANDA_HIGH_PD_CFG

from planning.grounding import observe_initial_state
from planning.symbolic import Goal, apply_skill, goal_satisfied, plan_goal
from execution.monitoring import GraspMonitor
from scripts.demo_utils import save_screenshot
from scenes.manipulation import CUBE_SIZE, PLATFORM_HEIGHT, ManipulationSceneCfg
from skills.pick import PickPhase, PickSkill
from skills.place import PlacePhase, PlaceSkill


def execute_goal(goal: Goal, args_cli, simulation_app):
    """Plan from a settled observation, execute skills, and verify their effects."""
    sim = SimulationContext(sim_utils.SimulationCfg(dt=0.01, render_interval=4, device=args_cli.device))
    sim.set_camera_view((2.0, 1.8, 1.7), (0.35, 0.0, 0.3))
    cfg = ManipulationSceneCfg(num_envs=1, env_spacing=2.0)
    cfg.robot = replace(FRANKA_PANDA_HIGH_PD_CFG, prim_path="{ENV_REGEX_NS}/Robot")
    if getattr(args_cli, "cube_start", "table") == "green_platform":
        px, py, pz = cfg.platform.init_state.pos
        cfg.cube.init_state.pos = (px, py, pz + PLATFORM_HEIGHT / 2 + CUBE_SIZE / 2 + 0.005)
    else:
        cfg.cube.init_state.pos = (args_cli.cube_x, args_cli.cube_y, CUBE_SIZE / 2 + 0.005)
    yaw_deg = getattr(args_cli, "cube_yaw_deg", 0.0)
    if yaw_deg:
        half_yaw = math.radians(yaw_deg) / 2
        cfg.cube.init_state.rot = (0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw))  # XYZW
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
    if yaw_deg:
        print("[SCENE] " + json.dumps({
            "configured_cube_yaw_deg": yaw_deg,
            "settled_cube_quaternion_xyzw": cube.data.root_pose_w.torch[0, 3:7].tolist(),
        }, allow_nan=False), flush=True)
    lift_position = initial_cube_position.clone()
    lift_position[2] += 0.20
    destination = scene.env_origins[0] + torch.tensor(cfg.platform.init_state.pos, device=sim.device)
    destination[2] += PLATFORM_HEIGHT / 2 + CUBE_SIZE / 2
    state = observe_initial_state(
        initial_cube_position.tolist(), cube.data.root_vel_w.torch[0].tolist(), destination.tolist(),
    )
    plan = plan_goal(goal, state)
    print(f"[WORLD] {json.dumps(state.to_dict())}", flush=True)
    print(f"[PLAN] {json.dumps([call.to_dict() for call in plan])}", flush=True)
    if not plan:
        # Settling and grounding established the goal; no manipulation was needed.
        result = {
            "goal": goal.to_dict(), "plan": [], "final_state": state.to_dict(),
            "execution_status": "already_satisfied",
            "initial_cube_position_m": initial_cube_position.tolist(),
            "final_cube_position_m": initial_cube_position.tolist(),
            "steps": 0, "physics_dt_s": dt, "cube_rise_m": 0.0, "stable_hold_s": 0.0,
        }
        print("[RESULT] " + json.dumps(result, allow_nan=False), flush=True)
        print(f"[SUCCESS] Goal already satisfied: {json.dumps(state.to_dict())}", flush=True)
        if args_cli.screenshot:
            save_screenshot(args_cli.screenshot, simulation_app)
        if args_cli.keep_open:
            print("[INFO] Holding the initial arm pose; close the app or press Ctrl+C to stop.", flush=True)
            while simulation_app.is_running():
                scene.write_data_to_sim()
                sim.step()
                scene.update(dt)
        return state
    skills = {"pick": PickSkill(position_threshold=0.01), "place": PlaceSkill()}
    plan_index = 0
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
    attempted_steps = 0
    failure_reason = None
    grasp_monitor = GraspMonitor()
    stuck_open = getattr(args_cli, "gripper_stuck_open", False)
    release_after_pick = getattr(args_cli, "release_after_pick", False)
    if stuck_open:
        print('[FAULT] {"gripper_stuck_open": true}', flush=True)
    if release_after_pick:
        print('[FAULT] {"release_after_pick": true}', flush=True)
    print(f"[INFO] Starting cube position: {initial_cube_position.tolist()}", flush=True)
    recorder = None
    if getattr(args_cli, "record_gif", None):
        from execution.recording import ViewportRecorder
        recorder = ViewportRecorder(args_cli.record_gif, dt, {
            "instruction": args_cli.instruction, "language_backend": args_cli.language_backend,
            "goal": goal.to_dict(), "language_frontend": args_cli.language_metadata,
        })
        recorder.capture(0, "pick:REST")

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
            call = plan[plan_index]
            active_skill = skills[call.skill]
            phase = active_skill.phase
            if call.skill == "pick":
                target_w, closed = active_skill.step(tcp_w[0], cube.data.root_pos_w.torch[0], lift_position, dt)
            else:
                target_w, closed = active_skill.step(tcp_w[0], destination, dt)
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
            release_fault_active = release_after_pick and call.skill == "place"
            finger_command.fill_(0.0 if closed and not stuck_open and not release_fault_active else 0.04)
            # The second finger is a passive mimic joint on the current Panda asset.
            robot.actuators.target_command.set_position_index(value=finger_command, joint_ids=finger_ids)
            scene.write_data_to_sim()
            sim.step()
            scene.update(dt)
            attempted_steps = step + 1
            if active_skill.phase != phase:
                print(f"[PHASE] {step * dt:.2f}s: {phase.name} -> {active_skill.phase.name}", flush=True)
            if recorder is not None and (step + 1) % 50 == 0:
                recorder.capture(step + 1, f"{call.skill}:{active_skill.phase.name}")
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
            cube_tcp_distance = torch.linalg.norm(observed_cube - tcp_after[0]).item()
            # The returned command belongs to this step, including a phase-transition tick.
            grasp_required = call.skill == "place" and closed
            if grasp_monitor.update(cube_tcp_distance, grasp_required, dt):
                failure_reason = "lost_grasp"
                break
            if call.skill == "pick":
                verified = (
                    active_skill.phase == PickPhase.LIFT
                    and observed_cube[2].item() >= initial_cube_position[2].item() + 0.10
                    and cube_tcp_distance < 0.05
                    and torch.linalg.norm(tcp_after[0] - lift_position).item() < 0.015
                )
            else:
                velocity = cube.data.root_vel_w.torch[0]
                verified = (
                    active_skill.phase == PlacePhase.DONE
                    and torch.linalg.norm(observed_cube[:2] - destination[:2]).item() < 0.04
                    and abs(observed_cube[2].item() - destination[2].item()) < 0.008
                    and torch.isfinite(velocity).all().item()
                    and torch.linalg.norm(velocity[:3]).item() < 0.01
                    and torch.linalg.norm(velocity[3:]).item() < 0.1
                    and tcp_after[0, 2].item() > destination[2].item() + 0.10
                )
            stable_time = stable_time + dt if verified else 0.0
            if stable_time >= 0.5:
                if call.skill == "pick":
                    pick_rise = observed_cube[2].item() - initial_cube_position[2].item()
                    print(f"[CHECK] Pick verified: cube_rise={pick_rise:.4f}m; hold={stable_time:.2f}s", flush=True)
                # Commit the symbolic effect only after sustained observed success.
                state = apply_skill(state, call)
                print(f"[WORLD] {json.dumps(state.to_dict())}", flush=True)
                plan_index += 1
                if plan_index < len(plan):
                    skills[plan[plan_index].skill].reset()
                    stable_time = 0.0
                    print(f"[INFO] Executing skill {plan[plan_index].skill}", flush=True)
                    continue
                success = True
                reached_step = step + 1
                break

    if not success:
        failed_phase = skills[plan[plan_index].skill].phase.name
        observed_cube = cube.data.root_pos_w.torch[0]
        failure = {
            "goal": goal.to_dict(), "plan": [call.to_dict() for call in plan],
            "reason": failure_reason or ("step_limit" if attempted_steps == args_cli.max_steps else "app_closed"),
            "last_verified_state": state.to_dict(),
            "active_skill": plan[plan_index].skill, "phase": failed_phase,
            "attempted_steps": attempted_steps, "max_steps": args_cli.max_steps,
            "physics_dt_s": dt, "injected_fault": {"gripper_stuck_open": stuck_open},
            "initial_cube_position_m": initial_cube_position.tolist(),
            "observed_cube_position_m": observed_cube.tolist(),
            "cube_rise_m": observed_cube[2].item() - initial_cube_position[2].item(),
            "tcp_position_m": tcp_after[0].tolist() if attempted_steps else None,
            "finger_joint_position_m": robot.data.joint_pos.torch[0, finger_ids[0]].item(),
            "stable_hold_s": stable_time,
        }
        if release_after_pick:
            failure["injected_fault"]["release_after_pick"] = True
        if failure_reason == "lost_grasp":
            failure.update(cube_tcp_distance_m=cube_tcp_distance, grasp_loss_duration_s=grasp_monitor.elapsed)
        print("[FAILURE] " + json.dumps(failure, allow_nan=False), flush=True)
        task = "Pick/place" if goal.action == "place" else "Pick"
        raise RuntimeError(
            f"{task} failed within {args_cli.max_steps} steps or was interrupted: phase={failed_phase}, "
            f"cube={cube.data.root_pos_w.torch[0].tolist()}"
        )
    if not goal_satisfied(goal, state):
        raise RuntimeError("Executed plan did not satisfy the symbolic goal.")
    final_cube = cube.data.root_pos_w.torch[0]
    result = {
        "goal": goal.to_dict(),
        "plan": [call.to_dict() for call in plan],
        "final_state": state.to_dict(),
        "initial_cube_position_m": initial_cube_position.tolist(),
        "final_cube_position_m": final_cube.tolist(),
        "steps": reached_step,
        "physics_dt_s": dt,
        "cube_rise_m": pick_rise,
        "stable_hold_s": stable_time,
    }
    if stuck_open:
        result["injected_fault"] = {"gripper_stuck_open": True}
    if release_after_pick:
        result.setdefault("injected_fault", {})["release_after_pick"] = True
    if recorder is not None:
        recorder.capture(reached_step, f"{plan[-1].skill}:VERIFIED")
        recorder.finish(result, simulation_app)
    print("[RESULT] " + json.dumps(result), flush=True)
    print(
        f"[SUCCESS] task={'pick_place' if goal.action == 'place' else 'pick'}; "
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
    return state
