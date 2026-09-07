from dataclasses import asdict
from pathlib import Path
import json
from statistics import mean, median
import cv2
from .vision import Detector


def annotate(image, observation):
    out = image.copy()

    def box(b, color):
        cv2.rectangle(
            out,
            (round(b.x), round(b.y)),
            (round(b.x + b.w), round(b.y + b.h)),
            color,
            2,
        )

    box(observation.viewport, (255, 180, 0))
    for t in observation.targets:
        color = (0, 180, 255) if t.ambiguous else (0, 255, 0)
        box(t.box, color)
        x, y = map(round, t.center)
        cv2.circle(out, (x, y), 3, color, -1)
        label = (
            "AMBIGUOUS" if t.ambiguous else "+".join(t.actions) or "done"
        ) + f" {t.confidence:.2f}"
        cv2.putText(
            out,
            label,
            (x + 12, y - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            1,
            cv2.LINE_AA,
        )
    return out


def validate(observation, expected, image_shape):
    errors = []
    if not expected:
        return errors, False
    if observation.state.value != expected["state"]:
        errors.append(f"state {observation.state.value} != {expected['state']}")
    if "targets" not in expected:
        return errors, False
    remaining = list(observation.targets)
    for item in expected["targets"]:
        cx, cy = item["center"]
        tolerance = expected.get("tolerance", 0.012) * min(image_shape[:2])
        matches = [
            t
            for t in remaining
            if (t.center[0] - cx) ** 2 + (t.center[1] - cy) ** 2 < tolerance**2
        ]
        if len(matches) != 1:
            errors.append(
                f'{item["name"]}: expected one target near {(cx,cy)}, found {len(matches)}'
            )
            continue
        t = matches[0]
        remaining.remove(t)
        for field in ("needs_light", "collectible"):
            if field in item and getattr(t, field) != item[field]:
                # Explicitly record permitted abstention; never count it as correct classification.
                if getattr(t, field) is None and field in item.get("allow_abstain", []):
                    continue
                errors.append(
                    f'{item["name"]}: {field}={getattr(t,field)} expected {item[field]}'
                )
    if remaining:
        errors.append(
            f"{len(remaining)} unexpected targets: {[tuple(map(round,t.center)) for t in remaining]}"
        )
    if (
        "page_token" in expected
        and tuple(expected["page_token"]) != observation.page_token
    ):
        errors.append(
            f'page marker {observation.page_token} != {expected["page_token"]}'
        )
    return errors, True


def run_dataset(root: Path, assets: Path, visualize=False, verbose=False):
    manifest_path = root / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text())
        if manifest_path.exists()
        else {"images": {}}
    )
    paths = sorted(
        p
        for p in root.rglob("*")
        if p.suffix.lower()
        in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")
        and "output" not in p.relative_to(root).parts
    )
    if not paths:
        print(f"FAIL: no test images in {root}")
        return 1
    detector = Detector(assets)
    records = []
    failures = 0
    annotated = 0
    for p in paths:
        image = cv2.imread(str(p))
        name = p.relative_to(root).as_posix()
        if image is None:
            print(f"FAIL {name}: cannot decode image")
            failures += 1
            continue
        o = detector.analyze(image)
        errors, grounded = validate(
            o, manifest.get("images", {}).get(name), image.shape
        )
        annotated += grounded
        warnings = list(o.warnings)
        if not grounded:
            warnings.append("No target-level ground truth; smoke test only")
        for t in o.targets:
            if not (
                0 <= t.center[0] < image.shape[1]
                and 0 <= t.center[1] < image.shape[0]
                and 0 <= t.confidence <= 1
            ):
                errors.append("Invalid target geometry/confidence")
            if t.ambiguous and t.actions:
                errors.append("Ambiguous target received an action")
        failures += bool(errors)
        light = sum(t.needs_light is True for t in o.targets)
        collect = sum(t.collectible is True for t in o.targets)
        both = sum(t.needs_light is True and t.collectible is True for t in o.targets)
        ambiguous = sum(t.ambiguous for t in o.targets)
        print(
            f'{"FAIL" if errors else "PASS" if grounded else "SMOKE"} {name} {image.shape[1]}x{image.shape[0]} '
            f"UI={o.state.value} viewport={asdict(o.viewport)} stars={len(o.targets)} "
            f"light={light} collect={collect} both={both} ambiguous={ambiguous} "
            f'{o.timings["total_ms"]:.2f}ms'
        )
        for message in errors + warnings:
            print("  " + message)
        if verbose:
            print("  stages:", o.timings)
            for t in o.targets:
                print(" ", tuple(map(round, t.center)), t.actions, t.evidence)
        records.append(
            dict(file=name, observation=asdict(o), errors=errors, ground_truth=grounded)
        )
        if visualize:
            output = root / "output" / p.relative_to(root)
            output.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(output), annotate(image, o)):
                raise OSError(f"Cannot write {output}")
    times = [r["observation"]["timings"]["total_ms"] for r in records]
    if not times:
        return 1
    summary = dict(
        images=len(paths),
        passed=len(paths) - failures,
        failed=failures,
        annotated=annotated,
        annotated_targets=sum(
            len(manifest["images"][r["file"]]["targets"])
            for r in records
            if r["ground_truth"]
        ),
        annotated_abstentions=sum(
            sum(t[field] is None for field in ("needs_light", "collectible"))
            for r in records
            if r["ground_truth"]
            for t in r["observation"]["targets"]
        ),
        mean_ms=mean(times),
        median_ms=median(times),
        worst_ms=max(times),
        targets=sum(len(r["observation"]["targets"]) for r in records),
        ambiguous_images=[
            r["file"]
            for r in records
            if any(
                t["needs_light"] is None or t["collectible"] is None
                for t in r["observation"]["targets"]
            )
        ],
    )
    print("SUMMARY " + json.dumps(summary))
    print(
        "Capture: N/A (offline). Timings include normalization and all vision stages; exclude decoding/output."
    )
    for stage in ("viewport_anchor_ms", "friend_detection_ms", "classification_ms"):
        print(
            f'{stage}: mean={mean(r["observation"]["timings"][stage] for r in records):.2f}'
        )
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "output" / "report.json").write_text(
        json.dumps(dict(summary=summary, images=records), indent=2)
    )
    return int(failures > 0)
