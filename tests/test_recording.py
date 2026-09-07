import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from collector.models import Observation, State, Box
from collector.recording import Recorder, replay


class RecordingTests(unittest.TestCase):
    def test_record_and_replay_without_input(self):
        with tempfile.TemporaryDirectory() as folder:
            o = Observation(State.PAGE, Box(0, 0, 20, 20), page_token=(10, 1))
            recorder = Recorder(folder)
            recorder.event("input", action="key_down", args=["c"])
            recorder.frame(np.zeros((20, 20, 3), np.uint8), "observation", o)
            recorder.event("failure", error="example")
            recorder.close()
            detector = Mock()
            detector.analyze.return_value = o
            self.assertEqual(replay(folder, detector), 0)
            detector.analyze.assert_called_once()
            result = json.loads((Path(folder) / "replay.jsonl").read_text())
            self.assertFalse(result["changed"])
            # New runs replace the manifest; old, unreferenced frames aren't replayed.
            Recorder(folder).close()
            self.assertEqual((Path(folder) / "events.jsonl").read_text(), "")
