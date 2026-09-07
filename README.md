# COTL Light Collector

The COTL Light Collector is a Python-based automation tool designed to assist players in the game "Sky: Children of the Light" by automating the process of collecting lights. It uses local OpenCV template matching, MSS screenshots, AHK for every keypress and friend double-click, and PyAutoGUI for the existing mouse movement, scrolling, and light clicks. The automation makes no network calls.

https://github.com/GalexY727/cotl-light-collector/assets/65139378/c70b7156-dc7f-4550-b522-fe94e5b0c144

## Features

- **Automated Light Collection**: Automatically locates and collects lights within the game, reducing the manual effort required.
- **Friend Interaction**: Supports light collection from friends by simulating the necessary keyboard and mouse interactions.

## Installation

There are two options to run this program:
### 1: Running the executable:
Launch the .exe inside of `./dist/`, and you should be good to go!
### 2: Running from source (Windows, 64-bit Python 3.11+ and AutoHotkey installed):
```
git clone <repository>
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Usage

Open the game "Sky: Children of the Light" and navigate to the area where you wish to collect lights.
Run main.py from your terminal or command prompt:
The script will take over the mouse and keyboard to start collecting lights. Ensure the game window remains active and in the foreground.

## Disclaimer

This tool is intended for educational purposes and to automate repetitive tasks within the game. Please use responsibly and at your own risk. The developers of this tool are not responsible for any potential consequences of using this automation script.

## Detection and resolution

All 15 images in `media/zenbook/**` were inspected. The corrected reference is
**2880x1800**, including the original Zenbook search regions. Each captured frame
sets `sx = width/2880` and `sy = height/1800`. Templates sweep nine sizes from
90% to 110% of that computed size; score-ordered NMS selects the strongest box
across all scales. Regions and the 70-reference-pixel flare grouping distance
use the same coordinate transform. At other aspect ratios x/y scale separately;
this assumes the game stretches the reference layout. Letterboxing, windowed
viewports, or independently reflowed UI require a calibrated viewport/layout;
resolution scaling alone cannot guarantee detection under those conditions.

`capture_and_cache_screen()` starts a check cycle. `locate_scaled(needle_path,
region=None, confidence=0.8, scales=None)` reuses that frame and returns a list
of `Match` objects with `.box`, `.center`, and `.score` (empty on no match).
Regions use current-screen pixels; custom `scales` are multipliers around the
computed size, not absolute scales. Offline callers can pass a full-screen BGR
array or filename to the capture helper. Flare detection shares one frame for
all three templates, page counting shares one frame, and candle/escape checks
share one frame. Actions are followed by fresh check cycles. Missing/corrupt
assets raise errors instead of silently being reported as no match.

Friend stars, flares, and blue/gray page bubbles retain color. Text/menu cues
(`esc`, `candle`, `const`, `add_friends`, `q_info`) use grayscale. The five
`lit_friends` samples show satellites at different positions around the star;
the matcher uses the central friend templates and detects satellites separately.
NMS uses box IoU and a joint 2D friend suppression ellipse reaching 1.25 icon
heights vertically to cover glow peaks. It retains vertically separated friends,
but exceptionally close real icons can still be merged. Thresholds are collected
in `CONFIDENCE`; glow radius and flare grouping distance are named constants.
The original page traversal, two light passes, click sequences, sleeps and
friend/light counters remain. All key down/up operations go through AHK.

Graphics quality is independent of resolution: bloom, lighting/color grading,
anti-aliasing and detail changes can still defeat normalized correlation,
especially on the small friend and flare templates. Color correlation helps
retain channel information but does not guarantee lit/unlit classification.
If debug captures show quality-dependent failures, a documented next option is
an edge-based match for structural candidates followed by a color check, or
additional templates captured at the target graphics quality. Edge matching
alone loses the lit/unlit color cue; feature matching such as ORB is better
suited to larger textured UI and is often unreliable on tiny smooth flares.
These fallbacks are not enabled automatically. No external model or API is used.

## Debugging and offline verification

Run `.venv\Scripts\python main.py --debug` to save PNG overlays and CSVs in
`cache/debug` (override with `--debug-dir PATH`). Green boxes pass the threshold;
orange boxes fall within 0.15 below it for diagnosis. Every raw threshold hit
from every scale is recorded **before NMS**, with its score printed beside it.
Dense labels can overlap; CSVs retain every box and exact score. Debug output
can be large and slow and is disabled by default.

Run `.venv\Scripts\python -m unittest discover -s tests -v` for synthetic,
offline regression tests, and `.venv\Scripts\python -m pip check` for dependency
compatibility. Tests never send input to the game. The 11 tests pass with the pinned dependencies.
Three repository screenshots were also processed without live input; the
2880x1800 sample returned 13 lit friends, consistent with visual inspection.
See the OpenCV 5 comparison below for measured matching times. Live-game
accuracy and timing remain to be verified.

## Dependencies

`requirements.txt` pins a compatible set tested in an isolated Python 3.14
environment. The conflicting MSS pins were replaced with one version and MSS
now captures directly into memory. The unused `keyboard` dependency/import was
removed. AHK remains the only keypress backend; install AutoHotkey separately
before running live automation. Pillow and PyAutoGUI remain for existing mouse
and screenshot utility scripts. OpenCV is upgraded to 5.0.0.93 and retains GUI support for `cv.py`.
AHK remains unchanged as the only keyboard backend.

Release references: [AHK](https://pypi.org/project/ahk/1.8.4/),
[MSS](https://pypi.org/project/mss/10.2.0/),
[OpenCV](https://pypi.org/project/opencv-python/5.0.0.93/),
[NumPy](https://pypi.org/project/numpy/2.4.4/), and
[Pillow](https://pypi.org/project/Pillow/12.3.0/).

## OpenCV 5 performance comparison

The environment and requirements now use `opencv-python==5.0.0.93`.
Three sequential runs per saved screenshot produced these median matching
and NMS times (seconds; screenshot/file loading excluded):

| Screenshot | OpenCV 4.13 / NumPy 2.4.4 | OpenCV 5 / NumPy 2.4.4 | OpenCV 5 / NumPy 2.5.3 |
| --- | ---: | ---: | ---: |
| image1.png | 13.081 | 9.035 | 9.404 |
| image5.png | 4.708 | 3.283 | 2.937 |
| cache/0.png | 6.103 | 3.004 | 3.167 |

OpenCV 5 was about 30-51% faster in these local runs. Every detected box and
confidence score was identical across all three dependency combinations.
These are small sequential benchmarks, not a controlled hardware study or a
guarantee for live capture. The 11 offline tests also pass with OpenCV 5.

NumPy 2.5.3 gave mixed timing changes and no overall improvement, so the
NumPy 2.4.4 pin remains. Other runtime packages are already current in the
package-index check; upgrading pip would not speed up image matching. All
keypresses still use AHK. The standard OpenCV wheel is CPU-only; this upgrade
does not enable GPU matching.

Reproduce using `.venv\Scripts\python tests/benchmark_detection.py --output
.venv/benchmark.json` (enter this as one command). Results include individual
run timings, boxes and scores. `tests/benchmark_results.json` records the
comparison summary; `--repeats N` changes the number of runs.
