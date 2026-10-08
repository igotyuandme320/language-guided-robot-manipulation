"""Optional real Kit viewport frames and a GIF published after verified success."""

import asyncio
import json
from pathlib import Path
import shutil
import tempfile

PROJECT = Path(__file__).resolve().parents[1]


def validate_recording_path(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    if not target.is_relative_to(PROJECT) or target.suffix.casefold() != ".gif":
        raise ValueError("--record_gif must be a .gif path inside the project")
    if target.exists() or target.with_suffix(".json").exists():
        raise ValueError("Recording GIF and its JSON metadata must not exist")
    return target


def publish_recording(target: Path, temporary: Path, metadata: dict) -> None:
    """Publish without overwriting, and roll back this attempt on write failure."""
    payload = json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    created = []
    try:
        with target.open("xb") as destination:
            created.append(target)
            with temporary.open("rb") as source:
                shutil.copyfileobj(source, destination)
        with target.with_suffix(".json").open("x") as destination:
            created.append(target.with_suffix(".json"))
            destination.write(payload)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise


class ViewportRecorder:
    """Queue captures during normal steps; wait only after task success."""

    def __init__(self, target: Path, dt: float, request: dict):
        from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport

        self.target = validate_recording_path(target)
        self.viewport = get_active_viewport()
        if self.viewport is None:
            raise RuntimeError("Recording needs an active Kit viewport.")
        cache = PROJECT / ".cache/day8"
        cache.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="recording_", dir=cache))
        self.dt, self.request = dt, request
        self.frames, self.pending = [], []
        self.capture_to_file = capture_viewport_to_file
        print(f"[RECORD] Raw frames: {self.directory}", flush=True)

    def capture(self, step: int, phase: str) -> None:
        if self.frames and self.frames[-1]["requested_step"] == step:
            return
        filename = f"frame_{len(self.frames):04d}.png"
        capture = self.capture_to_file(self.viewport, str(self.directory / filename))
        self.pending.append(asyncio.ensure_future(capture.wait_for_result()))
        self.frames.append({"file": filename, "requested_step": step, "phase": phase})

    def finish(self, result: dict, simulation_app) -> None:
        from PIL import Image

        for _ in range(100):
            if all(task.done() for task in self.pending):
                break
            simulation_app.update()
        if not all(task.done() for task in self.pending):
            raise RuntimeError("Recording captures did not complete within 100 app updates.")
        for task in self.pending:
            task.result()
        frames = []
        for row in self.frames:
            with Image.open(self.directory / row["file"]) as image:
                image = image.convert("RGB")
                image.thumbnail((720, 405), Image.Resampling.LANCZOS)
                frames.append(image)
        durations = [max(10, round((b["requested_step"] - a["requested_step"]) * self.dt * 1000))
                     for a, b in zip(self.frames, self.frames[1:])] + [2000]
        temporary = self.directory / "clip.gif"
        frame_size = list(frames[0].size)
        frames[0].save(temporary, save_all=True, append_images=frames[1:], duration=durations, loop=0)
        for frame in frames:
            frame.close()
        metadata = {"request": self.request, "result": result,
                    "source": "actual Kit viewport captures", "frame_size_px": frame_size,
                    "raw_frames_directory": str(self.directory.relative_to(PROJECT)),
                    "frames": self.frames, "frame_durations_ms": durations,
                    "timing_note": "Requested controller steps; capture may lag rendering. Playback uses nominal dt, with a 2 s final hold."}
        self.target.parent.mkdir(parents=True, exist_ok=True)
        publish_recording(self.target, temporary, metadata)
        print(f"[RECORD] GIF: {self.target}; frames={len(frames)}", flush=True)
