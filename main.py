"""CLI: offline tests never import or initialize capture/input adapters."""

import argparse
import logging
from pathlib import Path
from statistics import mean
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verified Sky constellation light collector"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Analyze every debug image without live input",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Write annotated test images under debug/output",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Detailed observations and timing logs"
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path(__file__).resolve().parent / "debug"
    )
    parser.add_argument(
        "--window-title",
        default="Sky",
        help="Required substring of foreground game window title",
    )
    parser.add_argument(
        "--focus-timeout",
        type=float,
        default=10.0,
        help="Seconds to focus Sky after launch",
    )
    parser.add_argument("--record", action="store_true", help="Record full live run to temporary cache/live")
    parser.add_argument("--replay", action="store_true", help="Replay cache/live screenshots offline; no game input")
    args = parser.parse_args(argv)
    if sum((args.test, args.record, args.replay)) > 1:
        parser.error("Choose one of --test, --record, or --replay")
    if not args.window_title.strip() or args.focus_timeout < 0:
        parser.error("Use a nonempty window title and nonnegative focus timeout")
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
    )
    if args.test:
        from collector.diagnostics import run_dataset

        return run_dataset(args.dataset, root / "media", args.visualize, args.debug)
    from collector.vision import Detector
    from collector.controller import Runner, TransitionError
    cache = Path(__file__).resolve().parent / "cache" / "live"
    if args.replay:
        from collector.recording import replay
        return replay(cache, Detector(root / "media"))
    from collector.runtime import WindowsGame, LiveError

    game = None
    recorder = None
    handler = None
    if args.record:
        from collector.recording import Recorder
        recorder = Recorder(cache)
        handler = logging.FileHandler(cache / "run.log", mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.info("Recording full run to %s; events and numbered frames overwrite the previous run", cache)
    try:
        logging.info(
            "Focus Sky within %.1f seconds. No input is sent until its UI is recognized.",
            args.focus_timeout,
        )
        game = WindowsGame(args.window_title, args.focus_timeout, recorder=recorder)
        runner = Runner(Detector(root / "media"), game, game, recorder=recorder)
        runner.run()
        if recorder:
            recorder.event("finished")
        return 0
    except (TransitionError, LiveError, KeyboardInterrupt) as error:
        logging.error("Stopped safely: %s", error or "interrupted")
        if recorder:
            recorder.event("failure", error=str(error) or "interrupted")
            if game is not None:
                try:
                    game.record_snapshot("failure")
                except Exception as capture_error:
                    recorder.event("failure_capture_unavailable", error=str(capture_error))
        if "runner" in locals():
            runner.report_observation("last observation before stop")
        return 1
    finally:
        if game is not None:
            game.close()
        if "runner" in locals() and runner.metrics:
            logging.info(
                "Live means: %s",
                {
                    k: round(mean(m[k] for m in runner.metrics), 2)
                    for k in runner.metrics[0]
                },
            )
        if recorder:
            recorder.close()
        if handler:
            logging.getLogger().removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
