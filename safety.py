"""Windows foreground and pause watchdog. No hooks or input at import time."""
import ctypes
from ctypes import wintypes
import threading
import time


class AutomationPaused(RuntimeError):
    pass


class WindowsSafety:
    def __init__(self, title='Sky'):
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.IsWindow.argtypes = [wintypes.HWND]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user.GetAsyncKeyState.restype = ctypes.c_short
        found = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def visit(hwnd, _):
            length = self.user.GetWindowTextLengthW(hwnd)
            text = ctypes.create_unicode_buffer(length+1)
            self.user.GetWindowTextW(hwnd, text, length+1)
            if self.user.IsWindowVisible(hwnd) and title.casefold() in text.value.casefold():
                found.append(hwnd)
            return True

        self.user.EnumWindows(visit, 0)
        if len(found) != 1:
            raise RuntimeError(f'Expected one visible game window matching {title!r}; found {len(found)}. '
                               'Use --game-title with its unique title.')
        self.hwnd = found[0]
        self.lock = threading.RLock()
        self.paused = threading.Event()
        self.stopped = threading.Event()
        self.held = set()
        self.ahk = None
        self.reason = ''
        self.generation = 0
        self.worker = threading.Thread(target=self.watch, daemon=True)

    def focused(self):
        return self.user.IsWindow(self.hwnd) and self.user.GetForegroundWindow() == self.hwnd

    def release(self):
        # Track before key_down so an interrupted backend call is released too.
        with self.lock:
            failures = []
            for key in tuple(self.held):
                try:
                    self.ahk.key_up(key)
                    self.held.remove(key)
                except Exception as error:
                    failures.append(error)
            if failures:
                raise RuntimeError('Could not release an automation key') from failures[0]

    def pause(self, reason):
        with self.lock:
            if not self.paused.is_set():
                self.reason = reason
                self.generation += 1
                self.paused.set()
                print(f'Paused: {reason}. Focus the game and press = to rescan and resume.')
            self.release()

    def check(self):
        if not self.focused():
            self.pause('game lost foreground focus')
        if self.paused.is_set():
            raise AutomationPaused(self.reason)

    def watch(self):
        was_resume = False
        while not self.stopped.wait(.02):
            try:
                if any(self.user.GetAsyncKeyState(k) & 0x8000 for k in (0xBD, 0x6D, 0x08)):
                    self.pause('pause key')
                elif not self.focused():
                    self.pause('game lost foreground focus')
                resume = bool(self.user.GetAsyncKeyState(0xBB) & 0x8000)
                if resume and not was_resume and self.focused():
                    with self.lock:
                        self.paused.clear()
                was_resume = resume
            except Exception as error:
                self.reason = str(error)
                self.paused.set()
                self.stopped.set()

    def start(self):
        self.worker.start()

    def key(self, key, *, generation=None):
        if self.ahk is None:
            # Starting the backend can block; leave the watchdog free to pause.
            from ahk import AHK
            self.ahk = AHK()
        try:
            with self.lock:
                self.check()
                if generation is not None and generation != self.generation:
                    raise AutomationPaused('interaction interrupted; rescan required')
                self.held.add(key)
                self.ahk.key_down(key)
            time.sleep(.1)
        finally:
            self.release()
        self.check()

    def action(self, function, *args, generation=None):
        with self.lock:
            self.check()
            if generation is not None and generation != self.generation:
                raise AutomationPaused('interaction interrupted; rescan required')
            function(*args)
        self.check()

    def open_friend(self, x, y, *, generation=None):
        if self.ahk is None:
            from ahk import AHK
            self.ahk = AHK()
        for _ in range(2):
            self.action(lambda: self.ahk.click(x, y, coord_mode='Screen'), generation=generation)

    def close(self):
        self.stopped.set()
        self.worker.join(timeout=1)
        self.release()
