# -*- coding: utf-8 -*-

import ctypes
import ctypes.wintypes as wintypes
import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from engine import RemapperEngine, load_config, save_config


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
TRAY_ICON_ID = 1


ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeout", wintypes.UINT),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def _clamp(value, low, high):
    return max(low, min(high, value))


def _compute_ui_scale(root):
    try:
        dpi_scale = root.winfo_fpixels("1i") / 96.0
    except tk.TclError:
        dpi_scale = 1.0
    screen_w = max(root.winfo_screenwidth(), 1)
    screen_h = max(root.winfo_screenheight(), 1)
    resolution_scale = min(screen_w / 1920, screen_h / 1080)
    return _clamp(max(dpi_scale, resolution_scale, 1.0), 1.0, 1.45)


def scaled(widget, value):
    scale = getattr(widget.winfo_toplevel(), "ui_scale", 1.0)
    return int(round(value * scale))


def ui_font(widget, size, weight=None):
    return ctk.CTkFont(family="Microsoft YaHei UI", size=scaled(widget, size), weight=weight)


def _dialog_font(widget, delta=0, weight=None):
    size = 19 + delta
    return ctk.CTkFont(family="Microsoft YaHei UI", size=scaled(widget, size), weight=weight)


def _readonly_entry(parent, variable):
    entry = ctk.CTkEntry(parent, textvariable=variable, font=_dialog_font(parent))
    entry.bind("<Key>", lambda _event: "break")
    return entry


class _BindXDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, width, height):
        super().__init__(parent)
        self._bindx_root = parent.winfo_toplevel()
        self.ui_scale = getattr(self._bindx_root, "ui_scale", 1.0)
        self.result = None

        self.title(title)
        self.geometry(f"{scaled(self, width)}x{scaled(self, height)}")
        self.minsize(scaled(self, width), scaled(self, height))
        self.resizable(False, False)
        self.configure(fg_color=("#f4f4f5", "#18181b"))
        self.transient(self._bindx_root)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill=tk.BOTH, expand=True, padx=scaled(self, 20), pady=scaled(self, 18))
        self.after(50, self.focus_force)

    def _center_on_parent(self):
        self.update_idletasks()
        parent = self._bindx_root
        x = parent.winfo_x() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_y() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _label(self, parent, text, width=118):
        return ctk.CTkLabel(parent, text=text, width=scaled(self, width), anchor="w", font=_dialog_font(self))

    def _row(self, parent=None, pady=(0, 10)):
        row = ctk.CTkFrame(parent or self.body, fg_color="transparent")
        row.pack(fill=tk.X, pady=(scaled(self, pady[0]), scaled(self, pady[1])))
        return row

    def _button_row(self):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill=tk.X, pady=(scaled(self, 12), 0))
        return row

    def _secondary_button(self, parent, text, command, width=84):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=scaled(self, width),
            font=_dialog_font(self),
            fg_color="#52525b",
            hover_color="#3f3f46",
        )

    def _on_cancel(self):
        self.result = None
        self.destroy()


class KeyCaptureDialog(_BindXDialog):
    KEYSYM_MAP = {
        "return": "enter",
        "escape": "esc",
        "space": "space",
        "left": "left",
        "right": "right",
        "up": "up",
        "down": "down",
        "home": "home",
        "end": "end",
        "prior": "pageup",
        "next": "pagedown",
        "insert": "insert",
        "delete": "delete",
        "backspace": "backspace",
        "caps_lock": "caps lock",
        "tab": "tab",
    }
    MODIFIER_MAP = {
        "control_l": "ctrl",
        "control_r": "ctrl",
        "alt_l": "alt",
        "alt_r": "alt",
        "shift_l": "shift",
        "shift_r": "shift",
        "super_l": "win",
        "super_r": "win",
        "meta_l": "win",
        "meta_r": "win",
    }
    MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")

    def __init__(self, parent, title="录制按键"):
        super().__init__(parent, title, 540, 230)
        self._pressed = set()
        self._captured = []

        ctk.CTkLabel(self.body, text="请按下目标按键组合", font=_dialog_font(self, 2, "bold")).pack(anchor=tk.W, pady=(0, scaled(self, 10)))
        self.key_var = tk.StringVar(value="等待输入...")
        ctk.CTkLabel(self.body, textvariable=self.key_var, font=_dialog_font(self, 5, "bold")).pack(fill=tk.X, pady=(0, scaled(self, 18)))

        btns = self._button_row()
        self.ok_btn = ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 88), font=_dialog_font(self))
        self.ok_btn.pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self.ok_btn.configure(state=tk.DISABLED)
        self._secondary_button(btns, "取消", self._on_cancel).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self._secondary_button(btns, "清除", self._on_clear).pack(side=tk.RIGHT)

        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self._center_on_parent()

    def _normalize(self, keysym):
        key = keysym.lower()
        if key in self.MODIFIER_MAP:
            return self.MODIFIER_MAP[key]
        if len(key) == 1:
            return key.lower()
        if key.startswith("f") and key[1:].isdigit():
            return key.lower()
        return self.KEYSYM_MAP.get(key, key)

    def _on_key_release(self, event):
        self._pressed.discard(self._normalize(event.keysym))

    def _on_key_press(self, event):
        name = self._normalize(event.keysym)
        if name in self.MODIFIER_ORDER:
            self._pressed.add(name)
            return
        modifiers = [mod for mod in self.MODIFIER_ORDER if mod in self._pressed]
        self._captured = modifiers + [name]
        self.key_var.set(" + ".join(self._captured))
        self.ok_btn.configure(state=tk.NORMAL)

    def _on_clear(self):
        self._pressed.clear()
        self._captured = []
        self.key_var.set("等待输入...")
        self.ok_btn.configure(state=tk.DISABLED)

    def _on_ok(self):
        if self._captured:
            self.result = self._captured
            self.destroy()


class MouseCaptureDialog(_BindXDialog):
    def __init__(self, parent, title="录制鼠标按键"):
        super().__init__(parent, title, 540, 230)
        self._listener = None

        ctk.CTkLabel(self.body, text="请按下鼠标按键", font=_dialog_font(self, 2, "bold")).pack(anchor=tk.W, pady=(0, scaled(self, 10)))
        self.key_var = tk.StringVar(value="等待输入...")
        ctk.CTkLabel(self.body, textvariable=self.key_var, font=_dialog_font(self, 5, "bold")).pack(fill=tk.X, pady=(0, scaled(self, 18)))

        btns = self._button_row()
        self.ok_btn = ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 88), font=_dialog_font(self))
        self.ok_btn.pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self.ok_btn.configure(state=tk.DISABLED)
        self._secondary_button(btns, "取消", self._on_cancel).pack(side=tk.RIGHT)

        self._start_listener()
        self._center_on_parent()

    def _start_listener(self):
        try:
            from pynput import mouse as pynput_mouse
        except ImportError as exc:
            self.key_var.set(f"鼠标监听不可用：{exc}")
            return

        def on_click(_x, _y, button, pressed):
            if pressed:
                self.after(0, lambda: self._on_detected(getattr(button, "name", str(button))))

        self._listener = pynput_mouse.Listener(on_click=on_click)
        self._listener.start()

    def _on_detected(self, name):
        self.key_var.set(name)
        self.ok_btn.configure(state=tk.NORMAL)

    def _on_ok(self):
        val = self.key_var.get()
        if val and val != "等待输入..." and not val.startswith("鼠标监听不可用"):
            self.result = val
        self._stop_listener()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self._stop_listener()
        self.destroy()

    def _stop_listener(self):
        if self._listener:
            self._listener.stop()
            self._listener = None


class AddMappingDialog(_BindXDialog):
    def __init__(self, parent, mapping_type="keyboard"):
        super().__init__(parent, "映射设置", 660, 430)
        self.mapping_type = mapping_type

        self.type_var = tk.StringVar(value=mapping_type)
        self.trigger_var = tk.StringVar(value="")
        self.button_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value="")
        self.desc_var = tk.StringVar(value="")

        row = self._row()
        self._label(row, "类型：").pack(side=tk.LEFT)
        ctk.CTkOptionMenu(row, values=["keyboard", "mouse"], variable=self.type_var, command=self._on_type_changed, width=scaled(self, 180), font=_dialog_font(self)).pack(side=tk.LEFT)

        self.trigger_frame = self._row()
        self._label(self.trigger_frame, "触发键：").pack(side=tk.LEFT)
        _readonly_entry(self.trigger_frame, self.trigger_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(self.trigger_frame, text="录制", command=self._capture_trigger, width=scaled(self, 82), font=_dialog_font(self)).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        self.mouse_frame = self._row()
        self._label(self.mouse_frame, "鼠标按键：").pack(side=tk.LEFT)
        ctk.CTkOptionMenu(self.mouse_frame, values=["left", "right", "middle", "x1", "x2"], variable=self.button_var, width=scaled(self, 180), font=_dialog_font(self)).pack(side=tk.LEFT)
        ctk.CTkButton(self.mouse_frame, text="录制", command=self._capture_mouse, width=scaled(self, 82), font=_dialog_font(self)).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        row = self._row()
        self._label(row, "输出键：").pack(side=tk.LEFT)
        _readonly_entry(row, self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(row, text="录制", command=self._capture_output, width=scaled(self, 82), font=_dialog_font(self)).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        row = self._row()
        self._label(row, "描述：").pack(side=tk.LEFT)
        ctk.CTkEntry(row, textvariable=self.desc_var, font=_dialog_font(self)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        btns = self._button_row()
        ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 92), font=_dialog_font(self)).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self._secondary_button(btns, "取消", self._on_cancel, width=92).pack(side=tk.RIGHT)

        self._on_type_changed()
        self._center_on_parent()

    def _on_type_changed(self, _value=None):
        self.mapping_type = self.type_var.get()
        if self.mapping_type == "keyboard":
            self.trigger_frame.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            self.mouse_frame.pack_forget()
        else:
            self.trigger_frame.pack_forget()
            self.mouse_frame.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            if not self.button_var.get():
                self.button_var.set("x1")

    def _capture_trigger(self):
        dlg = KeyCaptureDialog(self, "录制触发键")
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self.trigger_var.set(" + ".join(dlg.result))

    def _capture_output(self):
        dlg = KeyCaptureDialog(self, "录制输出键")
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self.output_var.set(" + ".join(dlg.result))

    def _capture_mouse(self):
        dlg = MouseCaptureDialog(self, "录制鼠标按键")
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self.button_var.set(dlg.result)

    def _on_ok(self):
        trigger = self.trigger_var.get().strip()
        output = self.output_var.get().strip()
        if self.mapping_type == "mouse":
            button = self.button_var.get().strip()
            if not button or not output:
                messagebox.showwarning("提示", "请录制按键", parent=self)
                return
        else:
            if not trigger or not output:
                messagebox.showwarning("提示", "请录制按键", parent=self)
                return

        self.result = {
            "trigger": [k.strip() for k in trigger.split("+") if k.strip()],
            "output": [k.strip() for k in output.split("+") if k.strip()],
            "description": self.desc_var.get().strip() or f"{trigger if self.mapping_type == 'keyboard' else 'Mouse ' + self.button_var.get()} -> {output}",
            "enabled": True,
        }
        if self.mapping_type == "mouse":
            self.result["button"] = self.button_var.get()
        self.destroy()


class RemapperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.ui_scale = _compute_ui_scale(self)
        ctk.set_widget_scaling(self.ui_scale)
        ctk.set_window_scaling(self.ui_scale)
        self.tk.call("tk", "scaling", self.ui_scale)

        self.title("按键重映射")
        self.geometry("1120x760")
        self.minsize(900, 620)
        self.configure(fg_color=("#f4f4f5", "#18181b"))

        self.config = load_config()
        self.engine = RemapperEngine()
        self._tray_queue = queue.Queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_tree_style()
        self._create_tray_icon()
        self._create_ui()
        self._refresh_list()
        self._start_engine()
        self._poll_tray_queue()

    def _setup_tree_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            borderwidth=0,
            relief="flat",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#18181b",
            font=("Microsoft YaHei UI", scaled(self, 20)),
            rowheight=scaled(self, 66),
        )
        style.configure(
            "Treeview.Heading",
            background="#e4e4e7",
            foreground="#27272a",
            relief="flat",
            font=("Microsoft YaHei UI", scaled(self, 21), "bold"),
        )
        style.map("Treeview", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])

    def _create_programmatic_icon(self):
        size = 16
        hdc_screen = user32.GetDC(None)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbm = gdi32.CreateCompatibleBitmap(hdc_screen, size, size)
        gdi32.SelectObject(hdc_mem, hbm)

        hbr_bg = gdi32.CreateSolidBrush(0x003366CC)
        rect = wintypes.RECT(0, 0, size, size)
        user32.FillRect(hdc_mem, ctypes.byref(rect), hbr_bg)
        gdi32.DeleteObject(hbr_bg)

        gdi32.SetBkMode(hdc_mem, 1)
        hfont = gdi32.CreateFontW(12, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, "Consolas")
        old_font = gdi32.SelectObject(hdc_mem, hfont)
        gdi32.SetTextColor(hdc_mem, 0x00FFFFFF)
        gdi32.TextOutW(hdc_mem, 2, 1, "KR", 2)
        gdi32.SelectObject(hdc_mem, old_font)
        gdi32.DeleteObject(hfont)

        mask_bm = gdi32.CreateBitmap(size, size, 1, 1, None)
        hdc_mask = gdi32.CreateCompatibleDC(None)
        gdi32.SelectObject(hdc_mask, mask_bm)
        hbr_white = gdi32.CreateSolidBrush(0x00FFFFFF)
        user32.FillRect(hdc_mask, ctypes.byref(rect), hbr_white)
        gdi32.DeleteObject(hbr_white)

        class ICONINFO(ctypes.Structure):
            _fields_ = [
                ("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP),
                ("hbmColor", wintypes.HBITMAP),
            ]

        icon_info = ICONINFO(True, 0, 0, mask_bm, hbm)
        h_icon = user32.CreateIconIndirect(ctypes.byref(icon_info))

        gdi32.DeleteObject(mask_bm)
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mask)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)
        return h_icon

    def _create_tray_icon(self):
        self.tray_hwnd = None
        self._tray_event = 0

        self._tray_wndproc_ref = ctypes.WINFUNCTYPE(
            wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )(self._tray_wndproc_impl)

        wc = WNDCLASS()
        wc.lpfnWndProc = ctypes.cast(self._tray_wndproc_ref, ctypes.c_void_p)
        wc.lpszClassName = "MouseRemapperTray"
        wc.hInstance = kernel32.GetModuleHandleW(None)
        user32.RegisterClassW(ctypes.byref(wc))

        self.tray_hwnd = user32.CreateWindowExW(
            0, wc.lpszClassName, "MouseRemapperTray",
            0, 0, 0, 0, 0, None, None, wc.hInstance, None
        )

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.tray_hwnd
        nid.uID = TRAY_ICON_ID
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = 0x0400
        nid.hIcon = self._create_programmatic_icon()
        nid.szTip = "按键重映射"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _tray_wndproc_impl(self, hwnd, msg, wparam, lparam):
        if msg == 0x0400:
            self._tray_queue.put(lparam)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _poll_tray_queue(self):
        try:
            while True:
                ev = self._tray_queue.get_nowait()
                if ev == WM_RBUTTONUP:
                    self._show_tray_menu()
                elif ev in {0x0202, WM_LBUTTONDBLCLK}:
                    self._show_window()
        except queue.Empty:
            pass
        self.after(20, self._poll_tray_queue)

    def _show_tray_menu(self):
        self.tray_menu = tk.Menu(self, tearoff=0)
        self.tray_menu.add_command(label="显示主窗口", command=self._show_window)
        self.tray_menu.add_separator()
        self.tray_menu.add_command(label="退出", command=self._quit_app)

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.tray_hwnd)
        self.tray_menu.tk_popup(pt.x, pt.y)
        self.tray_menu.grab_release()

    def _remove_tray_icon(self):
        if self.tray_hwnd:
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self.tray_hwnd
            nid.uID = TRAY_ICON_ID
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            user32.DestroyWindow(self.tray_hwnd)
            self.tray_hwnd = None

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _create_ui(self):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill=tk.BOTH, expand=True, padx=scaled(self, 18), pady=scaled(self, 18))

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, scaled(self, 12)))
        ctk.CTkLabel(header, text="鼠标映射", font=ui_font(self, 20, "bold")).pack(side=tk.LEFT)

        toolbar = ctk.CTkFrame(outer, corner_radius=10)
        toolbar.pack(fill=tk.X, pady=(0, scaled(self, 12)))
        ctk.CTkButton(toolbar, text="添加", command=self._add_mapping, width=76).pack(side=tk.LEFT, padx=(12, 6), pady=10)
        ctk.CTkButton(toolbar, text="编辑", command=self._edit_entry, width=76).pack(side=tk.LEFT, padx=6, pady=10)
        ctk.CTkButton(toolbar, text="删除", command=self._delete_entry, width=76, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=6, pady=10)
        self.running_var = tk.BooleanVar(value=True)
        ctk.CTkSwitch(toolbar, text="运行中", variable=self.running_var, onvalue=True, offvalue=False, command=self._toggle_engine, font=ui_font(self, 14)).pack(side=tk.LEFT, padx=(scaled(self, 18), 0), pady=10)
        ctk.CTkButton(toolbar, text="退出", command=self._quit_app, width=76, fg_color="#991b1b", hover_color="#7f1d1d").pack(side=tk.RIGHT, padx=(6, 12), pady=10)

        list_frame = ctk.CTkFrame(outer, corner_radius=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("enabled", "type", "trigger", "output", "desc")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("enabled", text="启用")
        self.tree.heading("type", text="类型")
        self.tree.heading("trigger", text="触发")
        self.tree.heading("output", text="输出")
        self.tree.heading("desc", text="描述")
        self.tree.column("enabled", width=80, minwidth=60, anchor=tk.CENTER)
        self.tree.column("type", width=90, minwidth=70, anchor=tk.CENTER)
        self.tree.column("trigger", width=220, minwidth=120)
        self.tree.column("output", width=220, minwidth=120)
        self.tree.column("desc", width=360, minwidth=140)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(scaled(self, 12), 0), pady=scaled(self, 12))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, scaled(self, 12)), pady=scaled(self, 12))

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="编辑", command=self._edit_entry)
        self.context_menu.add_command(label="启用/禁用", command=self._toggle_enabled)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self._delete_entry)

        status_frame = ctk.CTkFrame(outer, fg_color="transparent")
        status_frame.pack(fill=tk.X)
        self.status_label = ctk.CTkLabel(status_frame, text="就绪", text_color="#71717a", font=ui_font(self, 14))
        self.status_label.pack(side=tk.LEFT, padx=2, pady=(scaled(self, 8), 0))

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        idx = 0
        for mapping in self.config.get("mappings", []):
            trigger = " + ".join(mapping.get("trigger", []))
            output = " + ".join(mapping.get("output", []))
            desc = mapping.get("description", f"{trigger} -> {output}")
            enabled = "✓" if mapping.get("enabled", True) else "✗"
            self.tree.insert("", tk.END, iid=f"k{idx}", values=(enabled, "键盘", trigger, output, desc))
            idx += 1

        idx = 0
        for mapping in self.config.get("mouse_mappings", []):
            button = mapping.get("button", "")
            output = " + ".join(mapping.get("output", []))
            desc = mapping.get("description", f"Mouse {button} -> {output}")
            enabled = "✓" if mapping.get("enabled", True) else "✗"
            self.tree.insert("", tk.END, iid=f"m{idx}", values=(enabled, "鼠标", f"Mouse {button}", output, desc))
            idx += 1

        total = len(self.config.get("mappings", [])) + len(self.config.get("mouse_mappings", []))
        self.status_label.configure(text=f"共 {total} 个映射")

    def _add_mapping(self):
        dlg = AddMappingDialog(self, "keyboard")
        self.wait_window(dlg)
        if dlg.result:
            mapping = self._mapping_from_dialog(dlg, dlg.result.get("enabled", True))
            if dlg.mapping_type == "mouse":
                self.config.setdefault("mouse_mappings", []).append(mapping)
            else:
                self.config.setdefault("mappings", []).append(mapping)
            save_config(self.config)
            self._refresh_list()
            self._restart_engine()

    def _mapping_from_dialog(self, dlg, enabled):
        if dlg.mapping_type == "mouse":
            return {
                "button": dlg.result["button"],
                "output": dlg.result["output"],
                "description": dlg.result.get("description", ""),
                "enabled": enabled,
            }
        mapping = dict(dlg.result)
        mapping["enabled"] = enabled
        return mapping

    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell" and self.tree.identify_column(event.x) == "#1":
            self._toggle_enabled()

    def _toggle_enabled(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])
        mappings = self.config.get("mappings", []) if is_keyboard else self.config.get("mouse_mappings", [])
        if idx >= len(mappings):
            return
        mapping = mappings[idx]
        mapping["enabled"] = not mapping.get("enabled", True)
        save_config(self.config)
        self._refresh_list()
        self._restart_engine()

    def _edit_entry(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个映射", parent=self)
            return

        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])

        if is_keyboard:
            mappings = self.config.get("mappings", [])
            if idx >= len(mappings):
                return
            old = mappings[idx]
            dlg = AddMappingDialog(self, "keyboard")
            dlg.type_var.set("keyboard")
            dlg._on_type_changed()
            dlg.trigger_var.set(" + ".join(old.get("trigger", [])))
            dlg.output_var.set(" + ".join(old.get("output", [])))
            dlg.desc_var.set(old.get("description", ""))
        else:
            mappings = self.config.get("mouse_mappings", [])
            if idx >= len(mappings):
                return
            old = mappings[idx]
            dlg = AddMappingDialog(self, "mouse")
            dlg.type_var.set("mouse")
            dlg._on_type_changed()
            dlg.button_var.set(old.get("button", "x1"))
            dlg.output_var.set(" + ".join(old.get("output", [])))
            dlg.desc_var.set(old.get("description", ""))

        self.wait_window(dlg)
        if dlg.result:
            old_enabled = old.get("enabled", True)
            new_mapping = self._mapping_from_dialog(dlg, old_enabled)
            keyboard_mappings = self.config.setdefault("mappings", [])
            mouse_mappings = self.config.setdefault("mouse_mappings", [])
            if dlg.mapping_type == "mouse":
                if is_keyboard:
                    del keyboard_mappings[idx]
                    mouse_mappings.append(new_mapping)
                else:
                    mouse_mappings[idx] = new_mapping
            else:
                if is_keyboard:
                    keyboard_mappings[idx] = new_mapping
                else:
                    del mouse_mappings[idx]
                    keyboard_mappings.append(new_mapping)
            save_config(self.config)
            self._refresh_list()
            self._restart_engine()

    def _delete_entry(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个映射", parent=self)
            return
        if not messagebox.askyesno("确认", "确定要删除这个映射吗？", parent=self):
            return

        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])
        mappings = self.config.get("mappings", []) if is_keyboard else self.config.get("mouse_mappings", [])
        if idx < len(mappings):
            del mappings[idx]
        save_config(self.config)
        self._refresh_list()
        self._restart_engine()

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _start_engine(self):
        self.engine.start(self.config)

    def _stop_engine(self):
        self.engine.stop()

    def _restart_engine(self):
        self.engine.stop()
        time.sleep(0.1)
        if self.running_var.get():
            self.engine.start(self.config)

    def _toggle_engine(self):
        if self.running_var.get():
            self.engine.start(self.config)
        else:
            self.engine.stop()

    def _on_close(self):
        self.withdraw()

    def _quit_app(self):
        self._stop_engine()
        self._remove_tray_icon()
        self.after(100, self.destroy)
