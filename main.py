"""Offline, scale-aware Sky light collector. Run with --debug for raw overlays."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import time

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / 'media' / 'zenbook'
CACHE_DIR = BASE_DIR / 'cache'
REFERENCE_SIZE = (2880, 1800)
SCALE_SWEEP = tuple(np.linspace(0.90, 1.10, 9))
CONFIDENCE = {
    'esc': 0.7, 'candle': 0.6, 'const': 0.6, 'add_friends': 0.9,
    'page_bubble': 0.9, 'page_bubble_online': 0.9,
    'lit_friend': 0.8, 'unlit_friend': 0.9, 'flare': 0.8, 'q_info': 0.9,
}
# These are shape/text cues. Friend stars, flares and blue/gray page bubbles
# retain BGR color; grayscale would discard a useful distinguishing signal.
GRAYSCALE = {'esc', 'candle', 'const', 'add_friends', 'q_info'}
FRIEND_TYPES = {'lit_friend', 'unlit_friend'}
IOU_THRESHOLD = 0.3
FRIEND_GLOW_RADIUS = 1.25  # icon heights: includes the peak below the icon
FLARE_DISTANCE = 70.0  # pixels at the supplied 2880x1800 template reference
DEBUG = False
DEBUG_DIR = CACHE_DIR / 'debug'
DEBUG_MARGIN = 0.15

# One reference layout: the original Zenbook coordinates at 2880x1800.
# Regions are (left, top, width, height), never right/bottom coordinates.
REGIONS = {
    'friends': (250, 200, 2300, 1360),
    'candle': (840, 0, 1087, 1800),
    'esc': (2610, 1700, 200, 100),
}
page_transition_time = 1.3
total_pages = -1
current_page = 0
friend_count = 0
light_collected = 0
ahk = None
_mouse = None
_capture = None
_screen = None
_frame_id = 0
_debug_id = 0


@dataclass(frozen=True)
class Match:
    left: int
    top: int
    width: int
    height: int
    score: float
    template: str = ''

    @property
    def box(self):
        return (self.left, self.top, self.width, self.height)

    @property
    def center(self):
        return (self.left + self.width // 2, self.top + self.height // 2)


def read_image(filename):
    image = cv2.imread(str(filename), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f'Cannot read image: {filename}')
    return image


def capture_and_cache_screen(image=None):
    """Start a check cycle. All locate calls reuse this BGR frame until replaced.

    Supply a full-screen BGR array or filename for offline use. No screenshot,
    AHK process, or input action is started when working with supplied images.
    """
    global _screen, _capture, _frame_id
    if image is None:
        if _capture is None:
            import mss
            _capture = mss.mss()
        # Primary monitor, in physical pixels (MSS initializes DPI awareness).
        monitor = next(m for m in _capture.monitors[1:]
                       if m['left'] == 0 and m['top'] == 0)
        image = np.asarray(_capture.grab(monitor))[:, :, :3]
    elif isinstance(image, (str, Path)):
        image = read_image(image)
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError('Expected a full-screen uint8 BGR image')
    _screen = np.ascontiguousarray(image).copy()
    _frame_id += 1
    return _screen


def cached_screen():
    return capture_and_cache_screen() if _screen is None else _screen


def resolution_scale():
    height, width = cached_screen().shape[:2]
    # Templates are captured at 2880x1800. Scale each axis using actual capture
    # dimensions, not Windows logical/DPI dimensions. At 1440x900 both = .5.
    # Different aspect ratios use separate x/y factors; letterboxing or a UI
    # layout that reflows independently requires viewport-specific calibration.
    return width / REFERENCE_SIZE[0], height / REFERENCE_SIZE[1]


def scaled_region(name):
    sx, sy = resolution_scale()
    x, y, w, h = REGIONS[name]
    return (round(x * sx), round(y * sy), round(w * sx), round(h * sy))


def scaled_point(x, y):
    sx, sy = resolution_scale()
    return round(x * sx), round(y * sy)


def template_path(needle):
    filename = Path(needle)
    if filename.is_file():
        return filename.resolve()
    if filename.suffix == '':
        filename = filename.with_suffix('.png')
    return TEMPLATE_DIR / filename


@lru_cache(maxsize=64)
def load_template(filename):
    return read_image(filename)


@lru_cache(maxsize=256)
def resized_template(filename, width, height, gray):
    original = load_template(filename)
    interpolation = cv2.INTER_AREA if width < original.shape[1] else cv2.INTER_CUBIC
    resized = cv2.resize(original, (width, height), interpolation=interpolation)
    return cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if gray else resized


def overlaps(a, b):
    x = max(0, min(a.left + a.width, b.left + b.width) - max(a.left, b.left))
    y = max(0, min(a.top + a.height, b.top + b.height) - max(a.top, b.top))
    intersection = x * y
    iou = intersection / (a.width * a.height + b.width * b.height - intersection)
    if iou > IOU_THRESHOLD:
        return True
    if a.template in FRIEND_TYPES and b.template in FRIEND_TYPES:
        # Joint 2D ellipse, including one full icon height vertically. Unlike
        # x-only dedup, this retains friends sharing x at different rows.
        dx = (a.center[0] - b.center[0]) / max(a.width, b.width)
        dy = (a.center[1] - b.center[1]) / (FRIEND_GLOW_RADIUS * max(a.height, b.height))
        return dx * dx + dy * dy <= 1.0
    return False


def non_max_suppression(matches):
    kept = []
    # All scales compete; the highest confidence box wins, not the first scale.
    for candidate in sorted(matches, key=lambda m: m.score, reverse=True):
        if not any(overlaps(candidate, winner) for winner in kept):
            kept.append(candidate)
    return kept


def save_raw_overlay(matches, name, threshold):
    """Every pre-NMS threshold hit, plus lower-scoring diagnostic hits.

    CSV preserves every score/box even where dense overlay labels overlap.
    """
    global _debug_id
    _debug_id += 1
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stem = DEBUG_DIR / f'{_frame_id:06d}_{_debug_id:06d}_{name}_raw'
    overlay = cached_screen().copy()
    with stem.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['left', 'top', 'width', 'height', 'score', 'passes_threshold'])
        for match in sorted(matches, key=lambda m: m.score):
            accepted = match.score >= threshold
            writer.writerow([*match.box, match.score, accepted])
            color = (0, 255, 0) if accepted else (0, 128, 255)
            x, y, w, h = match.box
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 1)
            cv2.putText(overlay, f'{match.score:.3f}', (x, max(10, y - 2)),
                        cv2.FONT_HERSHEY_SIMPLEX, .3, color, 1)
    if not cv2.imwrite(str(stem.with_suffix('.png')), overlay):
        raise OSError(f'Cannot write overlay: {stem}')


def locate_scaled(needle_path, region=None, confidence=0.8, scales=None):
    """Return score-ordered NMS Match objects in full-screen coordinates.

    region is in current-screen pixels. scales are positive multipliers around
    the computed resolution scale (default .90..1.10). An empty result is [].
    Call capture_and_cache_screen once before each logical check cycle.
    """
    if not 0 <= confidence <= 1:
        raise ValueError('confidence must be between 0 and 1')
    screen = cached_screen()
    sh, sw = screen.shape[:2]
    x, y, w, h = (0, 0, sw, sh) if region is None else tuple(map(int, region))
    right, bottom = min(sw, x + w), min(sh, y + h)
    x, y = max(0, x), max(0, y)
    filename = str(template_path(needle_path))
    needle = load_template(filename)
    name = Path(filename).stem
    gray = name in GRAYSCALE
    raw = []
    if right > x and bottom > y:
        haystack = screen[y:bottom, x:right]
        if gray:
            haystack = cv2.cvtColor(haystack, cv2.COLOR_BGR2GRAY)
        sx, sy = resolution_scale()
        sizes = set()
        for multiplier in SCALE_SWEEP if scales is None else scales:
            if not np.isfinite(multiplier) or multiplier <= 0:
                raise ValueError('scales must contain finite positive multipliers')
            tw = max(1, round(needle.shape[1] * sx * multiplier))
            th = max(1, round(needle.shape[0] * sy * multiplier))
            if (tw, th) in sizes or tw > right - x or th > bottom - y:
                continue
            sizes.add((tw, th))
            template = resized_template(filename, tw, th, gray)
            # A constant template makes CCOEFF_NORMED degenerate (all ones).
            if np.var(template.astype(np.float32), axis=(0, 1)).sum() < 1e-6:
                continue
            scores = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
            floor = max(0, confidence - DEBUG_MARGIN) if DEBUG else confidence
            ys, xs = np.where(np.isfinite(scores) & (scores >= floor))
            raw.extend(Match(int(px + x), int(py + y), tw, th,
                             float(scores[py, px]), name) for py, px in zip(ys, xs))
    if DEBUG:
        save_raw_overlay(raw, name, confidence)
    return non_max_suppression([m for m in raw if m.score >= confidence])


def locate(name, region=None):
    return locate_scaled(name, region=region, confidence=CONFIDENCE[name])


def mouse():
    global _mouse
    if _mouse is None:
        # Initialize MSS first so capture and mouse coordinates agree under DPI.
        if _capture is None:
            capture_and_cache_screen()
        import pyautogui
        _mouse = pyautogui
    return _mouse


def send_key(key):
    global ahk
    if ahk is None:
        from ahk import AHK
        ahk = AHK()
    ahk.key_down(key)
    try:
        time.sleep(.1)
    finally:
        ahk.key_up(key)


def press_key(key):
    capture_and_cache_screen()
    if not locate('esc', scaled_region('esc')):
        print('Esc not found')
        return 0
    send_key(key)
    return 1


def doubleClick(x, y):
    global ahk
    if ahk is None:
        from ahk import AHK
        ahk = AHK()
    ahk.click(x, y, coord_mode='Screen')
    ahk.click(x, y, coord_mode='Screen')


def attempt_reentry():
    capture_and_cache_screen()
    if not locate('const'):
        return 0
    send_key('f')
    return 1


def enter_ui():
    if attempt_reentry():
        return
    for _ in range(7):
        mouse().scroll(25)
        height, width = cached_screen().shape[:2]
        mouse().moveTo(width // 2, height - 1)
    attempts = 50
    while attempts > 0:
        if attempt_reentry():
            break
        attempts -= 1
        mouse().moveTo(*scaled_point(1591, 932))
    time.sleep(3)


def index_to_start():
    while True:
        capture_and_cache_screen()
        if locate('add_friends'):
            return
        send_key('z')


def get_total_pages():
    capture_and_cache_screen()
    headings = locate('add_friends')
    if not headings:
        raise RuntimeError('Add Friends heading missing after indexing')
    heading = headings[0]
    height, width = cached_screen().shape[:2]
    top = heading.top + heading.height
    region = (heading.left, top, int(width * .12), height - top)
    online = locate('page_bubble_online', region)
    offline = locate('page_bubble', region)
    return len(non_max_suppression(online + offline))


def find_all(image, haystackPath=None):
    if haystackPath is None:
        mouse().moveTo(*scaled_point(500, 0))
    capture_and_cache_screen(haystackPath)
    return [m.box for m in locate(image, scaled_region('friends'))]


def cv_find_all(needlePath, haystackPath=None, confidence=None, *, use_cached=False):
    if not use_cached:
        if haystackPath is None:
            mouse().moveTo(*scaled_point(500, 0))
        capture_and_cache_screen(haystackPath)
    name = Path(needlePath).stem
    threshold = CONFIDENCE.get(name, .8) if confidence is None else confidence
    return [m.center for m in locate_scaled(needlePath, scaled_region('friends'), threshold)]


def find_flare_stars(testImagePath=None):
    if testImagePath is None:
        mouse().moveTo(*scaled_point(500, 0))
    capture_and_cache_screen(testImagePath)
    region = scaled_region('friends')
    stars = non_max_suppression(locate('lit_friend', region) + locate('unlit_friend', region))
    flares = cv_find_all('flare', use_cached=True)
    sx, sy = resolution_scale()
    # Measure in reference pixels: equivalent to a 70*s radius for equal axes.
    return [star.center for star in stars
            if sum(np.hypot((star.center[0] - fx) / sx,
                            (star.center[1] - fy) / sy) < FLARE_DISTANCE
                   for fx, fy in flares) > 1]


def wait_for_candle(duration):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining < .24:
            time.sleep(max(0, remaining))
        capture_and_cache_screen()
        if locate('candle', scaled_region('candle')):
            time.sleep(.05)
            return 1
    return 0


def light_friend(x, y):
    global friend_count
    doubleClick(x, y)
    time.sleep(.3)
    capture_and_cache_screen()
    skip = locate('candle', scaled_region('candle'))
    if not skip and not locate('esc'):
        enter_ui()
        return
    if not skip:
        wait_for_candle(.9)
    press_key('f')
    time.sleep(.2)
    press_key('esc')
    time.sleep(.3)
    friend_count += 1


def loop():
    global current_page, light_collected
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    while current_page <= total_pages:
        testImagePath = CACHE_DIR / f'{current_page}.png'
        testImage = capture_and_cache_screen().copy()
        for _ in range(2):
            for star in find_flare_stars():
                mouse().click(star)
                light_collected += 1
                cv2.circle(testImage, star, 40, (255, 0, 255), 5)
        while True:
            friends = find_all('unlit_friend')
            for x, y, w, h in friends:
                center = (x + w // 2, y + h // 2)
                cv2.circle(testImage, center, 12, (0, 255, 0), 2)
                light_friend(*center)
            if not friends:
                break
        press_key('c')
        if not cv2.imwrite(str(testImagePath), testImage):
            raise OSError(f'Cannot save page screenshot: {testImagePath}')
        time.sleep(page_transition_time)
        mouse().moveTo(*scaled_point(501, 0))
        current_page += 1


def main():
    global DEBUG, DEBUG_DIR, total_pages
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug', action='store_true', help='Save pre-NMS PNG overlays and CSV scores')
    parser.add_argument('--debug-dir', type=Path, default=DEBUG_DIR)
    args = parser.parse_args()
    DEBUG, DEBUG_DIR = args.debug, args.debug_dir
    print('Starting!!')
    start_time = time.monotonic()
    time.sleep(1)
    try:
        capture_and_cache_screen()
        if not locate('esc'):
            enter_ui()
        index_to_start()
        total_pages = get_total_pages()
        print(f'Total pages: {total_pages}')
        press_key('c')
        time.sleep(page_transition_time)
        loop()
        elapsed_time = time.monotonic() - start_time
        print(f'Lit {friend_count} friends, and collected {light_collected} light in {int(elapsed_time)} seconds')
    finally:
        if _capture is not None:
            _capture.close()


if __name__ == '__main__':
    main()
