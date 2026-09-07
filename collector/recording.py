"""Temporary live evidence and offline perception replay; no desktop imports."""

import json
from dataclasses import asdict
from time import monotonic
from pathlib import Path

import cv2


class Recorder:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.stream = (self.directory / "events.jsonl").open("w", encoding="utf-8")
        self.started = monotonic()
        self.sequence = 0

    def event(self, kind, **data):
        self.stream.write(json.dumps(dict(seconds=round(monotonic() - self.started, 4), kind=kind, **data), default=str) + "\n")
        self.stream.flush()

    def frame(self, frame, label, observation=None):
        self.sequence += 1
        name = f"frame-{self.sequence:06d}.png"
        if not cv2.imwrite(str(self.directory / name), frame):
            raise OSError(f"Cannot save diagnostic screenshot {name}")
        self.event("frame", file=name, label=label,
                   observation=asdict(observation) if observation is not None else None)

    def close(self):
        self.stream.close()


def replay(directory, detector):
    """Re-run perception on recorded frames in order, without sending input."""
    directory = Path(directory)
    count = 0
    changed = 0
    with (directory / "events.jsonl").open(encoding="utf-8") as source, (directory / "replay.jsonl").open("w", encoding="utf-8") as output:
        for line in source:
            event = json.loads(line)
            if event["kind"] != "frame":
                continue
            image = cv2.imread(str(directory / event["file"]))
            if image is None:
                raise ValueError(f"Missing recorded frame: {event['file']}")
            observed = detector.analyze(image)
            previous = event.get("observation")
            different = previous is not None and (
                previous["state"] != observed.state.value
                or previous["page_token"] != list(observed.page_token)
                or previous["targets"] != json.loads(json.dumps(asdict(observed), default=str))["targets"]
            )
            changed += bool(different)
            count += 1
            output.write(json.dumps(dict(file=event["file"], label=event["label"], changed=different, observation=asdict(observed)), default=str) + "\n")
    print(f"Replayed {count} frames; {changed} changed detections. Results: {directory / 'replay.jsonl'}")
    return 0
