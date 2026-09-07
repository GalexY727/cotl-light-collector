"""Offline regression tests: no real screenshots or keyboard/mouse actions."""
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
import main as app


class DetectionTests(unittest.TestCase):
    def setUp(self):
        app.DEBUG = False
        app._screen = None

    def scene(self, size, name='unlit_friend', multiplier=1.0):
        w, h = size
        scene = np.zeros((h, w, 3), dtype=np.uint8)
        needle = app.load_template(str(app.template_path(name)))
        tw = round(needle.shape[1] * w / 2880 * multiplier)
        th = round(needle.shape[0] * h / 1800 * multiplier)
        icon = cv2.resize(needle, (tw, th), interpolation=cv2.INTER_AREA if tw < needle.shape[1] else cv2.INTER_CUBIC)
        x, y = w // 2, h // 2
        scene[y:y+th, x:x+tw] = icon
        app.capture_and_cache_screen(scene)
        return x, y, tw, th

    def test_reference_and_other_resolutions(self):
        for size in [(2880, 1800), (1440, 900), (1920, 1080), (3840, 2160)]:
            with self.subTest(size=size):
                box = self.scene(size)
                x, y, w, h = box
                hits = app.locate_scaled('unlit_friend', (x-20, y-20, w+40, h+40), .9)
                self.assertEqual(hits[0].box, box)
                self.assertEqual(len(hits), 1)

    def test_best_scale_and_region_offset(self):
        box = self.scene((1440, 900), multiplier=1.1)
        x, y, w, h = box
        hits = app.locate_scaled('unlit_friend', (x-10, y-10, w+20, h+20), .7, [.9, 1, 1.1])
        self.assertEqual(hits[0].box, box)
        self.assertGreater(hits[0].score, .999)

    def test_nms_glow_and_separate_rows(self):
        a = app.Match(100, 100, 50, 60, .98, 'unlit_friend')
        glow = app.Match(103, 162, 50, 60, .93, 'unlit_friend')
        other = app.Match(100, 260, 50, 60, .95, 'lit_friend')
        cross_scale = app.Match(98, 98, 54, 64, .94, 'lit_friend')
        self.assertEqual(app.non_max_suppression([glow, other, cross_scale, a]), [a, other])

    def test_blank_and_clipped_regions(self):
        app.capture_and_cache_screen(np.zeros((900, 1440, 3), np.uint8))
        self.assertEqual(app.locate_scaled('flare', (1439, 899, 100, 100)), [])
        self.assertEqual(app.locate_scaled('flare', (-20, -20, 40, 40)), [])
        self.assertEqual(app.locate_scaled('flare', (1500, 1000, 50, 50)), [])

    def test_missing_file_is_not_silenced(self):
        app.capture_and_cache_screen(np.zeros((100, 100, 3), np.uint8))
        with self.assertRaises(FileNotFoundError):
            app.locate_scaled('missing-template')

    def test_color_policy(self):
        self.scene((1440, 900))
        real = cv2.matchTemplate
        for name in ['lit_friend', 'unlit_friend', 'flare', 'page_bubble', 'page_bubble_online', 'esc', 'candle', 'const']:
            with patch.object(cv2, 'matchTemplate', wraps=real) as match:
                app.locate_scaled(name, (650, 400, 200, 150), scales=[1])
                template = match.call_args.args[1]
                self.assertEqual(template.ndim, 2 if name in app.GRAYSCALE else 3)

    def test_frame_reuse(self):
        box = self.scene((1440, 900))
        with patch.object(app, 'capture_and_cache_screen', side_effect=AssertionError('extra capture')):
            app.locate_scaled('unlit_friend', box)
            app.locate_scaled('lit_friend', box)
            app.locate_scaled('flare', box)

    def test_flare_grouping_one_capture_and_scaled_radius(self):
        # A 30px offset is within 70*.5; a 40px offset is outside.
        frame = np.zeros((900, 1440, 3), np.uint8)
        star = app.Match(95, 95, 10, 10, .99, 'lit_friend')
        capture = app.capture_and_cache_screen
        with patch.object(app, 'capture_and_cache_screen', wraps=capture) as cap, \
             patch.object(app, 'locate', side_effect=[[star], []]), \
             patch.object(app, 'cv_find_all', return_value=[(130, 100), (100, 130)]):
            self.assertEqual(app.find_flare_stars(frame), [(100, 100)])
            self.assertEqual(cap.call_count, 1)
        with patch.object(app, 'locate', side_effect=[[star], []]), \
             patch.object(app, 'cv_find_all', return_value=[(130, 100), (100, 140)]):
            self.assertEqual(app.find_flare_stars(frame), [])

    def test_raw_overlay_and_scores_before_nms(self):
        x, y, w, h = self.scene((1440, 900))
        with tempfile.TemporaryDirectory() as directory, patch.object(app, 'DEBUG_DIR', Path(directory)):
            app.DEBUG = True
            hits = app.locate_scaled('unlit_friend', (x-10, y-10, w+20, h+20), .9)
            with next(Path(directory).glob('*.csv')).open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertGreater(len(rows), len(hits))
            self.assertTrue(any(r['passes_threshold'] == 'False' for r in rows))
            self.assertIsNotNone(cv2.imread(str(next(Path(directory).glob('*.png')))))

    def test_ahk_release_even_on_interruption(self):
        fake = Mock()
        with patch.object(app, 'ahk', fake), patch.object(app.time, 'sleep', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                app.send_key('f')
        fake.key_down.assert_called_once_with('f')
        fake.key_up.assert_called_once_with('f')

    def test_candle_and_escape_share_capture(self):
        with patch.object(app, 'doubleClick'), patch.object(app.time, 'sleep'), \
             patch.object(app, 'capture_and_cache_screen') as cap, \
             patch.object(app, 'scaled_region', return_value=None), \
             patch.object(app, 'locate', side_effect=[[], []]), \
             patch.object(app, 'enter_ui') as enter:
            app.light_friend(10, 10)
            cap.assert_called_once()
            enter.assert_called_once()


if __name__ == '__main__':
    unittest.main()
