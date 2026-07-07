# -*- coding: utf-8 -*-

import json
import os
import sys
import threading
import time
from pathlib import Path

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {"mappings": [], "mouse_mappings": []}


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_config():
    config_path = get_base_dir() / CONFIG_FILE
    if not config_path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    config.setdefault("mappings", [])
    config.setdefault("mouse_mappings", [])
    return config


def save_config(config):
    config_path = get_base_dir() / CONFIG_FILE
    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, config_path)


class RemapperEngine:
    def __init__(self):
        self.running = False
        self._thread = None
        self._thread_id = None
        self._thread_lock = threading.Lock()
        self._stop_event = threading.Event()
        self.last_error = None

    def start(self, config):
        with self._thread_lock:
            if self.running or (self._thread and self._thread.is_alive()):
                return
            self.running = True
            self.last_error = None
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, args=(config,), daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()
        thread = self._thread
        thread_id = self._thread_id
        if thread_id:
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
                user32.PostThreadMessageW.restype = wintypes.BOOL
                user32.PostThreadMessageW(thread_id, 0x0012, 0, 0)  # WM_QUIT
            except Exception:
                pass
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        if not thread or not thread.is_alive():
            with self._thread_lock:
                self.running = False
                self._thread = None
                self._thread_id = None

    def _run(self, config):
        import ctypes
        from ctypes import wintypes
        import keyboard as kb

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        WH_MOUSE_LL = 14
        WM_QUIT = 0x0012
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        WM_RBUTTONDOWN = 0x0204
        WM_RBUTTONUP = 0x0205
        WM_MBUTTONDOWN = 0x0207
        WM_MBUTTONUP = 0x0208
        WM_XBUTTONDOWN = 0x020B
        WM_XBUTTONUP = 0x020C
        XBUTTON1 = 1
        XBUTTON2 = 2

        BUTTON_MAP = {
            "left": (WM_LBUTTONDOWN, WM_LBUTTONUP),
            "right": (WM_RBUTTONDOWN, WM_RBUTTONUP),
            "middle": (WM_MBUTTONDOWN, WM_MBUTTONUP),
            "x1": (WM_XBUTTONDOWN, WM_XBUTTONUP),
            "x2": (WM_XBUTTONDOWN, WM_XBUTTONUP),
        }

        XBUTTON_MAP = {"x1": XBUTTON1, "x2": XBUTTON2}

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", wintypes.POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_ulonglong),
            ]

        HOOKPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )

        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
        ]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        ]
        user32.CallNextHookEx.restype = ctypes.c_long
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG), wintypes.HWND,
            wintypes.UINT, wintypes.UINT
        ]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = wintypes.LPARAM
        user32.PeekMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG), wintypes.HWND,
            wintypes.UINT, wintypes.UINT, wintypes.UINT
        ]
        user32.PeekMessageW.restype = wintypes.BOOL
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetCurrentThreadId.argtypes = []
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        mouse_mappings = []
        for m in config.get("mouse_mappings", []):
            if m.get("enabled", True) and m.get("button") in BUTTON_MAP:
                mouse_mappings.append(m)

        pressed_keys = set()
        lock = threading.Lock()
        triggered = [False]
        suppressing = [False]

        def norm(name):
            n = {"ctrl_l": "ctrl", "ctrl_r": "ctrl",
                 "shift_l": "shift", "shift_r": "shift",
                 "alt_l": "alt", "alt_r": "alt"}
            return n.get(name, name)

        def check_match():
            for mapping in config.get("mappings", []):
                if not mapping.get("enabled", True):
                    continue
                trigger = sorted([norm(k) for k in mapping["trigger"]])
                current = sorted([norm(k) for k in pressed_keys])
                if trigger == current:
                    return mapping
            return None

        def normalize_keys(keys):
            if isinstance(keys, str):
                if "+" not in keys:
                    return []
                keys = keys.split("+")
            if not isinstance(keys, (list, tuple)):
                return []
            return [str(k).strip().lower() for k in keys if str(k).strip()]

        def do_output(keys_str):
            keys = normalize_keys(keys_str)
            if not keys:
                return
            pressed = []
            suppressing[0] = True
            try:
                time.sleep(0.03)
                for k in keys:
                    kb.press(k)
                    pressed.append(k)
                for k in reversed(pressed):
                    kb.release(k)
            finally:
                for k in reversed(pressed):
                    try:
                        kb.release(k)
                    except Exception:
                        pass
                time.sleep(0.02)
                suppressing[0] = False

        def on_event(event):
            if self._stop_event.is_set():
                return False
            if suppressing[0]:
                if event.event_type == "up":
                    with lock:
                        pressed_keys.discard(event.name)
                        pressed_keys.discard(norm(event.name))
                return False
            name = event.name
            if event.event_type == "down":
                with lock:
                    pressed_keys.add(name)
                    pressed_keys.add(norm(name))
                mapping = check_match()
                if mapping and not triggered[0]:
                    triggered[0] = True
                    threading.Thread(target=do_output, args=(mapping["output"],), daemon=True).start()
                    return False
            elif event.event_type == "up":
                with lock:
                    pressed_keys.discard(name)
                    pressed_keys.discard(norm(name))
                    if not pressed_keys:
                        triggered[0] = False
            return True

        keyboard_unhook = kb.hook(on_event, suppress=True)

        matched_flag = threading.Event()

        def low_level_mouse_proc(nCode, wParam, lParam):
            if nCode >= 0 and not self._stop_event.is_set():
                info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                for m in mouse_mappings:
                    btn = m["button"]
                    down_msg, up_msg = BUTTON_MAP[btn]
                    if wParam == down_msg:
                        if btn in ("x1", "x2"):
                            xbtn = info.mouseData >> 16
                            expected_xbtn = XBUTTON_MAP[btn]
                            if xbtn != expected_xbtn:
                                continue
                        matched_flag.set()
                        threading.Thread(target=do_output, args=(m["output"],), daemon=True).start()
                        return 1
                    elif wParam == up_msg:
                        if matched_flag.is_set():
                            matched_flag.clear()
                            return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        hook_proc_ref = HOOKPROC(low_level_mouse_proc)
        hinst = kernel32.GetModuleHandleW(None)
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, hook_proc_ref, hinst, 0)
        if not hook:
            self.last_error = f"SetWindowsHookExW failed: {ctypes.get_last_error()}"
            keyboard_unhook()
            with self._thread_lock:
                self.running = False
                if self._thread is threading.current_thread():
                    self._thread = None
                    self._thread_id = None
            return

        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self._thread_id = kernel32.GetCurrentThreadId()

        try:
            while not self._stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result <= 0 or msg.message == WM_QUIT:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            keyboard_unhook()
            user32.UnhookWindowsHookEx(hook)
            with self._thread_lock:
                if self._thread is threading.current_thread():
                    self._thread = None
                    self._thread_id = None
                self.running = False
