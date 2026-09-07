import unittest
from dataclasses import replace
from collector.config import Config
from collector.controller import Runner, TransitionError
from collector.models import Box, FriendTarget, Observation, State


class Simulation:
    """Actions schedule visual responses; advancing fake time never touches a desktop."""

    def __init__(
        self, state=State.PAGE, light=True, collect=False, ignore=0, delay=0.12
    ):
        self.time = 0.0
        self.state = state
        self.light = light
        self.collect = collect
        self.ignore = ignore
        self.delay = delay
        self.events = []
        self.event_times = []
        self.pending = []
        self.page = 0 if state == State.INDEX else 1
        self.dialog_done = False
        self.shift = 0.0

    def sleep(self, duration):
        self.time += duration

    def nudge(self):
        self.event_times.append((self.time, "nudge", (1, 0)))

    def move(self, point):
        self.event_times.append((self.time, "move", point))

    def capture(self):
        while self.pending and self.pending[0][0] <= self.time:
            _, fn = self.pending.pop(0)
            fn()
        anchors = {}
        if self.state == State.SELECTED:
            anchors["candle"] = Box(450, 200, 40, 40)
        if self.state in (State.SELECTED, State.UNKNOWN) and self.dialog_done:
            anchors["esc"] = Box(900, 650, 30, 20)
        target = FriendTarget(
            Box(400 + self.shift, 300, 32, 32),
            0.98,
            self.light,
            self.collect,
            ((416 + self.shift) / 1000, 0.45),
            {},
        )
        return (
            Observation(
                self.state,
                Box(0, 0, 1000, 700),
                [target] if self.state == State.PAGE else [],
                anchors,
                (3, self.page) if self.state in (State.PAGE, State.INDEX) else (),
            ),
            0.0,
        )

    def analyze(self, image):
        return image

    def schedule(self, fn):
        self.pending.append((self.time + self.delay, fn))

    def click(self, point):
        self.events.append(("click", point))
        self.event_times.append((self.time, "click", point))
        if self.ignore:
            self.ignore -= 1
            self.shift += 2
            return
        if self.collect:
            self.schedule(lambda: setattr(self, "collect", False))
        else:
            self.schedule(lambda: setattr(self, "state", State.SELECTED))

    def key(self, key):
        self.events.append(("key", key))
        self.event_times.append((self.time, "key", key))
        if self.ignore:
            self.ignore -= 1
            return

        def response():
            if key in ("c", "z"):
                if key == "c":
                    self.page = (self.page + 1) % 3
                else:
                    self.page = max(0, self.page - 1)
                self.state = State.INDEX if self.page == 0 else State.PAGE
            elif key == "f" and self.state == State.ENTRY:
                self.state = State.INDEX
                self.page = 0
            elif key == "f":
                self.light = False
                self.dialog_done = True
                self.state = State.UNKNOWN
            elif key == "esc":
                self.state = State.PAGE
                self.dialog_done = False

        self.schedule(response)


def runner(sim, **overrides):
    values = dict(
        transition_timeout=0.6,
        stable_seconds=0.12,
        poll_interval=0.04,
        friend_click_settle_seconds=0.12,
    )
    values.update(overrides)
    config = replace(
        Config(),
        **values,
    )
    return Runner(sim, sim, sim, config, clock=lambda: sim.time, pause=sim.sleep)


class ControllerTests(unittest.TestCase):
    def test_ignored_selection_reacquires_then_verifies_light(self):
        sim = Simulation(ignore=1)
        r = runner(sim)
        target = r.observe().targets[0]
        r.light(target, (3, 1))
        clicks = [value for kind, value in sim.events if kind == "click"]
        self.assertEqual(len(clicks), 2)
        self.assertNotEqual(clicks[0], clicks[1])
        self.assertFalse(sim.light)
        self.assertEqual(sim.events.count(("key", "f")), 1)

    def test_delayed_selection_does_not_duplicate(self):
        sim = Simulation(delay=0.35)
        r = runner(sim)
        r.light(r.observe().targets[0], (3, 1))
        self.assertEqual(sum(k == "click" for k, _ in sim.events), 1)

    def test_ignored_collection_retries_and_verifies(self):
        sim = Simulation(collect=True, ignore=1)
        r = runner(sim)
        r.collect(r.observe().targets[0], (3, 1))
        self.assertFalse(sim.collect)
        self.assertEqual(sum(k == "click" for k, _ in sim.events), 2)

    def test_permanent_noop_is_bounded(self):
        sim = Simulation(ignore=100)
        r = runner(sim)
        with self.assertRaises(TransitionError):
            r.light(r.observe().targets[0], (3, 1))
        self.assertEqual(len(sim.events), 3)

    def test_navigation_requires_changed_page_marker(self):
        sim = Simulation(ignore=1)
        r = runner(sim)
        self.assertEqual(r.navigate("c").page_token, (3, 2))
        self.assertEqual(sim.events, [("key", "c"), ("key", "c")])

    def test_navigation_waits_before_capturing_even_when_tab_changes_early(self):
        sim = Simulation(ignore=1, delay=0.01)
        r = runner(sim)
        capture = sim.capture
        capture_times = []

        def recorded_capture():
            capture_times.append(sim.time)
            return capture()

        sim.capture = recorded_capture
        self.assertEqual(r.navigate("c").page_token, (3, 2))
        self.assertEqual(Config().page_transition_settle_seconds, 1.3)
        presses = [time for time, kind, key in sim.event_times if key == "c"]
        self.assertEqual(len(presses), 2)
        for pressed_at in presses:
            first_capture = next(time for time in capture_times if time > pressed_at)
            self.assertGreaterEqual(first_capture - pressed_at, 1.3 - 1e-9)

    def test_unknown_screen_sends_no_keys_even_in_recovery(self):
        sim = Simulation(state=State.UNKNOWN)
        r = runner(sim)
        with self.assertRaises(TransitionError):
            r.run()
        self.assertEqual(sim.events, [])

    def test_page_failure_never_reindexes(self):
        sim = Simulation(state=State.INDEX)
        r = runner(sim)
        def fail(page):
            raise TransitionError("ambiguous page")
        r.process_page = fail
        with self.assertRaisesRegex(TransitionError, "ambiguous page"):
            r.run()
        self.assertEqual(sim.events, [("key", "z")] * 5 + [("key", "c")])

    def test_ambiguous_friend_does_not_block_page_advance(self):
        sim = Simulation(state=State.INDEX, light=None, collect=False)
        runner(sim).run()
        self.assertEqual(sim.events, [("key", "z")] * 5 + [("key", "c")] * 2)

    def test_plan_skips_ambiguous_friend_but_keeps_confirmed_actions(self):
        sim = Simulation(collect=True)
        r = runner(sim)
        observation = r.observe()
        confirmed = observation.targets[0]
        observation.targets.append(replace(confirmed, needs_light=None))
        self.assertEqual(r.plan_actions(observation), ((confirmed, "collect"), (confirmed, "light")))

    def test_empty_verified_page_advances_without_clicking(self):
        sim = Simulation(state=State.INDEX, light=False)
        capture = sim.capture
        def empty_capture():
            observation, ms = capture()
            observation.targets = []
            return observation, ms
        sim.capture = empty_capture
        runner(sim).run()
        self.assertEqual(sim.events, [("key", "z")] * 5 + [("key", "c")] * 2)
        nudges = [time for time, kind, _ in sim.event_times if kind == "nudge"]
        presses = [time for time, kind, value in sim.event_times if kind == "key" and value == "c"]
        self.assertEqual(len(nudges), 2)
        parks = [time for time, kind, value in sim.event_times if kind == "move" and value == (500, 0)]
        self.assertEqual(len(parks), 2)
        for pressed, nudged, parked in zip(presses, nudges, parks):
            self.assertEqual(nudged, pressed)
            self.assertEqual(parked, pressed)
        events = [(kind, value) for _, kind, value in sim.event_times]
        for index, event in enumerate(events):
            if event == ("key", "c"):
                self.assertEqual(events[index - 1], ("nudge", (1, 0)))

    def test_index_right_process_through_last_page_without_wrapping(self):
        sim = Simulation(state=State.INDEX, light=False)
        r = runner(sim)
        r.run()
        self.assertEqual(sim.events, [("key", "z")] * 5 + [("key", "c")] * 2)

    def test_run_resets_with_z_before_first_friend_page(self):
        sim = Simulation(state=State.PAGE, light=False)
        r = runner(sim)
        r.run()
        self.assertEqual(sim.events, [("key", "z")] * 5 + [("key", "c")] * 2)

    def test_both_opening_dialog_gets_f_without_reselecting(self):
        sim = Simulation(collect=True)
        def open_friend(point):
            sim.events.append(("click", point))
            sim.event_times.append((sim.time, "click", point))
            sim.schedule(lambda: setattr(sim, "state", State.SELECTED))
        sim.click = open_friend
        r = runner(sim, friend_click_settle_seconds=2.1)
        r.process_page()
        self.assertFalse(sim.light)
        self.assertTrue(sim.collect)  # Persistent particles must not cause replay.
        self.assertEqual([k for k, _ in sim.events], ["click", "key", "key"])
        times = [time for time, _, _ in sim.event_times]
        self.assertAlmostEqual(times[1] - times[0], 2.1)
        self.assertAlmostEqual(times[2] - times[1], 0.3)

    def test_lighting_waits_from_click_before_pressing_f(self):
        sim = Simulation(delay=0.08)
        r = runner(sim, friend_click_settle_seconds=0.32)
        r.light(r.observe().targets[0], (3, 1))
        click_time = next(time for time, kind, _ in sim.event_times if kind == "click")
        light_time = next(
            time
            for time, kind, value in sim.event_times
            if kind == "key" and value == "f"
        )
        self.assertGreaterEqual(light_time - click_time, 0.32)

    def test_production_friend_settle_interval_is_1_2_seconds(self):
        self.assertAlmostEqual(Config().friend_click_settle_seconds, 1.2)

    def test_queued_friend_survives_missing_fresh_detection(self):
        sim = Simulation()
        r = runner(sim, friend_click_settle_seconds=1.2)
        target = r.observe().targets[0]
        capture = sim.capture
        def missing_capture():
            o, ms = capture()
            o.targets = []
            return o, ms
        sim.capture = missing_capture
        r.visit_friend(target, (3, 1))
        self.assertEqual([kind for kind, _ in sim.events], ["click", "key", "key"])
        self.assertFalse(sim.light)

    def test_queued_friend_survives_changed_classification(self):
        sim = Simulation(collect=True)
        r = runner(sim, friend_click_settle_seconds=1.2)
        target = r.observe().targets[0]
        sim.collect = False
        r.visit_friend(target, (3, 1))
        self.assertEqual([kind for kind, _ in sim.events], ["click", "key", "key"])

    def test_light_waits_before_escape_and_before_recapturing(self):
        sim = Simulation()
        r = runner(sim)
        capture = sim.capture
        captured = []
        def record():
            captured.append(sim.time)
            return capture()
        sim.capture = record
        r.light(r.observe().targets[0], (3, 1))
        keys = [(time, key) for time, kind, key in sim.event_times if kind == "key"]
        self.assertEqual([key for _, key in keys], ["f", "esc"])
        self.assertAlmostEqual(keys[1][0] - keys[0][0], 0.3)
        self.assertGreaterEqual(next(t for t in captured if t > keys[1][0]) - keys[1][0], 0.2 - 1e-9)

    def test_page_plan_is_complete_before_first_target_click(self):
        sim = Simulation(collect=True)
        r = runner(sim)
        r.process_page()
        self.assertEqual(
            [kind for _, kind, _ in sim.event_times], ["click"]
        )

    def test_click_target_refuses_a_friend_without_a_confirmed_action(self):
        sim = Simulation(light=False, collect=False)
        r = runner(sim)
        observation = r.observe()
        with self.assertRaises(TransitionError):
            r.click_target(observation, observation.targets[0])
        self.assertEqual(sim.events, [])

    def test_entry_requires_positive_anchor_state(self):
        sim = Simulation(state=State.ENTRY, light=False)
        r = runner(sim)
        self.assertEqual(r.index().state, State.INDEX)
        self.assertEqual(sim.events, [("key", "f")] + [("key", "z")] * 5)

    def test_disappearing_target_is_not_success(self):
        sim = Simulation()
        r = runner(sim)
        sim.state = State.UNKNOWN
        with self.assertRaises(TransitionError):
            r.navigate("c")
        self.assertEqual(sim.events, [])

    def test_page_change_before_processing_sends_no_input(self):
        sim = Simulation()
        r = runner(sim)
        with self.assertRaises(TransitionError):
            r.process_page((3, 2))
        self.assertEqual(sim.events, [])

    def test_unexpected_dialog_is_not_treated_as_target_selection(self):
        sim = Simulation()
        r = runner(sim)
        target = r.observe().targets[0]
        sim.state = State.SELECTED
        with self.assertRaises(TransitionError):
            r.light(target, (3, 1))
        self.assertEqual(sim.events, [])

    def test_polling_requires_persistent_evidence(self):
        sim = Simulation()
        r = runner(sim)
        result = r.wait(lambda o: int(sim.time / 0.04) % 2 == 0)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
