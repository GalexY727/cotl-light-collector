"""Repeatable offline benchmark; run from the repository root."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--repeats', type=int, default=3)
args = parser.parse_args()
report = {'opencv': main.cv2.__version__, 'numpy': main.np.__version__, 'frames': {}}
for filename in ['image1.png', 'image5.png', 'cache/0.png']:
    main.capture_and_cache_screen(filename)
    times = []
    for _ in range(args.repeats):
        start = time.perf_counter()
        matches = {name: main.locate(name, main.scaled_region('friends'))
                   for name in ['lit_friend', 'unlit_friend', 'flare']}
        times.append(time.perf_counter() - start)
    report['frames'][filename] = {
        'seconds': times, 'median_seconds': statistics.median(times),
        'matches': {name: [{'box': m.box, 'score': m.score} for m in hits]
                    for name, hits in matches.items()},
    }
    print(filename, round(statistics.median(times), 3), {name: len(hits) for name, hits in matches.items()}, flush=True)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2))
