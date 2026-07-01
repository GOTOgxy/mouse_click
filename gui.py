# -*- coding: utf-8 -*-

import ctypes
import ctypes.wintypes as wintypes
import queue
import tkinter as tk
from tkinter import ttk, messagebox

from engine import load_config, save_config, RemapperEngine

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
TRAY_ICON_ID = 1


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


kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE

user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.RegisterClassW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = wintypes.LPARAM

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH]
user32.FillRect.restype = ctypes.c_int

user32.CreateIconIndirect.argtypes = [ctypes.c_void_p]
user32.CreateIconIndirect.restype = wintypes.HANDLE

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH

gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetBkMode.restype = ctypes.c_int

gdi32.CreateFontW.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR]
gdi32.CreateFontW.restype = wintypes.HFONT

gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
gdi32.SetTextColor.restype = wintypes.COLORREF

gdi32.TextOutW.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
gdi32.TextOutW.restype = wintypes.BOOL

gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
gdi32.CreateBitmap.restype = wintypes.HBITMAP


class KeyCaptureDialog(tk.Toplevel):
    def __init__(self, parent, title="录制按键"):
        super().__init__(parent)
        self.title(title)
        self.geometry("350x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self._pressed = set()
        self._captured = []

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="请按下目标按键组合：", font=("", 11)).pack(pady=(0, 10))

        self.key_var = tk.StringVar(value="等待输入...")
        ttk.Label(frame, textvariable=self.key_var, font=("", 13, "bold")).pack(pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="确认", command=self._on_ok, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="清除", command=self._on_clear, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=8).pack(side=tk.LEFT, padx=5)

        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self.focus_set()

    def _on_key_release(self, event):
        name = self._normalize(event.keysym)
        self._pressed.discard(name)

    def _on_key_press(self, event):
        name = self._normalize(event.keysym)
        if name in ("ctrl", "shift", "alt", "cmd"):
            self._pressed.add(name)
            return

        combo = sorted(self._pressed | {name})
        self._captured = combo
        self.key_var.set(" + ".join(combo))

    def _normalize(self, keysym):
        mapping = {
            "control_l": "ctrl", "control_r": "ctrl",
            "shift_l": "shift", "shift_r": "shift",
            "alt_l": "alt", "alt_r": "alt",
            "super_l": "cmd", "super_r": "cmd",
        }
        return mapping.get(keysym.lower(), keysym.lower())

    def _on_clear(self):
        self._pressed.clear()
        self._captured = []
        self.key_var.set("等待输入...")

    def _on_ok(self):
        if self._captured:
            self.result = self._captured
            self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class MouseCaptureDialog(tk.Toplevel):
    def __init__(self, parent, title="录制鼠标按键"):
        super().__init__(parent)
        self.title(title)
        self.geometry("350x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self._listener = None

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="请按下鼠标按键：", font=("", 11)).pack(pady=(0, 10))

        self.key_var = tk.StringVar(value="等待输入...")
        ttk.Label(frame, textvariable=self.key_var, font=("", 13, "bold")).pack(pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="确认", command=self._on_ok, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=8).pack(side=tk.LEFT, padx=5)

        self._start_listener()

    def _start_listener(self):
        from pynput import mouse as pynput_mouse

        def on_click(x, y, button, pressed):
            if pressed:
                name = button.name
                self.after(0, lambda: self._on_detected(name))

        self._listener = pynput_mouse.Listener(on_click=on_click)
        self._listener.start()

    def _on_detected(self, name):
        self.key_var.set(name)

    def _on_ok(self):
        val = self.key_var.get()
        if val and val != "等待输入...":
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


class AddMappingDialog(tk.Toplevel):
    def __init__(self, parent, mapping_type="keyboard"):
        super().__init__(parent)
        self.title("添加映射")
        self.geometry("400x230")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.mapping_type = mapping_type

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        row_type = ttk.Frame(frame)
        row_type.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row_type, text="类型：", width=8).pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value=mapping_type)
        self.type_combo = ttk.Combobox(row_type, textvariable=self.type_var, values=["keyboard", "mouse"], state="readonly", width=15)
        self.type_combo.pack(side=tk.LEFT)
        self.type_combo.bind("<<ComboboxSelected>>", self._on_type_changed)

        self.trigger_frame = ttk.Frame(frame)
        self.trigger_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(self.trigger_frame, text="触发键：", width=8).pack(side=tk.LEFT)
        self.trigger_var = tk.StringVar(value="")
        ttk.Entry(self.trigger_frame, textvariable=self.trigger_var, state="readonly", width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(self.trigger_frame, text="录制", command=self._capture_trigger, width=6).pack(side=tk.LEFT, padx=(5, 0))

        self.mouse_frame = ttk.Frame(frame)
        self.mouse_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(self.mouse_frame, text="鼠标按键：", width=8).pack(side=tk.LEFT)
        self.button_var = tk.StringVar(value="")
        self.button_combo = ttk.Combobox(self.mouse_frame, textvariable=self.button_var, values=["left", "right", "middle", "x1", "x2"], state="readonly", width=12)
        self.button_combo.pack(side=tk.LEFT)
        ttk.Button(self.mouse_frame, text="录制", command=self._capture_mouse, width=6).pack(side=tk.LEFT, padx=(5, 0))

        row_out = ttk.Frame(frame)
        row_out.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row_out, text="输出键：", width=8).pack(side=tk.LEFT)
        self.output_var = tk.StringVar(value="")
        ttk.Entry(row_out, textvariable=self.output_var, state="readonly", width=20).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row_out, text="录制", command=self._capture_output, width=6).pack(side=tk.LEFT, padx=(5, 0))

        row_desc = ttk.Frame(frame)
        row_desc.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row_desc, text="描述：", width=8).pack(side=tk.LEFT)
        self.desc_var = tk.StringVar(value="")
        ttk.Entry(row_desc, textvariable=self.desc_var, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="确认", command=self._on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT)

        self._on_type_changed()

    def _on_type_changed(self, event=None):
        self.mapping_type = self.type_var.get()
        if self.mapping_type == "keyboard":
            self.trigger_frame.pack(fill=tk.X, pady=(0, 10))
            self.mouse_frame.pack_forget()
        else:
            self.trigger_frame.pack_forget()
            self.mouse_frame.pack(fill=tk.X, pady=(0, 10))

    def _capture_trigger(self):
        dlg = KeyCaptureDialog(self, "录制触发键")
        self.wait_window(dlg)
        if dlg.result:
            self.trigger_var.set(" + ".join(dlg.result))

    def _capture_output(self):
        dlg = KeyCaptureDialog(self, "录制输出键")
        self.wait_window(dlg)
        if dlg.result:
            self.output_var.set(" + ".join(dlg.result))

    def _capture_mouse(self):
        dlg = MouseCaptureDialog(self, "录制鼠标按键")
        self.wait_window(dlg)
        if dlg.result:
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
            "trigger": [k.strip() for k in trigger.split("+")],
            "output": [k.strip() for k in output.split("+")],
            "description": self.desc_var.get().strip() or f"{trigger if self.mapping_type == 'keyboard' else 'Mouse ' + self.button_var.get()} -> {output}",
            "enabled": True,
        }
        if self.mapping_type == "mouse":
            self.result["button"] = self.button_var.get()

        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class RemapperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("按键重映射")
        self.geometry("700x400")
        self.minsize(600, 300)

        self.config = load_config()
        self.engine = RemapperEngine()
        self._tray_queue = queue.Queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._create_tray_icon()
        self._create_ui()
        self._refresh_list()
        self._start_engine()
        self._poll_tray_queue()

    def _create_programmatic_icon(self):
        SIZE = 16
        hdc_screen = user32.GetDC(None)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbm = gdi32.CreateCompatibleBitmap(hdc_screen, SIZE, SIZE)
        gdi32.SelectObject(hdc_mem, hbm)

        hbr_bg = gdi32.CreateSolidBrush(0x003366CC)
        rect = wintypes.RECT(0, 0, SIZE, SIZE)
        user32.FillRect(hdc_mem, ctypes.byref(rect), hbr_bg)
        gdi32.DeleteObject(hbr_bg)

        gdi32.SetBkMode(hdc_mem, 1)
        hfont = gdi32.CreateFontW(12, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, "Consolas")
        old_font = gdi32.SelectObject(hdc_mem, hfont)
        gdi32.SetTextColor(hdc_mem, 0x00FFFFFF)
        gdi32.TextOutW(hdc_mem, 2, 1, "KR", 2)
        gdi32.SelectObject(hdc_mem, old_font)
        gdi32.DeleteObject(hfont)

        mask_bm = gdi32.CreateBitmap(SIZE, SIZE, 1, 1, None)
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

        h_icon = self._create_programmatic_icon()

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.tray_hwnd
        nid.uID = TRAY_ICON_ID
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = 0x0400
        nid.hIcon = h_icon
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
                elif ev == 0x0202:
                    self._show_window()
                elif ev == WM_LBUTTONDBLCLK:
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
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="添加映射", command=self._add_mapping, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="删除", command=self._delete_entry, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="编辑", command=self._edit_entry, width=8).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.running_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="运行中", variable=self.running_var, command=self._toggle_engine).pack(side=tk.LEFT, padx=2)

        ttk.Button(toolbar, text="退出", command=self._quit_app, width=8).pack(side=tk.RIGHT, padx=2)

        list_frame = ttk.Frame(self, padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("enabled", "type", "trigger", "output", "desc")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("enabled", text="启用")
        self.tree.heading("type", text="类型")
        self.tree.heading("trigger", text="触发")
        self.tree.heading("output", text="输出")
        self.tree.heading("desc", text="描述")

        self.tree.column("enabled", width=50, minwidth=40, anchor=tk.CENTER)
        self.tree.column("type", width=60, minwidth=50, anchor=tk.CENTER)
        self.tree.column("trigger", width=150, minwidth=100)
        self.tree.column("output", width=150, minwidth=100)
        self.tree.column("desc", width=200, minwidth=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="编辑", command=self._edit_entry)
        self.context_menu.add_command(label="启用/禁用", command=self._toggle_enabled)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self._delete_entry)

        status_frame = ttk.Frame(self, padding=(5, 2))
        status_frame.pack(fill=tk.X)
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        idx = 0
        for m in self.config.get("mappings", []):
            trigger = " + ".join(m.get("trigger", []))
            output = " + ".join(m.get("output", []))
            desc = m.get("description", f"{trigger} -> {output}")
            enabled = "✓" if m.get("enabled", True) else "✗"
            self.tree.insert("", tk.END, iid=f"k{idx}", values=(enabled, "键盘", trigger, output, desc))
            idx += 1

        idx = 0
        for m in self.config.get("mouse_mappings", []):
            button = m.get("button", "")
            output = " + ".join(m.get("output", []))
            desc = m.get("description", f"Mouse {button} -> {output}")
            enabled = "✓" if m.get("enabled", True) else "✗"
            self.tree.insert("", tk.END, iid=f"m{idx}", values=(enabled, "鼠标", f"Mouse {button}", output, desc))
            idx += 1

        total = len(self.config.get("mappings", [])) + len(self.config.get("mouse_mappings", []))
        self.status_label.config(text=f"共 {total} 个映射")

    def _add_mapping(self):
        dlg = AddMappingDialog(self, "keyboard")
        self.wait_window(dlg)
        if dlg.result:
            if dlg.mapping_type == "mouse":
                mapping = {
                    "button": dlg.result["button"],
                    "output": dlg.result["output"],
                    "description": dlg.result.get("description", ""),
                    "enabled": dlg.result.get("enabled", True),
                }
                self.config.setdefault("mouse_mappings", []).append(mapping)
            else:
                self.config.setdefault("mappings", []).append(dlg.result)
            save_config(self.config)
            self._refresh_list()
            self._restart_engine()

    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#1":
                self._toggle_enabled()

    def _toggle_enabled(self):
        sel = self.tree.selection()
        if not sel:
            return

        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])

        if is_keyboard:
            mappings = self.config.get("mappings", [])
            if idx >= len(mappings):
                return
            m = mappings[idx]
        else:
            mappings = self.config.get("mouse_mappings", [])
            if idx >= len(mappings):
                return
            m = mappings[idx]

        m["enabled"] = not m.get("enabled", True)
        save_config(self.config)
        self._refresh_list()
        self._restart_engine()

    def _edit_entry(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个映射")
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
            if dlg.mapping_type == "mouse":
                self.config["mouse_mappings"][idx] = {
                    "button": dlg.result["button"],
                    "output": dlg.result["output"],
                    "description": dlg.result.get("description", ""),
                    "enabled": dlg.result.get("enabled", True),
                }
            else:
                self.config["mappings"][idx] = dlg.result
            save_config(self.config)
            self._refresh_list()
            self._restart_engine()

    def _delete_entry(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个映射")
            return

        if not messagebox.askyesno("确认", "确定要删除这个映射吗？"):
            return

        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])

        if is_keyboard:
            mappings = self.config.get("mappings", [])
            if idx < len(mappings):
                del mappings[idx]
        else:
            mappings = self.config.get("mouse_mappings", [])
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
        import time
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
