import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch
import cv2
import numpy as np
from collector.vision import Detector
from collector.models import State
from collector.diagnostics import validate, run_dataset

ROOT = Path(__file__).resolve().parents[1]


class VisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = Detector(ROOT / "media")
        cls.manifest = json.loads((ROOT / "debug/manifest.json").read_text())["images"]

    def test_annotated_originals(self):
        for name, expected in self.manifest.items():
            if "targets" not in expected:
                continue
            with self.subTest(name=name):
                image = cv2.imread(str(ROOT / "debug" / name))
                o = self.detector.analyze(image)
                errors, _ = validate(o, expected, image.shape)
                self.assertEqual(errors, [])

    def test_friend_dialog_with_footer_controls_detects_candle(self):
        image = cv2.imread(str(ROOT / "debug/friend-selected.png"))
        o = self.detector.analyze(image)
        self.assertEqual(o.state, State.SELECTED)
        self.assertTrue({"q_info", "esc", "candle"}.issubset(o.anchors))
        self.assertEqual(o.page_token, ())
        self.assertEqual(o.targets, [])

    def test_footer_speck_does_not_invalidate_pagination(self):
        image = cv2.imread(str(ROOT / "debug/pagination-footer-speck.png"))
        o = self.detector.analyze(image)
        self.assertEqual(o.state, State.PAGE)
        self.assertEqual(o.page_token, (10, 4))
        self.assertEqual(len(o.targets), 10)

    def test_scaled_geometry_and_letterboxing(self):
        # Geometry changes use real images and exactly the production detector.
        source = cv2.imread(str(ROOT / "debug/image4.png"))
        original = self.detector.analyze(source)
        for factor in (0.5, 0.75, 1.25, 1.5):
            with self.subTest(scale=factor):
                resized = cv2.resize(
                    source, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA
                )
                image = cv2.copyMakeBorder(resized, 30, 30, 50, 50, cv2.BORDER_CONSTANT)
                o = self.detector.analyze(image)
                self.assertEqual(o.state, State.PAGE)
                self.assertEqual(o.page_token, original.page_token)
                self.assertEqual(len(o.targets), len(original.targets))
                self.assertEqual(sum(t.collectible is True for t in o.targets), 8)
                for target in original.targets:
                    center = np.array(target.center) * factor + [50, 30]
                    self.assertLess(
                        min(
                            np.linalg.norm(np.array(t.center) - center)
                            for t in o.targets
                        ),
                        8 * factor,
                    )

    def test_unknown_images_are_not_actionable(self):
        rng = np.random.default_rng(42)
        for image in [
            np.zeros((720, 1280, 3), np.uint8),
            rng.integers(0, 256, (720, 1280, 3), dtype=np.uint8),
        ]:
            o = self.detector.analyze(image)
            self.assertEqual(o.state, State.UNKNOWN)
            self.assertEqual(o.targets, [])

    def test_synthetic_index_and_candle_anchor_routing(self):
        # Composites test routing only; they are not evidence of actual game transitions.
        source = cv2.imread(str(ROOT / "debug/image4.png"))
        for name, state in [("add_friends", State.INDEX), ("candle", State.SELECTED)]:
            with self.subTest(anchor=name):
                image = source.copy()
                icon = cv2.imread(str(ROOT / "media/ui" / f"{name}.png"))
                x, y = (20, 1008) if name == "add_friends" else (900, 400)
                image[y : y + icon.shape[0], x : x + icon.shape[1]] = icon
                observation = self.detector.analyze(image)
                self.assertEqual(observation.state, state)
                if state == State.SELECTED:
                    self.assertEqual(observation.targets, [])

    def test_constellation_tabs_are_required_before_page_state(self):
        image = cv2.imread(str(ROOT / "debug" / "image4.png"))
        height, width = image.shape[:2]
        image[int(height * 0.95) :, : int(width * 0.3)] = 0
        observation = self.detector.analyze(image)
        self.assertEqual(observation.state, State.UNKNOWN)
        self.assertEqual(observation.page_token, ())
        self.assertEqual(observation.targets, [])

    def test_zero_index_fixture_identifies_leftmost_friend_tab(self):
        image = cv2.imread(str(ROOT / "debug" / "zero-index.png"))
        observation = self.detector.analyze(image)
        self.assertEqual(observation.state, State.INDEX)
        self.assertEqual(observation.page_token, (10, 0))

    def test_corrupt_image_fails(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(
            io.StringIO()
        ):
            root = Path(folder)
            (root / "broken.png").write_bytes(b"broken")
            self.assertEqual(run_dataset(root, ROOT / "media"), 1)

    def test_no_input_modules_imported_in_test_mode(self):
        import main

        # Poison adapters: any attempted import or use would fail.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cv2.imwrite(str(root / "blank.png"), np.zeros((180, 320, 3), np.uint8))
            with patch.dict(
                sys.modules,
                {
                    "collector.runtime": None,
                    "pyautogui": None,
                    "mss": None,
                    "ahk": None,
                },
            ), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main.main(["--test", "--dataset", str(root)]), 0)

    def test_bad_annotations_and_empty_dataset_fail(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(
            io.StringIO()
        ):
            root = Path(folder)
            self.assertEqual(run_dataset(root, ROOT / "media"), 1)
            cv2.imwrite(str(root / "blank.png"), np.zeros((180, 320, 3), np.uint8))
            (root / "manifest.json").write_text(
                json.dumps({"images": {"blank.png": {"state": "index", "targets": []}}})
            )
            self.assertEqual(run_dataset(root, ROOT / "media"), 1)

    def test_output_images_not_retested(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(
            io.StringIO()
        ):
            root = Path(folder)
            (root / "output").mkdir()
            (root / "output" / "bad.png").write_bytes(b"not an image")
            cv2.imwrite(str(root / "blank.png"), np.zeros((180, 320, 3), np.uint8))
            self.assertEqual(run_dataset(root, ROOT / "media"), 0)


if __name__ == "__main__":
    unittest.main()
