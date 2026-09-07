"""Bounded state machine. All success conditions use fresh observations."""

import logging
from time import monotonic, sleep
from .config import Config
from .models import State

log = logging.getLogger(__name__)


class TransitionError(RuntimeError):
    pass


def reacquire(observation, target):
    matches = [
        t
        for t in observation.targets
        if sum((a - b) ** 2 for a, b in zip(t.relative, target.relative)) < 0.018**2
    ]
    return matches[0] if len(matches) == 1 else None


class Runner:
    def __init__(
        self,
        detector,
        capture,
        input_device,
        config=Config(),
        clock=monotonic,
        pause=sleep,
        recorder=None,
    ):
        self.detector, self.capture, self.input = detector, capture, input_device
        self.config, self.clock, self.pause = config, clock, pause
        self.metrics = []
        self.last = None
        self.recorder = recorder

    def observe(self):
        image, capture_ms = self.capture.capture()
        self.last = self.detector.analyze(image)
        self.last.timings["capture_ms"] = capture_ms
        if self.recorder:
            self.recorder.frame(image, "observation", self.last)
        self.metrics.append(dict(self.last.timings))
        log.debug(
            "state=%s page=%s timings=%s",
            self.last.state.value,
            self.last.page_token,
            self.last.timings,
        )
        return self.last

    def wait(self, predicate):
        deadline = self.clock() + self.config.transition_timeout
        since = None
        while self.clock() < deadline:
            o = self.observe()
            if predicate(o):
                if since is None:
                    since = self.clock()
                if self.clock() - since >= self.config.stable_seconds:
                    return o
            else:
                since = None
            self.pause(self.config.poll_interval)
        self.report_observation("wait timed out")
        return None

    def report_observation(self, reason):
        o = self.last
        if o is None:
            log.info("[diagnostic] %s: no observation available", reason)
            return
        log.info(
            "[diagnostic] %s: state=%s page=%s viewport=%s anchors=%s friends=%d warnings=%s timings=%s",
            reason, o.state.value, o.page_token, o.viewport,
            sorted(o.anchors), len(o.targets), o.warnings, o.timings,
        )
        for number, target in enumerate(o.targets, 1):
            log.info(
                "[target %d] center=%s confidence=%.3f light=%s collect=%s ambiguous=%s evidence=%s",
                number, target.center, target.confidence, target.needs_light,
                target.collectible, target.ambiguous, target.evidence,
            )

    def navigate(self, key):
        before = self.observe()
        if before.state not in (State.INDEX, State.PAGE) or not before.page_token:
            raise TransitionError(
                "Navigation requires constellation anchors and a pagination marker"
            )
        expected = (
            before.page_token[0],
            (before.page_token[1] + (1 if key == "c" else -1)) % before.page_token[0],
        )
        for attempt in range(self.config.retries):
            current = self.observe()
            if (
                current.state in (State.INDEX, State.PAGE)
                and current.page_token == expected
            ):
                settled = self.wait(
                    lambda o: o.state in (State.INDEX, State.PAGE)
                    and o.page_token == expected
                )
                if settled:
                    return settled
            if (
                current.state not in (State.INDEX, State.PAGE)
                or current.page_token != before.page_token
            ):
                raise TransitionError("Navigation landed in an unexpected state/page")
            log.info("[navigation] from=%s expected=%s attempt=%d/%d", before.page_token, expected, attempt + 1, self.config.retries)
            self.input.nudge()
            self.input.key(key)
            self.input.move((500, 0))
            # The tab marker changes before the friend stars finish animating.
            # Do not capture transition frames or use them for the page census.
            log.info(
                "[navigation] waiting %.1fs for page animation",
                self.config.page_transition_settle_seconds,
            )
            self.pause(self.config.page_transition_settle_seconds)
            result = self.wait(
                lambda o: o.state in (State.INDEX, State.PAGE)
                and o.page_token == expected
            )
            if result:
                log.info(
                    "[navigation] page transition confirmed: %s", result.page_token
                )
                return result
            log.warning(
                "[navigation] no confirmed transition; retry %d/%d",
                attempt + 1,
                self.config.retries,
            )
        raise TransitionError("Page navigation ignored or did not settle")

    def force_leftmost_index(self, observation):
        """Force the non-wrapping constellation tabs to their leftmost index."""
        if (
            observation.state not in (State.INDEX, State.PAGE)
            or not observation.page_token
        ):
            raise TransitionError(
                "Cannot reset tabs without a recognized friend constellation"
            )

        tab_count, _ = observation.page_token
        presses = tab_count + self.config.index_reset_extra_presses
        for batch in range(self.config.max_index_reset_batches):
            for _ in range(presses):
                self.input.key("z")
                self.pause(self.config.index_reset_key_interval)
            settled = self.wait(
                lambda x: x.state == State.INDEX and x.page_token == (tab_count, 0)
            )
            if settled:
                log.info(
                    "[navigation] leftmost index confirmed after %d Z presses", presses
                )
                return settled
            current = self.observe()
            if current.state not in (State.INDEX, State.PAGE) or not current.page_token:
                raise TransitionError(
                    "Constellation tabs disappeared while resetting to index"
                )
            if current.page_token[0] != tab_count:
                raise TransitionError(
                    "Constellation tab count changed while resetting to index"
                )
            log.warning(
                "[navigation] index not confirmed after Z batch %d/%d",
                batch + 1,
                self.config.max_index_reset_batches,
            )
        raise TransitionError("Leftmost constellation index was not confirmed")

    def index(self):
        o = self.observe()
        if o.state == State.UNKNOWN:
            settled = self.wait(
                lambda x: x.state
                in (State.ENTRY, State.INDEX, State.PAGE, State.SELECTED)
            )
            if settled is not None:
                o = settled
        if o.state == State.ENTRY:
            for attempt in range(self.config.retries):
                o = self.observe()
                if o.state in (State.INDEX, State.PAGE):
                    break
                if o.state != State.ENTRY:
                    raise TransitionError(
                        "Entry anchor disappeared; no blind entry key"
                    )
                self.input.key("f")
                result = self.wait(lambda x: x.state in (State.INDEX, State.PAGE))
                if result:
                    o = result
                    break
                log.warning(
                    "[entry] no confirmed entry; retry %d/%d",
                    attempt + 1,
                    self.config.retries,
                )
        if o.state == State.SELECTED:
            o = self.close_friend()
        if o.state not in (State.INDEX, State.PAGE):
            raise TransitionError("Cannot recover: no recognized constellation tabs")
        return self.force_leftmost_index(o)

    def close_friend(self):
        for attempt in range(self.config.retries):
            o = self.observe()
            if o.state == State.PAGE:
                return o
            if o.state != State.SELECTED and "esc" not in o.anchors:
                raise TransitionError("Friend dialog lost its back control")
            self.input.key("esc")
            result = self.wait(lambda x: x.state == State.PAGE and bool(x.page_token))
            if result:
                return result
            log.warning(
                "[friend] close ignored; retry %d/%d", attempt + 1, self.config.retries
            )
        raise TransitionError("Friend dialog did not close")

    def same_page(self, o, page):
        return o.state == State.PAGE and o.page_token == page

    def click_target(self, observation, target):
        if observation.state != State.PAGE or target.ambiguous or not target.actions:
            raise TransitionError(
                "Refusing to click a target without a confirmed action"
            )
        if not (
            observation.viewport.x
            <= target.center[0]
            < observation.viewport.x + observation.viewport.w
            and observation.viewport.y
            <= target.center[1]
            < observation.viewport.y + observation.viewport.h
        ):
            raise TransitionError(
                "Refusing to click a target outside the detected game viewport"
            )
        self.input.click(target.center)
        # Hovering the star draws a ring that can hide its particles. Park without clicking.
        if "q_info" in observation.anchors:
            self.input.move(observation.anchors["q_info"].center)

    def collect(self, target, page):
        def done(o):
            t = reacquire(o, target)
            return self.same_page(o, page) and t is not None and t.collectible is False

        for attempt in range(self.config.retries):
            o = self.observe()
            if done(o):
                if self.wait(done):
                    return
                o = self.observe()
            t = reacquire(o, target)
            if not self.same_page(o, page) or t is None or t.ambiguous:
                raise TransitionError("Collect target could not be safely reacquired")
            self.click_target(o, t)
            if self.wait(done):
                log.info("[friend] collection verified")
                return
            if self.last.state == State.SELECTED:
                self.close_friend()
                if self.wait(done):
                    return
            log.warning(
                "[friend] collect click unconfirmed; retry %d/%d",
                attempt + 1,
                self.config.retries,
            )
        raise TransitionError("Collection did not produce a stable particle-free star")

    def light(self, target, page):
        selected = None
        clicked_at = None
        for attempt in range(self.config.retries):
            o = self.observe()
            if o.state == State.SELECTED:
                if attempt == 0:
                    raise TransitionError(
                        "A friend dialog opened before this target was clicked"
                    )
                selected = o
                break
            t = reacquire(o, target)
            if not self.same_page(o, page) or t is None or t.ambiguous:
                raise TransitionError("Selection target could not be safely reacquired")
            if t.needs_light is False:
                if self.wait(
                    lambda x: self.same_page(x, page)
                    and reacquire(x, target) is not None
                    and reacquire(x, target).needs_light is False
                ):
                    return
                raise TransitionError("Already-lit state did not remain stable")
            # Fresh center on every retry; never double-click a delayed animation.
            clicked_at = self.clock()
            self.click_target(o, t)
            selected = self.wait(
                lambda x: x.state == State.SELECTED and "candle" in x.anchors
            )
            if selected:
                break
            log.warning(
                "[friend] selection click ignored; retry %d/%d",
                attempt + 1,
                self.config.retries,
            )
        if not selected:
            raise TransitionError("Friend selection never opened the candle prompt")
        self.wait_for_friend_settle(clicked_at)
        self.input.key("f")
        log.info("[friend] waiting %.1fs after F", self.config.light_key_settle_seconds)
        self.pause(self.config.light_key_settle_seconds)
        self.input.key("esc")
        log.info("[friend] waiting %.1fs after Esc", self.config.friend_close_settle_seconds)
        self.pause(self.config.friend_close_settle_seconds)

        def done(o):
            t = reacquire(o, target)
            return self.same_page(o, page) and t is not None and t.needs_light is False

        if not self.wait(done):
            raise TransitionError(
                "Light action changed the dialog but star did not become lit"
            )
        log.info("[friend] lighting verified on the page")

    def wait_for_friend_settle(self, clicked_at):
        """Wait 1.1 seconds from the friend click while guarding the candle dialog."""
        if clicked_at is None:
            raise TransitionError("Friend selection has no recorded click time")
        deadline = clicked_at + self.config.friend_click_settle_seconds
        while self.clock() < deadline:
            o = self.observe()
            if o.state != State.SELECTED or "candle" not in o.anchors:
                raise TransitionError(
                    "Friend dialog changed before its settle interval elapsed"
                )
            self.pause(min(self.config.poll_interval, deadline - self.clock()))
        o = self.observe()
        if o.state != State.SELECTED or "candle" not in o.anchors:
            raise TransitionError(
                "Friend dialog did not remain stable for the settle interval"
            )
        log.info(
            "[friend] candle dialog remained stable for %.1fs",
            self.config.friend_click_settle_seconds,
        )

    @staticmethod
    def plan_actions(observation):
        """Build the complete page plan before any target click is issued.

        Coordinates are intentionally not trusted later: every planned target is
        reacquired from a fresh frame just before its action.
        """
        if observation.state != State.PAGE or not observation.page_token:
            raise TransitionError("Cannot plan actions outside a verified friend page")
        plan = []
        for target in observation.targets:
            if target.ambiguous:
                continue
            # Collect first: it can change the visual state before lighting.
            if target.collectible:
                plan.append((target, "collect"))
            if target.needs_light:
                plan.append((target, "light"))
        return tuple(plan)

    def visit_friend(self, target, page):
        """One queued visit; particle classification never triggers a replay."""
        o = self.observe()
        if not self.same_page(o, page):
            raise TransitionError("Queued friend's page changed")
        current = reacquire(o, target)
        log.info("[queue] using planned center=%s actions=%s; fresh_match=%s fresh_actions=%s", target.center, target.actions, current is not None, current.actions if current else None)
        self.click_target(o, target)
        log.info("[friend] waiting %.1fs after click", self.config.friend_click_settle_seconds)
        self.pause(self.config.friend_click_settle_seconds)
        selected = self.observe()
        if self.same_page(selected, page):
            log.info("[queue] click stayed on page (collection or ignored input); not replaying target %s", target.center)
            return
        if selected.state != State.SELECTED or "candle" not in selected.anchors:
            raise TransitionError("Queued friend did not show a recognized candle prompt after settling")
        self.input.key("f")
        log.info("[friend] waiting %.1fs after F", self.config.light_key_settle_seconds)
        self.pause(self.config.light_key_settle_seconds)
        self.input.key("esc")
        log.info("[friend] waiting %.1fs after Esc", self.config.friend_close_settle_seconds)
        self.pause(self.config.friend_close_settle_seconds)
        returned = self.observe()
        if not self.same_page(returned, page) and not self.wait(lambda x: self.same_page(x, page)):
            raise TransitionError("Friend cycle did not return to its constellation page")
        log.info("[queue] visit finished; advancing without particle-based retries")

    def process_page(self, expected_page=None):
        start = self.clock()
        o = self.observe()
        page = o.page_token
        if not self.same_page(o, page) or not page:
            raise TransitionError("No stable friend page")
        if expected_page is not None and page != expected_page:
            raise TransitionError(
                "Page changed between verified navigation and processing"
            )
        census = list(o.targets)
        log.info(
            "[page %s] %d friends; light=%d collect=%d both=%d",
            page[1],
            len(o.targets),
            sum(t.needs_light is True for t in o.targets),
            sum(t.collectible is True for t in o.targets),
            sum(t.needs_light is True and t.collectible is True for t in o.targets),
        )
        stable = self.wait(
            lambda x: self.same_page(x, page)
            and len(x.targets) == len(census)
            and all(reacquire(x, target) is not None for target in census)
        )
        if stable is None:
            latest = self.last
            ambiguous = sum(target.ambiguous for target in latest.targets)
            missing = sum(reacquire(latest, target) is None for target in census)
            raise TransitionError(
                "Page did not produce a stable, complete action plan: "
                f"state={latest.state.value}, page={latest.page_token}, "
                f"friends={len(latest.targets)} (expected {len(census)}), "
                f"ambiguous={ambiguous}, missing/moved={missing}"
            )
        plan = self.plan_actions(stable)
        self.report_observation("page plan")
        skipped = [target for target in stable.targets if target.ambiguous]
        if skipped:
            log.warning(
                "[page %s] skipping %d ambiguous friends; no clicks on these targets",
                page[1], len(skipped),
            )
        log.info("[page %s] planned %d actions before clicking", page[1], len(plan))
        if not plan:
            log.info("[page %s] no confirmed actions; advancing", page[1])
            return
        if len(plan) > self.config.max_actions_per_page:
            raise TransitionError("Per-page action plan exceeds the safety limit")
        queue = [target for target in stable.targets if target.actions]
        log.info("[queue] page=%s friends=%d (both actions share one visit)", page, len(queue))
        for index, target in enumerate(queue, 1):
            log.info("[queue] %d/%d page=%s center=%s actions=%s", index, len(queue), page, target.center, target.actions)
            self.visit_friend(target, page)
        log.info("[page %s] queue exhausted in %.2fs; skipped=%d", page[1], self.clock() - start, len(skipped))

    def run(self):
        self.index()
        o = self.navigate("c")
        for _ in range(self.config.max_pages):
            if o.state == State.INDEX:
                raise TransitionError("Unexpected index before the final page was completed")
            self.process_page(o.page_token)
            if o.page_token[1] == o.page_token[0] - 1:
                log.info("All pages completed; final pagination marker confirmed")
                return
            o = self.navigate("c")
        raise TransitionError("Page limit reached before the final pagination marker")
