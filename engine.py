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
        import keyboard as kb
        from pynput import mouse as pynput_mouse

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
            for k in keys_str:
                kb.press(k.lower())
            for k in reversed(keys_str):
                kb.release(k.lower())
            suppressing[0] = False

        def on_event(event):
            if self._stop_event.is_set():
                return
            if suppressing[0]:
                return
            name = event.name
            if event.event_type == "down":
                with lock:
                    pressed_keys.add(name)
                    pressed_keys.add(norm(name))
                mapping = check_match()
                if mapping and not triggered[0]:
                    triggered[0] = True
                    threading.Thread(target=do_output, args=(mapping["output"],), daemon=True).start()
            elif event.event_type == "up":
                with lock:
                    pressed_keys.discard(name)
                    pressed_keys.discard(norm(name))
                    if not pressed_keys:
                        triggered[0] = False

        def on_mouse_click(x, y, button, pressed):
            if self._stop_event.is_set():
                return
            if pressed:
                for mapping in config.get("mouse_mappings", []):
                    if not mapping.get("enabled", True):
                        continue
                    if mapping["button"] == button.name:
                        threading.Thread(target=do_output, args=(mapping["output"],), daemon=True).start()
                        return

        kb.hook(on_event)
        ml = pynput_mouse.Listener(on_click=on_mouse_click)
        ml.start()

        while not self._stop_event.is_set():
            time.sleep(0.1)

        kb.unhook_all()
        ml.stop()
