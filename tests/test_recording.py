"""Recording publication must preserve existing results and clean failed writes."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from execution.recording import publish_recording

PROJECT = Path(__file__).resolve().parents[1]


class RecordingPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=PROJECT)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "source.gif"
        self.source.write_bytes(b"recorded bytes")
        self.target = self.directory / "result.gif"

    def test_success_publishes_clip_and_readable_metadata(self):
        publish_recording(self.target, self.source, {"source": "actual frames"})
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        self.assertEqual(json.loads(self.target.with_suffix(".json").read_text()), {"source": "actual frames"})

    def test_metadata_collision_preserves_existing_file_and_rolls_back_clip(self):
        metadata = self.target.with_suffix(".json")
        metadata.write_text("existing metadata")
        with self.assertRaises(FileExistsError):
            publish_recording(self.target, self.source, {})
        self.assertFalse(self.target.exists())
        self.assertEqual(metadata.read_text(), "existing metadata")

    def test_failed_copy_removes_only_new_output(self):
        with patch("execution.recording.shutil.copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                publish_recording(self.target, self.source, {})
        self.assertFalse(self.target.exists())
        self.assertFalse(self.target.with_suffix(".json").exists())
        self.assertTrue(self.source.exists())

    def test_existing_clip_is_not_removed_on_failed_exclusive_create(self):
        self.target.write_bytes(b"existing clip")
        with self.assertRaises(FileExistsError):
            publish_recording(self.target, self.source, {})
        self.assertEqual(self.target.read_bytes(), b"existing clip")


if __name__ == "__main__":
    unittest.main()
