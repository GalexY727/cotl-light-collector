"""Offline labeled baseline + sampled video replay. Never imports input backends."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
from detector import observe, UIState
from automation import plan_page


def run(output, video_step=.5):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=True)
    labels = json.loads((root/'tests/baseline_labels.json').read_text())['pages']
    results = []
    for path in sorted((root/'media/new').rglob('*.jpg')):
        frame = cv2.imread(str(path))
        timings = []
        for _ in range(3):
            start = time.perf_counter()
            observation = observe(frame)
            queue = plan_page(observation) if observation.state == UIState.LIST else []
            timings.append(time.perf_counter()-start)
        errors = []
        if path.name in labels:
            label = labels[path.name]
            expected = {(c, r): (([c, r] not in label['already_lit']), [c, r] in label['collect'])
                        for c in range(3) for r in range(7) if [c, r] not in label['empty']}
            actual = {f.slot: (f.needs_light, f.needs_collect) for f in observation.friends}
            errors = [str(slot) for slot in expected.keys() | actual.keys() if expected.get(slot) != actual.get(slot)]
        for friend in observation.friends:
            x, y = friend.center
            text = 'BOTH' if friend.needs_light and friend.needs_collect else (
                'LIGHT' if friend.needs_light else 'COLLECT' if friend.needs_collect else 'done')
            color = (0, 180, 255) if text != 'done' else (0, 220, 0)
            cv2.circle(frame, (x, y), 31, color, 2)
            cv2.putText(frame, text, (x+28, y-15), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1)
        cv2.imwrite(str(output/(path.stem+'.jpg')), frame)
        results.append({'file':str(path.relative_to(root)), 'state':observation.state.value,
                        'friends':len(observation.friends), 'actions':len(queue),
                        'lighting':sum(f.needs_light for f in observation.friends),
                        'collecting':sum(f.needs_collect for f in observation.friends),
                        'both':sum(f.needs_light and f.needs_collect for f in observation.friends),
                        'planning_seconds':timings, 'mismatched_slots':errors})
    video = cv2.VideoCapture(str(root/'media/new/2026-10-27 23-37-56.mp4'))
    if not video.isOpened():
        raise RuntimeError('Cannot read baseline video')
    samples = []
    seconds = 0
    while seconds < video.get(cv2.CAP_PROP_FRAME_COUNT)/video.get(cv2.CAP_PROP_FPS):
        video.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
        ok, frame = video.read()
        if not ok:
            raise RuntimeError(f'Cannot read video at {seconds}s')
        start = time.perf_counter()
        observation = observe(frame)
        queue = plan_page(observation) if observation.state == UIState.LIST else []
        samples.append({'seconds':seconds, 'state':observation.state.value,
                        'friends':len(observation.friends), 'actions':len(queue),
                        'planning_seconds':time.perf_counter()-start})
        seconds += video_step
    video.release()
    passed = not any(r['mismatched_slots'] or max(r['planning_seconds']) >= 1 for r in results)
    passed &= not any(s['planning_seconds'] >= 1 for s in samples)
    report = {'passed':bool(passed), 'images':results, 'video_samples':samples}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed':bool(passed), 'images':len(results), 'video_samples':len(samples),
                      'max_planning_seconds':max([max(r['planning_seconds']) for r in results] +
                                                 [s['planning_seconds'] for s in samples]),
                      'mismatches':sum(len(r['mismatched_slots']) for r in results)}, indent=2))
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('cache/baseline-replay'))
    parser.add_argument('--video-step', type=float, default=.5)
    args = parser.parse_args()
    if args.video_step <= 0:
        parser.error('--video-step must be positive')
    sys.exit(0 if run(args.output, args.video_step) else 1)
