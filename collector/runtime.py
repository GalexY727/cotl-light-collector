"""Windows-only adapters, imported only for live execution."""

import ctypes
from ctypes import wintypes
from pathlib import Path
from time import perf_counter, monotonic, sleep
from ahk import AHK
from ahk.exceptions import AHKBaseException, AhkExecutableNotFoundError
import numpy as np


class LiveError(RuntimeError):
    pass


class WindowsGame:
    key_hold_seconds = 0.1

    def __init__(self, title="Sky", focus_timeout=10.0, recorder=None):
        self.recorder = recorder
        if not hasattr(ctypes, "WinDLL"):
            raise LiveError("Live mode requires Windows")
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        self.user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.GetClientRect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.RECT),
        ]
        self.user.ClientToScreen.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.POINT),
        ]
        self.user.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        name = ctypes.create_unicode_buffer(512)
        deadline = monotonic() + focus_timeout
        while True:
            self.hwnd = self.user.GetForegroundWindow()
            self.user.GetWindowTextW(self.hwnd, name, len(name))
            if title.casefold() in name.value.casefold():
                break
            if monotonic() >= deadline:
                raise LiveError(
                    f"Game ({title!r}) did not receive focus before startup timeout"
                )
            sleep(0.1)
        import mss

        self.sct = mss.mss()
        self.ahk = self.create_ahk()
        self.last_rect = None

    @staticmethod
    def create_ahk():
        """Use the v1 executable that the original working collector used."""
        executable = Path(r"C:\Program Files\AutoHotkey\v1.1.37.02\AutoHotkeyU64.exe")
        kwargs = {"version": "v1"}
        if executable.is_file():
            kwargs["executable_path"] = str(executable)
        try:
            return AHK(**kwargs)
        except AhkExecutableNotFoundError as error:
            raise LiveError(
                "AutoHotkey v1 is required for live input but was not found"
            ) from error

    def rect(self):
        if self.user.GetForegroundWindow() != self.hwnd:
            raise LiveError("Sky lost focus; stopped before sending input")
        r = wintypes.RECT()
        p = wintypes.POINT(0, 0)
        if not self.user.GetClientRect(
            self.hwnd, ctypes.byref(r)
        ) or not self.user.ClientToScreen(self.hwnd, ctypes.byref(p)):
            raise LiveError("Cannot read game client geometry")
        if r.right < 200 or r.bottom < 200:
            raise LiveError("Game client is minimized or too small")
        return dict(left=p.x, top=p.y, width=r.right, height=r.bottom)

    def capture(self):
        start = perf_counter()
        self.last_rect = self.rect()
        frame = np.asarray(self.sct.grab(self.last_rect))[:, :, :3].copy()
        return frame, (perf_counter() - start) * 1000

    def guard(self):
        rect = self.rect()
        if rect != self.last_rect:
            raise LiveError(
                "Game window moved/resized after capture; stopped before using stale coordinates"
            )
        return rect

    def click(self, point):
        rect = self.guard()
        x, y = point
        if not (0 <= x < rect["width"] and 0 <= y < rect["height"]):
            raise LiveError("Detected click lies outside the game client")
        screen_x, screen_y = round(x + rect["left"]), round(y + rect["top"])
        print(
            f"[input] click client=({round(x)}, {round(y)}) "
            f"screen=({screen_x}, {screen_y})",
            flush=True,
        )
        self.dispatch(self.ahk.click, screen_x, screen_y)

    def key(self, key):
        self.guard()
        print(f"[input] key={key}", flush=True)
        self.dispatch(self.ahk.key_down, key)
        sleep(self.key_hold_seconds)
        self.dispatch(self.ahk.key_up, key)

    def move(self, point):
        rect = self.guard()
        x, y = point
        if not (0 <= x < rect["width"] and 0 <= y < rect["height"]):
            raise LiveError("Pointer parking location is outside the game client")
        print(
            f"[input] mouse move client=({round(x)}, {round(y)}) "
            f"screen=({round(x + rect['left'])}, {round(y + rect['top'])})",
            flush=True,
        )
        self.dispatch(
            self.ahk.mouse_move,
            round(x + rect["left"]),
            round(y + rect["top"]),
            speed=0,
        )

    def nudge(self):
        self.guard()
        print("[input] mouse move relative=(1, 0)", flush=True)
        self.dispatch(self.ahk.mouse_move, 1, 0, speed=0, relative=True)

    def dispatch(self, action, *args, **kwargs):
        recorder = getattr(self, "recorder", None)
        name = getattr(action, "__name__", str(action))
        # Key-up must not be delayed by disk writes or additional capture.
        record_frame = name in ("click", "key_down")
        if recorder:
            if record_frame:
                self.record_snapshot("before " + name)
            recorder.event("input", action=name, args=args, kwargs=kwargs)
        try:
            action(*args, **kwargs)
        except (AHKBaseException, OSError) as error:
            raise LiveError("AutoHotkey input dispatch failed") from error

    def record_snapshot(self, label):
        # Do not overwrite last_rect: the input geometry guard must remain valid.
        rect = self.guard()
        frame = np.asarray(self.sct.grab(rect))[:, :, :3].copy()
        self.recorder.frame(frame, label)

    def close(self):
        self.sct.close()
