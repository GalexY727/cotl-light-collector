# COTL Light Collector

Automates lighting friends and collecting their light in **Sky: Children of the
Light**, using local OpenCV detection. No network calls or external models.

## Setup

Use Windows, 64-bit Python, and an installed AutoHotkey runtime. The pinned
requirements were tested with Python 3.14. The EXE in `dist/` is an older build;
run from source for the current detector and pause controls.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

Open the game on the primary monitor in full-screen **16:9**, without borders or
letterboxing. Start from the friend constellation or list view; the script
switches to list view for scanning. There are three seconds to focus the game.

```powershell
.venv\Scripts\python main.py
.venv\Scripts\python main.py --scan-only
.venv\Scripts\python main.py --scan-only --report cache/my-scan.json
```

`--scan-only` navigates through every friend page until wraparound and reports
which friends need lighting, collecting, or both. It never clicks friends or
executes their queued actions. It still sends UI entry/view/page navigation
keys. The JSON report defaults to `cache/scan-report.json` and includes totals,
per-page detections, coordinates, planned actions, and planning times. Reports
are saved after each page, including partial results if interrupted. Pausing
and resuming rescans safely and does not duplicate pages in the report.

- **Alt-tab**, **-**, keypad minus, or **Backspace** pauses and releases held keys.
- Focus the game and press **=** to resume with a fresh scan.
- **Ctrl+C** exits and releases held keys.
- `--game-title TEXT` selects a unique game window title (default: `Sky`).
- `--debug` saves page screenshots and JSON queues in `cache/debug`;
  `--debug-dir PATH` changes that location.

## How it works

Explicit UI states gate inputs. Each page produces its complete action queue
within a one-second budget, including capture; exceeding it stops the run.
Ring cores need lighting; orbiting satellites indicate collection independently.
Friends needing both are collected first, then lit. Fresh captures verify each
action before it is counted. Unknown UI and failed transitions stop input.

Lighting uses fixed 0.9-second opening and 0.2-second animation timers; visual
confirmation can advance either step early. Timer actions require a recognized
friend panel. The foreground watchdog polls every 20 ms and checks before each
input; this is not a hard real-time guarantee.

The current baseline is `media/new/`: 165 labeled friends across eight pages,
including three needing both actions. Offline detection plus queue construction
measured below one second; live capture/timing and native hotkeys still need
interactive verification. Other aspect ratios or reflowed layouts require
calibration. Use at your own risk.

## Verify offline

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python tools/replay_baseline.py
```

Tests cover labeled friends at three resolutions, video checkpoints, action
ordering, scan-only navigation, timer races, pause/focus handling, and key
release. Replay writes annotated images and timing results to
`cache/baseline-replay/`; saved measurements are in `tests/baseline_results.json`.
The legacy template matcher and its benchmark remain available for offline
comparison in `main.py` and `tests/benchmark_detection.py`.
