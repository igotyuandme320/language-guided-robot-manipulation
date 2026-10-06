# Day 1 — Environment Setup

## Goal

Set up and verify the development environment for language-guided robot manipulation with Franka Panda in Isaac Lab.

## Setup

- Remote Ubuntu workstation
- NVIDIA GeForce RTX 3080 10GB
- Conda + Python 3.12
- Isaac Sim 6.1
- Isaac Lab
- Franka Panda
- MacBook as the remote development client

## Progress

- [x] Remote SSH access
- [x] GitHub SSH authentication
- [x] Project repository cloned
- [x] Isaac Lab environment installed
- [x] Isaac Sim headless simulation verified
- [x] Franka Panda manipulation environment loaded
- [x] Differential inverse kinematics controller verified
- [x] Gripper controller verified
- [x] WebRTC livestream configured
- [x] Isaac Sim visualization streamed successfully to Mac

## Notes

Development is performed remotely from a MacBook via SSH.

Isaac Lab is launched with `uv run` instead of the legacy `isaaclab.sh` workflow.

The official Franka lift-cube state machine example was successfully executed using:

```bash
uv run python scripts/environments/state_machine/lift_cube_sm.py \
  --num_envs 1
```

For remote visualization, Isaac Sim is launched with WebRTC livestreaming:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib" \
uv run python scripts/environments/state_machine/lift_cube_sm.py \
  --num_envs 1 \
  --livestream 2
```

The simulation can now be viewed from the Mac using the Isaac Sim WebRTC Streaming Client.

## Result

The complete simulation pipeline is working:

```text
Mac
 ↓
SSH / WebRTC
 ↓
Ubuntu workstation
 ↓
Isaac Lab
 ↓
Franka Panda
 ↓
IK + Gripper Control
```

## Next

Create a custom manipulation scene containing:

- Franka Panda
- Table
- Red cube
- Green target

Then begin implementing reusable robot manipulation skills.