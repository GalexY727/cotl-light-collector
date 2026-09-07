# Validation and benchmark results

Measured on 2026-09-05 in the supplied Windows workspace. No live mouse/keyboard input was issued during validation.

Environment: Python 3.14.2, OpenCV 4.14.0, NumPy 2.5.2. The detector configures one OpenCV worker.

## Regression run

`python main.py --test --visualize` exited 0. `python -m unittest discover -s tests -q` passed **26 tests**. All 16 copied fixtures were verified byte-identical to their source images.

- Images checked: 16; successful checks: 16; failed: 0.
- Fully annotated images: 6; named friends found: 68/68; unexpected targets in these six images: 0.
- Explicit classification abstentions on annotated images: 3 (not counted as correct classifications).
- Ten cache images have state/invariant smoke coverage only. These are not ten accuracy passes.
- Total detections including smoke fixtures: 141.
- Full-dataset processing latency: mean **138.63 ms**, median **119.89 ms**, worst **221.10 ms**.

| Stage | Mean ms |
| --- | ---: |
| viewport_anchor_ms | 93.49 |
| friend_detection_ms | 42.82 |
| classification_ms | 1.10 |

The total includes normalization, anchors, friend detection, classification and pagination. Image decoding and visualization writes are excluded. Capture time is N/A offline; live capture is separately instrumented but was not measured against Sky. Timing varies with machine load; earlier full-dataset runs ranged roughly 94–220 ms mean.

## Legacy comparison

`python tools/benchmark.py --repeats 3` runs 18 samples per method (six original screenshots, three repetitions each). The old live module is never imported.

| Method | Mean ms | Median ms | Worst ms |
| --- | ---: | ---: | ---: |
| Historical searches with repeated decoding | 649.43 | 472.89 | 1336.67 |
| Historical searches plus repeated PNG encoding | 1205.72 | 938.50 | 2459.67 |
| New complete frame analysis | 193.25 | 184.45 | 272.84 |

Offline six original samples. Legacy = original three color-template searches, repeated decoding and x-only deduplication. PNG variant encodes identical in-memory frames in place of screenshot writes. No live capture or input latency measured. New includes anchors, names, classification and pagination.

The benchmark uses a different image mix and workload from the 16-image regression run. These measurements establish a processing improvement for these inputs, not a live completion-rate or accuracy guarantee. The old code additionally paid full-screen screenshot costs, mouse movement, fixed waits (1.3 s per page and 0.8 s or more per lighting attempt), and repeated full-page scans. Those live costs are not included above.

## Unresolved cases

- `image1.png`: Rei has an obscuring ring; collection abstains.
- `image3.png`: Kiwi and Polo collection states abstain around nearby text/ring evidence. Expected labels remain false and true respectively; the manifest explicitly permits unknown, never the opposite state.
- `cache/1.png`, `cache/2.png`, `cache/7.png`: ambiguous stars in historical marked-up frames.
- `cache/5.png`, `cache/6.png`: zero safe named-star detections despite visible marked-up friends. The runner refuses to treat these as completed pages.
- Other cache images may miss faded names; they lack target-level ground truth and must not be included in an accuracy percentage.

## Coverage limits

The tests cover ignored selection/collection/navigation, delayed responses, bounded failure and recovery, collect-before-light ordering, last-page completion without wrapping, unexpected page/dialog changes, persistent observation, original and resized/letterboxed screenshots, synthetic index/candle routing, blank/noise negatives, bad annotations, corrupt/empty datasets, input-import isolation, one-frame BGRA capture conversion, negative monitor origins, stale-window guards and corner failsafe handling.

**Live acceptance remains open.** There are no real index or selected-friend screenshots, post-light dialogs, timestamped before/after action sequences, or live ignored-click trials in the checkout. Synthetic routing and simulated state responses are not substitutes. The inherited entry key, footer index label, candle behavior, pagination endpoint, English PC layout and timing assumptions require live verification. No game throughput, capture latency, or multi-monitor DPI success claim is made.

Detailed machine-readable observations and annotated screenshots are in `debug/output/` (generated and gitignored).
