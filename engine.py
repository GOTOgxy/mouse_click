# -*- coding: utf-8 -*-

import json
import sys
import threading
import time
from pathlib import Path

CONFIG_FILE = "config.json"


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_config():
    config_path = get_base_dir() / CONFIG_FILE
    if not config_path.exists():
        return {"mappings": [], "mouse_mappings": []}
    return json.loads(config_path.read_text(encoding="utf-8"))


def save_config(config):
    config_path = get_base_dir() / CONFIG_FILE
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


class RemapperEngine:
    def __init__(self):
        self.running = False
        self._thread = None
        self._stop_event = threading.Event()

    def start(self, config):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(config,), daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()

    def _run(self, config):
        import ctypes
        from ctypes import wintypes
        import keyboard as kb

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        WH_MOUSE_LL = 14
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
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = wintypes.LPARAM
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

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

        def do_output(keys_str):
            suppressing[0] = True
            time.sleep(0.05)
            kb.press(keys_str[0].lower())
            for k in keys_str[1:]:
                kb.press(k.lower())
            for k in reversed(keys_str):
                kb.release(k.lower())
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

        kb.hook(on_event)

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

        msg = wintypes.MSG()
        while not self._stop_event.is_set():
            user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        kb.unhook_all()
        user32.UnhookWindowsHookEx(hook)
