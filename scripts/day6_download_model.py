"""Cache the pinned optional model; never install or modify Isaac Lab dependencies."""

import os
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.environ["HF_XET_CACHE"] = str(PROJECT / ".cache/day6/xet")

from planning.llm import MODEL_CACHE, MODEL_ID, MODEL_REVISION


def main():
    from huggingface_hub import snapshot_download

    snapshot = snapshot_download(
        MODEL_ID, revision=MODEL_REVISION, cache_dir=MODEL_CACHE,
        allow_patterns=["*.json", "*.safetensors", "merges.txt"], token=False,
    )
    print(f"[MODEL] {MODEL_ID} revision={MODEL_REVISION}")
    print(f"[CACHE] {snapshot}")


if __name__ == "__main__":
    main()
