"""Pure vision for the October 2026 UI. Coordinates use a 2048x1152 viewport.

The list is deliberately calibrated separately from the old 16:10 constellation
templates. Unknown/partial UI frames never authorize an interaction.
"""
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent / 'media' / 'baseline'
SIZE = (2048, 1152)
XS = (574, 925, 1278)
YS = tuple(range(384, 769, 64))


class UIState(str, Enum):
    UNKNOWN = 'unknown'
    WORLD = 'world'
    CONSTELLATION = 'constellation'
    ADD_FRIENDS = 'add_friends'
    LIST = 'list'
    FRIEND = 'friend'
    LIGHT_READY = 'light_ready'


@dataclass(frozen=True)
class Friend:
    column: int
    row: int
    center: tuple[int, int]
    needs_light: bool
    needs_collect: bool
    score: float

    @property
    def slot(self):
        return self.column, self.row


@dataclass(frozen=True)
class Observation:
    state: UIState
    friends: tuple[Friend, ...] = ()
    page: str = ''


@lru_cache(maxsize=32)
def template(name):
    result = cv2.imread(str(ASSETS / (name + '.png')), cv2.IMREAD_GRAYSCALE)
    if result is None:
        raise FileNotFoundError(f'Missing baseline template: {name}')
    return result


def cue(gray, name, region, threshold=.85):
    x, y, w, h = region
    scores = cv2.matchTemplate(gray[y:y+h, x:x+w], template(name), cv2.TM_CCOEFF_NORMED)
    return float(scores.max()) >= threshold


def list_friends(gray, original_size):
    """Validate each list slot's core, then measure its satellites independently.

    Ring + satellites means BOTH. Bright core + satellites means collect only.
    A single background star or a white dot in a name is not a collection cue.
    """
    width, height = original_size
    yy, xx = np.mgrid[-28:29, -28:29]
    radius = np.hypot(xx, yy)
    annulus = (radius > 14) & (radius < 28)
    friends = []
    for column, x in enumerate(XS):
        for row, y in enumerate(YS):
            core = gray[y-12:y+13, x-12:x+13]
            scores = [float(cv2.matchTemplate(core, template(name), cv2.TM_CCOEFF_NORMED)[0, 0])
                      for name in ('unlit_core', 'lit_core')]
            if max(scores) < .82 or abs(scores[0] - scores[1]) < .12:
                if int(core.max()) > 85:
                    return None  # visible but ambiguous friend: do not silently skip it
                continue
            patch = gray[y-28:y+29, x-28:x+29]
            _, _, stats, centers = cv2.connectedComponentsWithStats(
                ((patch > 100) & annulus).astype(np.uint8))
            angles = [np.arctan2(cy-28, cx-28)
                      for stat, (cx, cy) in zip(stats[1:], centers[1:])
                      if 2 <= stat[4] <= 40 and stat[2] <= 9 and stat[3] <= 9]
            collect = any(abs(np.arctan2(np.sin(a-b), np.cos(a-b))) > np.pi/2
                          for a in angles for b in angles)
            friends.append(Friend(column, row,
                                  (round(x*width/SIZE[0]), round(y*height/SIZE[1])),
                                  scores[0] > scores[1], collect, max(scores)))
    return tuple(friends)


def page_signature(gray):
    # Names identify a page independently of lighting, orbit animation, cursor,
    # and notification dots. Quantization reduces JPEG/video noise.
    strips = [gray[374:785, x+30:x+180] for x in XS]
    binary = np.hstack([cv2.resize(s, (75, 205)) > 100 for s in strips])
    return np.packbits(binary).tobytes().hex()


def same_page(a, b):
    if not a or not b or len(a) != len(b):
        return False
    return (int(a, 16) ^ int(b, 16)).bit_count() / (len(a)*4) < .025


def observe(frame):
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError('Expected a BGR frame')
    height, width = frame.shape[:2]
    # Reflow/letterboxing is uncalibrated: fail closed instead of stretching it.
    if abs(width/height - 16/9) > .02:
        return Observation(UIState.UNKNOWN)
    gray = cv2.cvtColor(cv2.resize(frame, SIZE), cv2.COLOR_BGR2GRAY)
    if (cue(gray, 'panel_gift', (1375, 205, 180, 90)) and
            cue(gray, 'panel_manage', (1380, 705, 220, 85))):
        ready = cue(gray, 'light_prompt', (250, 120, 1050, 700), .82)
        return Observation(UIState.LIGHT_READY if ready else UIState.FRIEND)
    back = cue(gray, 'back', (1870, 1070, 178, 65), .8)
    if back and cue(gray, 'list_heading', (5, 1050, 250, 70)) and cue(
            gray, 'list_toggle', (1690, 5, 250, 80)):
        friends = list_friends(gray, (width, height))
        if friends:
            return Observation(UIState.LIST, friends, page_signature(gray))
    if back and cue(gray, 'constellation_toggle', (1740, 5, 250, 80), .8):
        return Observation(UIState.CONSTELLATION)
    if back and cue(gray, 'add_heading', (5, 1050, 260, 80), .8):
        return Observation(UIState.ADD_FRIENDS)
    if cue(gray, 'world_prompt', (300, 500, 1000, 600), .85):
        return Observation(UIState.WORLD)
    return Observation(UIState.UNKNOWN)
