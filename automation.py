"""Bounded, observation-driven UI state machine; input is injected for replay."""
import time
from collections import deque
from dataclasses import dataclass
from detector import UIState, observe, same_page


class AutomationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Action:
    kind: str
    slot: tuple[int, int]


def plan_page(observation):
    """One snapshot -> a complete ordered queue; collect before lighting BOTH."""
    if observation.state != UIState.LIST:
        raise AutomationError('Cannot plan actions outside a verified list page')
    return deque(Action(kind, friend.slot) for friend in observation.friends
                 for kind, needed in [('collect', friend.needs_collect), ('light', friend.needs_light)]
                 if needed)


class Controller:
    def __init__(self, capture, key, click, open_friend, *, sleep=time.sleep,
                 checks=30, guard=lambda: None, clock=time.monotonic, on_plan=lambda *args: None):
        self.capture, self.key, self.click = capture, key, click
        self.open_friend, self.sleep = open_friend, sleep
        self.checks = checks
        self.guard, self.clock = guard, clock
        self.queue = deque()
        self.on_plan = on_plan
        self.state = UIState.UNKNOWN
        self.lit = self.collected = 0
        self.history = []
        self.last_analysis_seconds = 0.

    def read(self):
        self.guard()
        started = self.clock()
        observation = observe(self.capture())
        self.last_analysis_seconds = self.clock() - started
        if observation.state != self.state:
            self.history.append((self.state.value, observation.state.value))
            self.state = observation.state
            print(f'UI: {self.state.value}')
        return observation

    def wait(self, predicate, reason):
        # Two consistent observations keep transient fades from authorizing input.
        previous = None
        for _ in range(self.checks):
            current = self.read()
            if predicate(current):
                if previous is not None and previous.state == current.state and (
                        current.state != UIState.LIST or (
                            same_page(previous.page, current.page) and
                            [(f.slot, f.needs_light, f.needs_collect) for f in previous.friends] ==
                            [(f.slot, f.needs_light, f.needs_collect) for f in current.friends])):
                    return current
                previous = current
            else:
                previous = None
            self.sleep(.2)
        raise AutomationError(f'Timed out waiting for {reason}; last UI: {self.state.value}')

    def list_ui(self):
        current = self.wait(lambda o: o.state != UIState.UNKNOWN, 'recognized UI')
        if current.state in (UIState.FRIEND, UIState.LIGHT_READY):
            self.key('esc')
            current = self.wait(lambda o: o.state in (UIState.LIST, UIState.CONSTELLATION),
                                'friend panel to close')
        if current.state == UIState.WORLD:
            self.key('f')
            current = self.wait(lambda o: o.state in (UIState.LIST, UIState.CONSTELLATION,
                                                     UIState.ADD_FRIENDS), 'friend UI to open')
        if current.state == UIState.ADD_FRIENDS:
            self.key('c')
            current = self.wait(lambda o: o.state in (UIState.LIST, UIState.CONSTELLATION),
                                'friends page')
        if current.state == UIState.CONSTELLATION:
            self.key('g')
            current = self.wait(lambda o: o.state == UIState.LIST, 'list view')
        if current.state != UIState.LIST:
            raise AutomationError('Cannot enter calibrated list view')
        return current

    @staticmethod
    def friend_on(observation, page, slot):
        if observation.state != UIState.LIST or not same_page(observation.page, page):
            return None
        return next((f for f in observation.friends if f.slot == slot), None)

    def prepare_page(self, current):
        started = self.clock()
        self.queue = plan_page(current)
        planning_seconds = self.last_analysis_seconds + self.clock() - started
        if planning_seconds >= 1:
            raise AutomationError(f'Page planning exceeded one second ({planning_seconds:.3f}s)')
        print(f'Queued {len(self.queue)} actions in {planning_seconds:.3f}s')
        self.on_plan(current, tuple(self.queue), planning_seconds)

    def process_page(self, current):
        page = current.page
        self.prepare_page(current)
        while self.queue:
            current = self.wait(lambda o: o.state == UIState.LIST and same_page(o.page, page),
                                'original list page')
            action = self.queue[0]
            friend = self.friend_on(current, page, action.slot)
            if friend is None:
                raise AutomationError(f'Queued friend disappeared: {action.slot}')
            if not (friend.needs_collect if action.kind == 'collect' else friend.needs_light):
                self.queue.popleft()
                continue
            if action.kind == 'collect':
                self.click(*friend.center)
                current = self.wait(
                    lambda o: (f := self.friend_on(o, page, friend.slot)) is not None and
                    not f.needs_collect, 'collection satellites to disappear')
                self.collected += 1
                self.queue.popleft()
                continue
            self.open_friend(*friend.center)
            self.race_panel(.9)
            self.key('f')
            self.race_panel(.2, after_light=True)
            self.key('esc')
            current = self.wait(
                lambda o: (f := self.friend_on(o, page, friend.slot)) is not None and
                not f.needs_light, 'friend to be lit on original list page')
            self.lit += 1
            self.queue.popleft()
        remaining = [f for f in current.friends if f.needs_collect or f.needs_light]
        if remaining:
            raise AutomationError('Page still has pending work after draining its queue')
        return current

    def race_panel(self, delay, after_light=False):
        """Vision may beat a fixed timer, but a timer never authorizes unknown UI.

        Post-open: LIGHT_READY wins early; a confirmed friend panel permits the
        timed F fallback. Post-F: FRIEND wins early, otherwise wait the fixed
        animation delay before closing. Final list appearance verifies success.
        """
        deadline = self.clock() + delay
        early_state = UIState.FRIEND if after_light else UIState.LIGHT_READY
        previous = None
        for _ in range(max(self.checks, 60)):
            current = self.read()
            if current.state == early_state and previous == early_state:
                return
            if self.clock() >= deadline and current.state in (UIState.FRIEND, UIState.LIGHT_READY):
                return
            previous = current.state
            self.sleep(.05)
        raise AutomationError('Friend panel was not confirmed before timer action')

    def run(self, max_pages=32, *, scan_only=False):
        current = self.list_ui()
        seen = []
        for _ in range(max_pages):
            if any(same_page(current.page, p) for p in seen):
                return self.lit, self.collected
            seen.append(current.page)
            print(f'{"Scanning" if scan_only else "Processing"} list page {len(seen)}: '
                  f'{len(current.friends)} friends')
            if scan_only:
                self.prepare_page(current)
            else:
                current = self.process_page(current)
            old_page = current.page
            self.key('c')
            current = self.wait(lambda o: o.state in (UIState.LIST, UIState.ADD_FRIENDS) and
                                (o.state != UIState.LIST or not same_page(o.page, old_page)),
                                'next list page')
            if current.state == UIState.ADD_FRIENDS:
                self.key('c')
                current = self.wait(lambda o: o.state == UIState.LIST, 'list after Add Friends')
        raise AutomationError('Page limit reached before a verified wraparound')
