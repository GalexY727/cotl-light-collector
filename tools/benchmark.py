"""Offline comparison with the historical three-search hot path. Never imports old live code."""

import argparse
import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector.vision import Detector


def legacy(image, path, roundtrip):
    pack = ROOT / "media" / ("zenbook" if image.shape[1] > 1920 else "desktop")
    region = (250, 200, 2550, 1560) if image.shape[1] > 1920 else (190, 120, 1700, 1068)
    x, y, right, bottom = region
    for name in ("lit_friend", "unlit_friend", "flare"):
        if roundtrip:
            cv2.imwrite(str(path), image)
        haystack = cv2.imread(str(path))
        needle = cv2.imread(str(pack / (name + ".png")))
        result = cv2.matchTemplate(
            haystack[y:bottom, x:right], needle, cv2.TM_CCOEFF_NORMED
        )
        locations = list(zip(*np.where(result >= 0.8)[::-1]))
        unique = []
        for point in locations:
            if all(abs(point[0] - p[0]) >= needle.shape[0] for p in unique):
                unique.append(point)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    v = Detector(ROOT / "media")
    result = {k: [] for k in ("legacy_reads_ms", "legacy_png_roundtrip_ms", "new_ms")}
    output = ROOT / "debug/output"
    output.mkdir(exist_ok=True)
    scratch = output / "benchmark-frame.png"
    for path in sorted((ROOT / "debug").glob("image*.png")):
        im = cv2.imread(str(path))
        v.analyze(im)
        for _ in range(args.repeats):
            start = perf_counter()
            legacy(im, path, False)
            result["legacy_reads_ms"].append((perf_counter() - start) * 1000)
            start = perf_counter()
            legacy(im, scratch, True)
            result["legacy_png_roundtrip_ms"].append((perf_counter() - start) * 1000)
            result["new_ms"].append(v.analyze(im).timings["total_ms"])
    summary = {
        k: dict(mean=mean(a), median=median(a), worst=max(a), samples=len(a))
        for k, a in result.items()
    }
    summary["scope"] = (
        "Offline six original samples. Legacy = original three color-template searches, repeated decoding and x-only deduplication. PNG variant encodes identical in-memory frames in place of screenshot writes. No live capture or input latency measured. New includes anchors, names, classification and pagination."
    )
    print(json.dumps(summary, indent=2))
    (output / "benchmark.json").write_text(json.dumps(summary, indent=2))
    scratch.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
