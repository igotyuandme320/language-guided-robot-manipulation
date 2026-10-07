"""Small utilities shared by the standalone Isaac Sim demos."""

import asyncio
from pathlib import Path


def save_screenshot(path: str | Path, simulation_app) -> None:
    """Save the active Kit viewport, waiting for the capture to finish."""
    from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport

    viewport = get_active_viewport()
    if viewport is None:
        raise RuntimeError("Screenshot requires a Kit viewport: use --viz kit or --livestream 2.")
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    capture = capture_viewport_to_file(viewport, str(destination))
    pending = asyncio.ensure_future(capture.wait_for_result())
    for _ in range(100):
        simulation_app.update()
        if pending.done():
            pending.result()
            print(f"[INFO] Screenshot saved: {destination}", flush=True)
            return
    raise RuntimeError("Viewport capture did not finish within 100 app updates.")
