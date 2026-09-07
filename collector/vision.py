"""No capture, input, sleeps, or disk writes. Coordinates refer to the input image."""

from pathlib import Path
from time import perf_counter
import cv2
import numpy as np
from .config import Config
from .models import Box, FriendTarget, Observation, State


class Detector:
    def __init__(self, assets: Path, config=Config()):
        self.config = config
        # These small ROIs do not benefit from a large OpenCV worker pool.
        cv2.setNumThreads(config.opencv_threads)
        self.templates = {}
        # One canonical pack; these names refer to historical asset provenance only.
        for name in (
            "esc",
            "q_info",
            "add_friends",
            "const",
            "candle",
            "lit_friend",
            "unlit_friend",
        ):
            im = cv2.imread(str(assets / "ui" / (name + ".png")), cv2.IMREAD_GRAYSCALE)
            if im is None:
                raise ValueError(f"Missing template: {name}")
            self.templates[name] = im
        self.scaled = {}

    def template(self, name, scale):
        original = self.templates[name]
        size = tuple(max(3, round(v * scale)) for v in original.shape[::-1])
        key = name, size
        if key not in self.scaled:
            self.scaled[key] = cv2.resize(original, size, interpolation=cv2.INTER_AREA)
        return self.scaled[key]

    def match(self, gray, name, scales):
        best = (0.0, None, 1.0)
        for scale in scales:
            t = self.template(name, scale)
            if min(gray.shape) < 3 or any(a < b for a, b in zip(gray.shape, t.shape)):
                continue
            _, score, _, loc = cv2.minMaxLoc(
                cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
            )
            if score > best[0]:
                best = (score, Box(*loc, t.shape[1], t.shape[0]), scale)
        return best

    @staticmethod
    def tab_token(image, ui_scale):
        """Return (number of tabs, selected tab), or an empty tuple when absent."""
        height, width = image.shape[:2]
        footer = image[int(height * 0.965) :, : int(width * 0.3)]
        gray = cv2.cvtColor(footer, cv2.COLOR_BGR2GRAY)
        _, _, stats, centers = cv2.connectedComponentsWithStats(
            np.uint8(gray > 55) * 255
        )
        dots = [
            (float(center[0]), float(center[1]), int(area))
            for (x, y, dot_width, dot_height, area), center in zip(
                stats[1:], centers[1:]
            )
            if 2 * ui_scale <= dot_width <= 12 * ui_scale
            and 2 * ui_scale <= dot_height <= 12 * ui_scale
            and 0.6 < dot_width / dot_height < 1.6
        ]
        if len(dots) < 2:
            return ()
        candidates = set()
        for seed in dots:
            row = sorted(dot for dot in dots if abs(dot[1] - seed[1]) < 5 * ui_scale)
            if len(row) < 3:
                continue
            gaps = np.diff([dot[0] for dot in row])
            areas = sorted(dot[2] for dot in row)
            if (
                max(dot[1] for dot in row) - min(dot[1] for dot in row) < 5 * ui_scale
                and min(gaps) > 0.7 * np.median(gaps)
                and max(gaps) < 1.3 * np.median(gaps)
                and areas[-1] > 1.3 * areas[-2]
            ):
                candidates.add((len(row), int(np.argmax([dot[2] for dot in row]))))
        return next(iter(candidates)) if len(candidates) == 1 else ()

    def analyze(self, image):
        start = perf_counter()
        if (
            image is None
            or image.size == 0
            or image.ndim != 3
            or image.shape[2] != 3
            or image.dtype != np.uint8
        ):
            raise ValueError("Expected a nonempty uint8 BGR image")
        h0, w0 = image.shape[:2]
        # Input is a game client capture in live mode; remove only true black letterboxing.
        active = cv2.inRange(image, (0, 0, 0), (12, 12, 12)) == 0
        rows = np.flatnonzero(active.mean(axis=1) > 0.1)
        cols = np.flatnonzero(active.mean(axis=0) > 0.1)
        x0, y0, w, h = 0, 0, w0, h0
        if len(rows) and len(cols):
            x0, y0 = int(cols[0]), int(rows[0])
            w, h = int(cols[-1] - x0 + 1), int(rows[-1] - y0 + 1)
        scale = min(1.0, self.config.analysis_height / h)
        small = cv2.resize(
            image[y0 : y0 + h, x0 : x0 + w],
            (round(w * scale), round(h * scale)),
            interpolation=cv2.INTER_AREA,
        )
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        hh, ww = gray.shape

        def original(b):
            return Box(b.x / scale + x0, b.y / scale + y0, b.w / scale, b.h / scale)

        obs = Observation(State.UNKNOWN, Box(x0, y0, w, h))
        bottom = int(hh * 0.88)
        roi = gray[bottom:, int(ww * 0.55) :]
        qscore, qb, ui_scale = self.match(roi, "q_info", np.arange(0.4, 1.31, 0.05))
        escscore, eb, _ = self.match(
            roi, "esc", [ui_scale * 0.95, ui_scale, ui_scale * 1.05]
        )
        ui = (
            qscore >= self.config.anchor_threshold
            and escscore >= self.config.esc_threshold
            and qb.x < eb.x
            and abs(qb.y - eb.y) < 8 * ui_scale
        )
        if ui:
            for name, b in [("q_info", qb), ("esc", eb)]:
                obs.anchors[name] = original(
                    Box(b.x + int(ww * 0.55), b.y + bottom, b.w, b.h)
                )
            obs.page_token = self.tab_token(small, ui_scale)
            if obs.page_token:
                score, b, _ = self.match(
                    gray[bottom:, : int(ww * 0.5)],
                    "add_friends",
                    [ui_scale * factor for factor in np.arange(0.9, 1.101, 0.025)],
                )
                obs.state = (
                    State.INDEX if score >= self.config.index_threshold else State.PAGE
                )
                if obs.state == State.INDEX:
                    obs.anchors["index"] = original(Box(b.x, b.y + bottom, b.w, b.h))
            else:
                # Footer controls alone are not enough to authorize constellation keys or clicks.
                ui = False
        if not ui:
            escscore, eb, _ = self.match(roi, "esc", np.arange(0.4, 1.31, 0.05))
            if escscore >= 0.74:
                obs.anchors["esc"] = original(
                    Box(eb.x + int(ww * 0.55), eb.y + bottom, eb.w, eb.h)
                )
            # A candle is selection evidence, never a generic ESC button alone.
            score, b, _ = self.match(gray, "candle", np.arange(0.4, 1.31, 0.1))
            if score >= self.config.candle_threshold:
                obs.state = State.SELECTED
                obs.anchors["candle"] = original(b)
            else:
                score, b, _ = self.match(gray, "const", np.arange(0.4, 1.31, 0.1))
                if score >= self.config.entry_threshold:
                    obs.state = State.ENTRY
                    obs.anchors["entry"] = original(b)
        if ui:
            left = int(ww * 0.25)
            score, b, _ = self.match(
                gray[:, left : int(ww * 0.75)],
                "candle",
                [ui_scale * 0.9, ui_scale, ui_scale * 1.1],
            )
            if score >= self.config.candle_threshold:
                obs.state = State.SELECTED
                obs.anchors["candle"] = original(Box(b.x + left, b.y, b.w, b.h))
                ui = False
        obs.timings["viewport_anchor_ms"] = (perf_counter() - start) * 1000
        detect_start = perf_counter()
        if ui:
            # Tiny bright connected components nominate centers. Template work stays local.
            mask = np.uint8(gray > self.config.core_brightness) * 255
            count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
            candidates = []
            for (x, y, bw, bh, area), (cx, cy) in zip(stats[1:], centers[1:]):
                if not (ww * 0.035 < cx < ww * 0.965 and hh * 0.08 < cy < hh * 0.87):
                    continue
                if (
                    area < 10 * ui_scale**2
                    or area > 1000 * ui_scale**2
                    or max(bw, bh) > 35 * ui_scale
                ):
                    continue
                if not 0.5 <= bw / bh <= 2.0:
                    continue
                if any(
                    np.hypot(cx - a[1], cy - a[2]) < 22 * ui_scale for a in candidates
                ):
                    continue
                r = round(24 * ui_scale)
                ix, iy = round(cx), round(cy)
                patch = gray[max(0, iy - r) : iy + r + 1, max(0, ix - r) : ix + r + 1]
                scores = {}
                for name in ("lit_friend", "unlit_friend"):
                    scores[name] = self.match(
                        patch, name, [ui_scale * v for v in (0.85, 1.0, 1.15)]
                    )
                name = max(scores, key=lambda k: scores[k][0])
                score, b, _ = scores[name]
                if score < self.config.star_threshold:
                    continue
                bx, by = b.center
                px = max(0, ix - r) + bx
                py = max(0, iy - r) + by
                if any(
                    np.hypot(px - a[1], py - a[2]) < 22 * ui_scale for a in candidates
                ):
                    continue
                # Names may be underneath or beside a favorite-constellation star.
                label = False
                for lx, ly, lw, lh in [
                    (
                        px - 75 * ui_scale,
                        py + 24 * ui_scale,
                        150 * ui_scale,
                        25 * ui_scale,
                    ),
                    (
                        px - 155 * ui_scale,
                        py - 10 * ui_scale,
                        125 * ui_scale,
                        22 * ui_scale,
                    ),
                    (
                        px + 30 * ui_scale,
                        py - 10 * ui_scale,
                        125 * ui_scale,
                        22 * ui_scale,
                    ),
                ]:
                    text = gray[
                        max(0, int(ly)) : min(hh, int(ly + lh)),
                        max(0, int(lx)) : min(ww, int(lx + lw)),
                    ]
                    if text.size:
                        _, _, ts, _ = cv2.connectedComponentsWithStats(
                            np.uint8(
                                cv2.subtract(
                                    text,
                                    cv2.GaussianBlur(
                                        text, (0, 0), max(1.0, 2 * ui_scale)
                                    ),
                                )
                                > self.config.text_contrast
                            )
                            * 255
                        )
                        letters = sum(
                            min(3, max(1, int(a[2] / (5 * ui_scale))))
                            for a in ts[1:]
                            if 3 * ui_scale <= a[3] <= 23 * ui_scale and a[4] >= 2
                        )
                        label |= letters >= 3
                if label:
                    candidates.append((score, px, py, scores))
            obs.timings["friend_detection_ms"] = (perf_counter() - detect_start) * 1000
            classify_start = perf_counter()
            for score, px, py, scores in candidates:
                lit = scores["lit_friend"][0]
                unlit = scores["unlit_friend"][0]
                light = (
                    unlit > lit
                    if abs(unlit - lit) >= self.config.classification_margin
                    else None
                )
                # Isolated bright, compact particles in a star-relative annulus.
                r = round(38 * ui_scale)
                ix, iy = round(px), round(py)
                patch = gray[iy - r : iy + r + 1, ix - r : ix + r + 1]
                particles = 0
                if patch.shape == (2 * r + 1, 2 * r + 1):
                    _, _, ps, pc = cv2.connectedComponentsWithStats(
                        np.uint8(patch > self.config.particle_brightness) * 255
                    )
                    for (ax, ay, aw, ah, area), (cx, cy) in zip(ps[1:], pc[1:]):
                        d = np.hypot(cx - r, cy - r)
                        if (
                            20 * ui_scale < d < 36 * ui_scale
                            and cy - r <= 22 * ui_scale
                            and 1 <= area <= 35 * ui_scale**2
                            and max(aw, ah) <= 9 * ui_scale
                        ):
                            particles += 1
                collectible = (
                    True if particles >= 2 else (None if particles == 1 else False)
                )
                if patch.shape != (2 * r + 1, 2 * r + 1):
                    collectible = None
                b = original(
                    Box(
                        px - 16 * ui_scale,
                        py - 16 * ui_scale,
                        32 * ui_scale,
                        32 * ui_scale,
                    )
                )
                obs.targets.append(
                    FriendTarget(
                        b,
                        score,
                        light,
                        collectible,
                        (px / ww, py / hh),
                        {
                            "lit_score": round(lit, 3),
                            "unlit_score": round(unlit, 3),
                            "particles": particles,
                        },
                    )
                )
            obs.targets.sort(key=lambda t: (t.relative[1], t.relative[0]))
            obs.timings["classification_ms"] = (perf_counter() - classify_start) * 1000
            if not obs.page_token:
                obs.warnings.append("Friend-constellation tabs not established")
            if not obs.targets and obs.state == State.PAGE:
                obs.warnings.append(
                    "No named stars established; this does not prove an empty/completed page"
                )
        obs.timings.setdefault("friend_detection_ms", 0.0)
        obs.timings.setdefault("classification_ms", 0.0)
        obs.timings["total_ms"] = (perf_counter() - start) * 1000
        if any(t.ambiguous for t in obs.targets):
            obs.warnings.append(
                "Ambiguous star state; no action planned for these targets"
            )
        return obs
