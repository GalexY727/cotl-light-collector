"""Exercise coordinate/focus guards without initializing any desktop adapter."""

import unittest
from unittest.mock import Mock, patch
import numpy as np
from collector.runtime import WindowsGame, LiveError


class RuntimeTests(unittest.TestCase):
    def game(self):
        game = WindowsGame.__new__(WindowsGame)
        game.last_rect = dict(left=-1280, top=20, width=1280, height=720)
        game.rect = Mock(return_value=game.last_rect.copy())
        game.ahk = Mock()
        return game

    def test_client_to_monitor_coordinates(self):
        game = self.game()
        with patch("builtins.print") as report:
            game.click((100, 200))
        game.ahk.click.assert_called_once_with(-1180, 220)
        report.assert_called_once_with(
            "[input] click client=(100, 200) screen=(-1180, 220)", flush=True
        )

    def test_key_press_is_reported_before_dispatch(self):
        game = self.game()
        with patch("builtins.print") as report:
            game.key("z")
        report.assert_called_once_with("[input] key=z", flush=True)
        game.ahk.key_down.assert_called_once_with("z")
        game.ahk.key_up.assert_called_once_with("z")

    def test_geometry_change_prevents_input(self):
        game = self.game()
        game.rect.return_value["left"] = 0
        with self.assertRaises(LiveError):
            game.click((100, 200))
        game.ahk.click.assert_not_called()

    def test_nudge_moves_one_pixel_without_clicking(self):
        game = self.game()
        with patch("builtins.print"):
            game.nudge()
        game.ahk.mouse_move.assert_called_once_with(1, 0, speed=0, relative=True)
        game.ahk.click.assert_not_called()

    def test_outside_client_prevents_input(self):
        game = self.game()
        with self.assertRaises(LiveError):
            game.click((-1, 200))
        game.ahk.click.assert_not_called()

    def test_capture_converts_one_bgra_frame_in_memory(self):
        game = self.game()
        game.sct = Mock()
        pixels = np.zeros((720, 1280, 4), np.uint8)
        pixels[0, 0] = [10, 20, 30, 255]
        game.sct.grab.return_value = pixels
        frame, ms = game.capture()
        self.assertEqual(frame.shape, (720, 1280, 3))
        np.testing.assert_array_equal(frame[0, 0], [10, 20, 30])
        self.assertGreaterEqual(ms, 0)
        game.sct.grab.assert_called_once_with(game.last_rect)
        game.ahk.click.assert_not_called()

    def test_ahk_failure_becomes_readable_stop(self):
        game = self.game()
        game.ahk.click.side_effect = OSError("AHK transport closed")
        with self.assertRaisesRegex(LiveError, "AutoHotkey input dispatch failed"):
            game.click((100, 200))


if __name__ == "__main__":
    unittest.main()
