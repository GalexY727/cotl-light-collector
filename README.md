# COTL Light Collector

A Windows/OpenCV constellation collector built around observed UI transitions. `main.py` is the entry point; perception never captures the screen or sends input.

## Run

Use Python 3.10+ and a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py --test
python -m unittest discover -s tests -v
python main.py
```

The existing checkout environment is `venv`, so it can also be activated with `.\venv\Scripts\Activate.ps1`. Live mode gives you ten seconds to focus Sky. Open the friend constellation first, or stand where its interaction icon is visible. The runner cannot find a constellation stone from arbitrary gameplay. English UI and the existing `F`, `Z`, `C`, `Esc` bindings are assumed.

```powershell
python main.py --test --visualize
python main.py --test --debug
python main.py --test --dataset path/to/fixtures
python main.py --debug --focus-timeout 15
python tools/benchmark.py --repeats 3
```

Keep the actual game window in front. Losing focus or moving/resizing it between capture and input stops the run. Ctrl+C or PyAutoGUI's corner failsafe also stops it. Window identification uses the foreground title containing `Sky`; `--window-title` selects a more specific title if needed. Do not use a browser/image viewer with a matching title. The old checked-in `dist` executable has **not** been rebuilt and does not contain this implementation.

## Architecture

| Module | Responsibility |
| --- | --- |
| `collector/config.py` | Thresholds, polling, retry/page/action budgets |
| `collector/models.py` | Viewport, bounding boxes, friend state/evidence, observations |
| `collector/vision.py` | Pure BGR image to UI state, targets, page marker and stage timings |
| `collector/runtime.py` | DPI-aware Windows client geometry, one persistent MSS capture session, guarded input |
| `collector/controller.py` | Indexing, page processing, action verification and bounded recovery |
| `collector/diagnostics.py` | Production-detector regression harness, validation and overlays |
| `tests/` | Fake-clock interaction tests, real image regressions, scale/letterbox and no-input tests |
| `tools/benchmark.py` | Reproducible offline comparison with the old three-search hot path |

The live flow is: recognize the friend constellation from its bottom-left tab strip -> send enough non-wrapping `Z` inputs to force its verified zero index -> move right once with `C` -> build the complete page action plan -> collect before lighting -> verify each action -> verify page completion -> advance with `C`. The selected pagination dot is identified by its larger connected-component area, not brightness (online dots can be brighter). Completion requires processing the page whose final pagination dot is selected. It does not assume the last page wraps around.

A click is a request, not success. Selection polls for a stable candle prompt. Collection requires reacquiring the same star on the same page with its particles absent. Lighting requires the candle prompt to change, returning to the same page, and reacquiring that star with the lit ray pattern. Every retry starts from a fresh observation. Targets disappearing, a changed page, or an ambiguous classification do not count as success. The pointer is moved to the detected footer control after a click to avoid hovering over a star.

Polling is every 60 ms plus analysis time, with a 2.5-second timeout and at least 240 ms of persistent evidence. After a verified friend-star click, the runner waits **1.1 seconds from that click** while continually confirming the candle dialog remains open, then presses `F` to light. There are at most three attempts per interaction, 40 pages, 100 actions per page, and two recovery passes. Recovery recognizes the current UI, closes a recognized friend dialog or enters through the constellation icon, and re-indexes. It re-scans already processed pages rather than replaying old coordinates. If recovery cannot establish a known state, it stops with the failed transition. An empty detection result cannot establish completion, and a previously seen friend cannot silently disappear from the page's target record.

## Vision and coordinates

Current live queue behavior: each page is scanned and each actionable friend is queued once, including friends marked for both collection and lighting. A visit clicks the friend, waits 2.1 seconds, checks for the candle prompt, presses F, waits 0.3 seconds, presses Esc, and waits 0.2 seconds before checking the returned page. Persistent particles do not cause another visit. If a click leaves the constellation page open (collection-only or ignored input), it is logged and the queue advances without sending F or Esc into the page. Ambiguous friends are skipped. Queue exhaustion means all queued visits were attempted, not that every candle was visually verified. Z is used only for startup indexing; subsequent navigation uses C with a 1.3-second transition delay.

MSS captures only the foreground game's client area into memory. Window origin is applied only when issuing input. The detector removes dark letterboxing and normalizes large images to at most 720 pixels tall. It measures the UI scale from the `Q Info` keycap and cross-checks the adjacent `Esc` keycap. No screen-width branch or coordinate preset exists.

`media/ui` contains seven canonical crops copied from the old assets. Their resized versions are cached. Anchor searches use relative footer/central regions; friend geometry, text search regions, clustering distance and particle radii are derived from the measured icon scale. Reasonable English PC UI placement is still an assumption, not arbitrary-layout recognition. The viewport is the game client (or a client screenshot), not a general desktop window detector.

Bright connected components nominate candidate stars. Local multi-scale comparisons distinguish four-ray unlit cores from lit cores with diagonal rays. Nearby text contrast supplies additional friend evidence, including side labels in favorite constellations. Two-dimensional distance clustering merges candidates for the same star; stars sharing an x coordinate remain separate. Compact bright components in an annulus provide collection evidence. Two or more particles mean collectible; one means uncertain. Core-score ties and clipped particle regions also produce uncertainty. Uncertain targets receive no actions. Shape scores are correlation scores, **not calibrated probabilities**.

Important thresholds are in `Config`: anchor 0.78, ESC 0.70, index 0.85, candle 0.86, entry 0.88, star 0.91, class margin 0.025. Brightness thresholds use uint8 grayscale. Geometric constants describe proportions or canonical crop dimensions and are multiplied by measured UI scale. Tune against annotations; do not lower everything to one global threshold. OpenCV uses one worker because this workload consists mostly of small ROIs.

## Dataset and validation

For a full live diagnostic run, use `python -u main.py --record`. This adds no trial limit. Temporary evidence goes to `cache/live/`: numbered screenshots before clicks/key-downs and at every observation, `events.jsonl` with inputs and detector results, and `run.log`. A failure also attempts a fresh screenshot while respecting the focus/geometry guard. Recording adds screenshot/disk overhead; key-up is not delayed by an extra screenshot. Each run overwrites the event index, log, and matching numbered screenshots; leftover frames from longer older runs are ignored by replay.

Use `python main.py --replay` to analyze the recorded frames offline without initializing the game adapter or sending input. It writes `cache/live/replay.jsonl`, including changes from the recorded detections. This replays perception, not game responses, and does not by itself prove that inputs succeeded. After a failure, ask to debug the latest `cache/live` run; the local files contain the evidence, so there is no need to paste the entire console. Preserve the folder before starting another recorded run if needed.

There was **no `debug` directory in the supplied checkout**. `debug/image1.png` through `image6.png` and `debug/cache/` are byte-for-byte copies of existing source images. Original images and assets remain unchanged.

`python main.py --test` analyzes every supported image recursively, excluding `output/`, using exactly the production detector. It never imports the live adapter, AHK or MSS. Missing datasets, corrupt images, invalid detections and annotation mismatches return a nonzero exit code. Unannotated images are explicitly marked `SMOKE`; passing smoke coverage does not claim accurate detection. Add fixtures and reviewed labels as described in `debug/README.md`.

The six original samples have 68 manually identified named friends with lighting and collection labels. Three collection labels explicitly permit **abstention**, which is reported rather than counted as a correct state prediction. The historical cache images have state-only coverage: several contain diagnostic circles drawn into the pixels, and some names are faded. They are not a reliable basis for assigning new action ground truth. In particular, no targets are established in marked-up `cache/5.png` and `cache/6.png`.

Optional overlays and machine-readable per-target evidence/timings go to `debug/output/`; originals are never overwritten. Test output reports viewport, counts, ambiguous cases, average/median/worst processing time, and stage means. Live debug logging includes capture time and transition decisions. Normal execution writes no frame PNGs.

## Measured status and limits

See `BENCHMARKS.md` for measured results and scope. Offline regression and simulated transitions are useful evidence, but **live end-to-end completion has not been validated**. The repository supplies no actual index, selected-friend, post-light dialog, or before/after click sequences. Synthetic anchor-routing and simulated transition tests do not replace that evidence. Index detection currently expects the historical `Add Friends` label in the footer, with `Q Info`/`Esc` visible and the first pagination dot selected. This layout must be checked in the actual game.

Other limits: OCR is not used; very faint/occluded names can be missed. Dense or unfamiliar layouts may stop on ambiguity. A short-lived absence of particles can resemble collection, so persistent observations reduce but cannot eliminate that risk without live sequences. Unknown selected dialogs without a recognizable candle/back control stop. Empty pages stop conservatively. Multi-monitor DPI behavior and real ignored-click timing remain untested on the game. Scale tests cover 960x540 through 2880x1620 with letterboxing; supplied screenshots cover 1920x1080 and 2880x1800. These tests do not establish support for every aspect ratio, localization, HDR mode or UI scale.

The incomplete experimental `cv.py`, `compare.py`, `test.py`, `ss.py` and `save_histogram.py` were removed. Their useful image/flare ideas are represented in the detector and offline benchmark. Live input uses AutoHotkey v1, preserving the input mechanism used by the original working collector.
