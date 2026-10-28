"""Human-labeled media baseline and offline controller/safety regressions."""
import json
from pathlib import Path
import threading
import tempfile
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from detector import Friend, Observation, UIState, observe, same_page
from automation import Controller, AutomationError, plan_page
from safety import WindowsSafety, AutomationPaused

ROOT = Path(__file__).resolve().parents[1]
PAGE = '00'*100
OTHER_PAGE = 'ff'*100


class BaselineTests(unittest.TestCase):
    def test_every_labeled_friend_and_action(self):
        labels = json.loads((ROOT/'tests/baseline_labels.json').read_text())['pages']
        count = 0
        for name, label in labels.items():
            frame = cv2.imread(str(ROOT/'media/new/list-mode'/name))
            for size in [(2560, 1440), (1920, 1080), (1280, 720)]:
                with self.subTest(page=name, size=size):
                    o = observe(cv2.resize(frame, size))
                    self.assertEqual(o.state, UIState.LIST)
                    expected = {(c, r): ([c, r] not in label['already_lit'], [c, r] in label['collect'])
                                for c in range(3) for r in range(7) if [c, r] not in label['empty']}
                    self.assertEqual({f.slot:(f.needs_light, f.needs_collect) for f in o.friends}, expected)
                    self.assertEqual(len(plan_page(o)), sum(sum(flags) for flags in expected.values()))
                    self.assertTrue(all(0 <= f.center[0] < size[0] and 0 <= f.center[1] < size[1]
                                        for f in o.friends))
            count += len(expected)
        self.assertEqual(count, 165)

    def test_panel_and_world_states(self):
        for name, state in [('need_to_light_friend', UIState.LIGHT_READY),
                            ('just_lit_friend', UIState.FRIEND), ('not_in_friend_ui', UIState.WORLD)]:
            with self.subTest(name=name):
                o = observe(cv2.imread(str(ROOT/'media/new'/(name+'.jpg'))))
                self.assertEqual(o.state, state)
                self.assertEqual(o.friends, ())
                with self.assertRaises(AutomationError):
                    plan_page(o)

    def test_unknown_and_unsupported_aspect(self):
        for size in [(1152, 2048), (900, 1440)]:
            self.assertEqual(observe(np.zeros((*size, 3), np.uint8)).state, UIState.UNKNOWN)

    def test_short_last_page_and_ambiguous_friend(self):
        frame = cv2.resize(cv2.imread(str(ROOT/'media/new/list-mode/page_0.jpg')), (2048,1152))
        first = frame[350:415, 540:800].copy()
        frame[350:810, 540:1510] = (8, 3, 2)
        frame[350:415, 540:800] = first
        observation = observe(frame)
        self.assertEqual(observation.state, UIState.LIST)
        self.assertEqual(len(observation.friends), 1)
        frame[502:523, 915:936] = 255
        self.assertEqual(observe(frame).state, UIState.UNKNOWN)

    def test_video_states(self):
        cap = cv2.VideoCapture(str(ROOT/'media/new/2026-10-27 23-37-56.mp4'))
        self.assertTrue(cap.isOpened())
        try:
            for second, state in [(0, UIState.UNKNOWN), (4, UIState.CONSTELLATION),
                                  (16, UIState.CONSTELLATION), (24, UIState.ADD_FRIENDS),
                                  (28, UIState.LIST), (34, UIState.LIST), (38, UIState.LIST),
                                  (40, UIState.LIST)]:
                cap.set(cv2.CAP_PROP_POS_MSEC, second*1000)
                ok, frame = cap.read()
                self.assertTrue(ok)
                with self.subTest(second=second):
                    self.assertEqual(observe(frame).state, state)
        finally:
            cap.release()

    def test_page_identity_survives_resolution_and_video(self):
        frame = cv2.imread(str(ROOT/'media/new/list-mode/page_0.jpg'))
        original = observe(frame)
        self.assertTrue(same_page(original.page, observe(cv2.resize(frame, (1280,720))).page))
        other = observe(cv2.imread(str(ROOT/'media/new/list-mode/page_1.jpg')))
        self.assertFalse(same_page(original.page, other.page))

    def test_video_actions_during_orbit_animation_and_selection(self):
        labels = json.loads((ROOT/'tests/baseline_labels.json').read_text())['pages']
        cap = cv2.VideoCapture(str(ROOT/'media/new/2026-10-27 23-37-56.mp4'))
        try:
            for second, page in [(28,0),(29,0),(30,1),(31,2),(32,2),(33,3),
                                 (34,4),(35,5),(37,6),(38,7),(40,0)]:
                cap.set(cv2.CAP_PROP_POS_MSEC, second*1000)
                ok, frame = cap.read()
                self.assertTrue(ok)
                label = labels[f'page_{page}.jpg']
                expected = {(c,r):([c,r] not in label['already_lit'], [c,r] in label['collect'])
                            for c in range(3) for r in range(7) if [c,r] not in label['empty']}
                with self.subTest(second=second):
                    o = observe(frame)
                    self.assertEqual(o.state, UIState.LIST)
                    self.assertEqual({f.slot:(f.needs_light,f.needs_collect) for f in o.friends}, expected)
        finally:
            cap.release()


class ControllerTests(unittest.TestCase):
    def setup_controller(self, light=True, collect=True, broken=False):
        self.state = UIState.LIST
        self.light, self.collect = light, collect
        self.events = []
        self.now = 0

        def read():
            friends = (Friend(0, 0, (574, 384), self.light, self.collect, .99),)
            return Observation(self.state, friends if self.state == UIState.LIST else (), PAGE)

        def key(key):
            self.events.append(key)
            if broken:
                return
            if key == 'f':
                self.state = UIState.FRIEND
                self.light = False
            elif key == 'esc':
                self.state = UIState.LIST

        def click(*point):
            self.events.append(('collect', point))
            if not broken:
                self.collect = False

        def open_friend(*point):
            self.events.append(('open', point))
            self.state = UIState.LIGHT_READY

        def sleep(duration):
            self.now += duration

        controller = Controller(lambda: None, key, click, open_friend, sleep=sleep,
                                clock=lambda: self.now, checks=3)
        return controller, read

    def test_both_actions_queue_and_verified_completion(self):
        c, read = self.setup_controller()
        queue = plan_page(read())
        self.assertEqual([a.kind for a in queue], ['collect', 'light'])
        with patch('automation.observe', side_effect=lambda _:read()):
            c.process_page(read())
        self.assertEqual(self.events, [('collect',(574,384)), ('open',(574,384)), 'f', 'esc'])
        self.assertEqual((c.lit, c.collected), (1,1))
        self.assertEqual(len(c.queue), 0)

    def test_failed_collection_never_dequeues_or_counts(self):
        c, read = self.setup_controller(broken=True)
        with patch('automation.observe', side_effect=lambda _:read()):
            with self.assertRaises(AutomationError):
                c.process_page(read())
        self.assertEqual((c.lit, c.collected), (0,0))
        self.assertEqual(len(c.queue), 2)
        self.assertEqual(len(self.events), 1)

    def test_pause_cancels_before_any_input(self):
        c, read = self.setup_controller()
        c.guard = Mock(side_effect=AutomationPaused('test'))
        with self.assertRaises(AutomationPaused):
            c.process_page(read())
        self.assertEqual(self.events, [])

    def test_planning_budget_stops_before_inputs(self):
        c, read = self.setup_controller()
        c.last_analysis_seconds = 1.01
        with self.assertRaises(AutomationError):
            c.process_page(read())
        self.assertEqual(self.events, [])

    def test_unknown_ui_never_receives_timer_key(self):
        c, read = self.setup_controller(collect=False)
        self.state = UIState.UNKNOWN
        with patch('automation.observe', side_effect=lambda _:read()):
            with self.assertRaises(AutomationError):
                c.race_panel(.2)
        self.assertEqual(self.events, [])

    def test_vision_beats_timer_and_confirmed_panel_timer_fallback(self):
        c, read = self.setup_controller()
        self.state = UIState.LIGHT_READY
        with patch('automation.observe', side_effect=lambda _:read()):
            c.race_panel(.9)
        self.assertLess(self.now, .9)
        self.now = 0
        self.state = UIState.FRIEND
        with patch('automation.observe', side_effect=lambda _:read()):
            c.race_panel(.9)
        self.assertGreaterEqual(self.now, .9)

    def test_completed_page_wrap_terminates(self):
        c, read = self.setup_controller(light=False, collect=False)
        pages = iter([PAGE, OTHER_PAGE, PAGE])
        observations = [Observation(UIState.LIST, read().friends, p) for p in pages]
        c.list_ui = Mock(return_value=observations[0])
        c.process_page = Mock(side_effect=lambda o:o)
        c.wait = Mock(side_effect=observations[1:])
        self.assertEqual(c.run(), (0,0))
        self.assertEqual(c.process_page.call_count, 2)

    def test_scan_only_queues_all_actions_without_friend_inputs(self):
        c, read = self.setup_controller()
        observations = [Observation(UIState.LIST, read().friends, p)
                        for p in (PAGE, OTHER_PAGE, PAGE)]
        c.list_ui = Mock(return_value=observations[0])
        c.wait = Mock(side_effect=observations[1:])
        c.click = Mock(side_effect=AssertionError('collection in scan-only'))
        c.open_friend = Mock(side_effect=AssertionError('friend opened in scan-only'))
        c.on_plan = Mock()
        self.assertEqual(c.run(scan_only=True), (0,0))
        self.assertEqual(self.events, ['c', 'c'])
        self.assertEqual(c.on_plan.call_count, 2)
        for call in c.on_plan.call_args_list:
            self.assertEqual([a.kind for a in call.args[1]], ['collect', 'light'])

    def test_scan_only_budget_failure_prevents_page_navigation(self):
        c, read = self.setup_controller()
        c.list_ui = Mock(return_value=read())
        c.last_analysis_seconds = 1.01
        with self.assertRaises(AutomationError):
            c.run(scan_only=True)
        self.assertEqual(self.events, [])


class ScanReportTests(unittest.TestCase):
    def test_cli_reports_completed_and_partial_scans(self):
        import main
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory(dir=ROOT/'cache') as directory:
                report = Path(directory)/'scan.json'
                friend = Friend(0,0,(574,384), True, True, .99)
                observation = Observation(UIState.LIST, (friend,), PAGE)
                safe = Mock(generation=0)

                def factory(*args, **kwargs):
                    controller = Mock(lit=0, collected=0)

                    def run(**options):
                        self.assertTrue(options['scan_only'])
                        for _ in range(2):  # a resumed/repeated page must not duplicate totals
                            kwargs['on_plan'](observation, tuple(plan_page(observation)), .05)
                        if fail:
                            raise AutomationError('transition failed')
                    controller.run.side_effect = run
                    return controller

                with patch('sys.argv', ['main.py','--scan-only','--report',str(report)]), \
                     patch('safety.WindowsSafety', return_value=safe), \
                     patch('automation.Controller', side_effect=factory), \
                     patch.object(main.time, 'sleep'):
                    if fail:
                        with self.assertRaises(AutomationError):
                            main.main()
                    else:
                        main.main()
                data = json.loads(report.read_text())
                self.assertEqual(data['status'], 'incomplete' if fail else 'complete')
                self.assertEqual(data['totals'], {'friends':1, 'lighting':1, 'collecting':1,
                                                  'both':1, 'actions':2})
                self.assertEqual(len(data['pages']), 1)
                self.assertEqual([a['kind'] for a in data['pages'][0]['queue']], ['collect','light'])
                safe.close.assert_called_once()


class SafetyTests(unittest.TestCase):
    def safety(self):
        guard = WindowsSafety.__new__(WindowsSafety)
        guard.lock = threading.RLock()
        guard.paused = threading.Event()
        guard.held = {'f','esc'}
        guard.ahk = Mock()
        guard.generation = 0
        guard.focused = Mock(return_value=True)
        return guard

    def test_pause_releases_all_automation_keys(self):
        guard = self.safety()
        guard.pause('Backspace')
        self.assertTrue(guard.paused.is_set())
        self.assertFalse(guard.held)
        self.assertEqual(guard.ahk.key_up.call_count, 2)
        with self.assertRaises(AutomationPaused):
            guard.action(Mock())

    def test_focus_loss_blocks_input_and_releases_keys(self):
        guard = self.safety()
        guard.focused.return_value = False
        action = Mock()
        with self.assertRaises(AutomationPaused):
            guard.action(action)
        action.assert_not_called()
        self.assertFalse(guard.held)

    def test_key_backend_failure_still_releases(self):
        guard = self.safety()
        guard.held.clear()
        guard.ahk.key_down.side_effect = RuntimeError('backend failed')
        with self.assertRaises(RuntimeError):
            guard.key('f')
        guard.ahk.key_up.assert_called_once_with('f')
        self.assertFalse(guard.held)

    def test_quick_pause_resume_cannot_execute_stale_actions(self):
        guard = self.safety()
        guard.pause('minus')
        guard.paused.clear()
        action = Mock()
        with self.assertRaises(AutomationPaused):
            guard.action(action, generation=0)
        action.assert_not_called()

    def test_focus_is_checked_between_friend_clicks(self):
        guard = self.safety()
        guard.ahk.click.side_effect = lambda *args, **kwargs: setattr(
            guard.focused, 'return_value', False)
        with self.assertRaises(AutomationPaused):
            guard.open_friend(100, 200, generation=0)
        self.assertEqual(guard.ahk.click.call_count, 1)

    def test_pause_key_polling_and_explicit_resume(self):
        for virtual_key in (0xBD, 0x6D, 0x08):
            guard = self.safety()
            guard.stopped = Mock()
            guard.stopped.wait.side_effect = [False, False, True]
            guard.user = Mock()
            tick = [0]

            def key_state(key):
                if key == 0xBB:
                    tick[0] += 1
                    return 0x8000 if tick[0] == 2 else 0
                return 0x8000 if tick[0] == 0 and key == virtual_key else 0

            guard.user.GetAsyncKeyState.side_effect = key_state
            guard.watch()
            self.assertEqual(guard.generation, 1)
            self.assertFalse(guard.paused.is_set())
            self.assertFalse(guard.held)


if __name__ == '__main__':
    unittest.main()
