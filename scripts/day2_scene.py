"""Day 2: a custom Panda tabletop manipulation scene.

Run in the existing environment:
    conda activate robot-demo
    cd ~/robotics/IsaacLab
    LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        uv run --no-sync python ../language-guided-robot-manipulation/scripts/day2_scene.py --viz kit --livestream 2

Add --max_steps 240 --check for a bounded smoke check. AppLauncher is supported but
deprecated in this Isaac Lab develop checkout.
"""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Minimal custom Franka Panda scene.")
parser.add_argument("--max_steps", type=int, default=0, help="Stop after this many steps; 0 runs until closed.")
parser.add_argument("--check", action="store_true", help="Check that the cube settles on the table.")
parser.add_argument("--screenshot", type=Path, help="Save the Kit viewport when the bounded run ends.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if args_cli.max_steps < 0:
    parser.error("--max_steps must be nonnegative")
if (args_cli.check or args_cli.screenshot) and args_cli.max_steps < 120:
    parser.error("--check/--screenshot require --max_steps >= 120")

# Isaac Sim must start before importing simulation and scene modules.
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import torch

import isaaclab.sim as sim_utils
from isaaclab.scene import InteractiveScene
from isaaclab.sim import SimulationContext

from demo_utils import save_screenshot
from scenes.manipulation import CUBE_SIZE, ManipulationSceneCfg


def main():
    """Create the scene and hold the Panda in its default joint pose."""
    sim = SimulationContext(sim_utils.SimulationCfg(dt=0.01, device=args_cli.device))
    sim.set_camera_view((2.0, 1.8, 1.7), (0.35, 0.0, 0.3))
    scene = InteractiveScene(ManipulationSceneCfg(num_envs=1, env_spacing=2.0))
    sim.reset()

    robot = scene["robot"]
    joint_pos = robot.data.default_joint_pos.torch.clone()
    joint_vel = robot.data.default_joint_vel.torch.clone()
    robot.write_joint_position_to_sim_index(position=joint_pos)
    robot.write_joint_velocity_to_sim_index(velocity=joint_vel)
    scene.reset()
    robot.actuators.target_command.set_position_index(value=joint_pos)

    print(f"[INFO] Franka scene ready: {robot.num_instances} robot, {robot.num_joints} joints.", flush=True)
    sim_dt = sim.get_physics_dt()
    step_count = 0
    while simulation_app.is_running() and (args_cli.max_steps == 0 or step_count < args_cli.max_steps):
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim_dt)
        step_count += 1

    print(f"[INFO] Simulation finished after {step_count} steps.", flush=True)
    if (args_cli.check or args_cli.screenshot) and step_count != args_cli.max_steps:
        raise RuntimeError("Bounded scene check was interrupted before all steps completed.")
    if args_cli.check:
        position = scene["cube"].data.root_pos_w.torch[0]
        velocity = scene["cube"].data.root_vel_w.torch[0]
        if not torch.isfinite(robot.data.joint_pos.torch).all() or robot.num_joints != 9:
            raise RuntimeError("Panda articulation did not initialize correctly.")
        if not torch.isfinite(position).all() or abs(position[2].item() - CUBE_SIZE / 2) > 0.005:
            raise RuntimeError(f"Cube did not settle on the table: {position.tolist()}")
        # Linear velocity is in m/s; angular velocity is in rad/s.
        if (
            not torch.isfinite(velocity).all()
            or torch.linalg.norm(velocity[:3]).item() > 0.01
            or torch.linalg.norm(velocity[3:]).item() > 0.1
        ):
            raise RuntimeError(f"Cube is still moving: {velocity.tolist()}")
        print(f"[CHECK] Cube settled at {position.tolist()}; Panda has 9 finite joint positions.", flush=True)
    if args_cli.screenshot:
        save_screenshot(args_cli.screenshot, simulation_app)


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
