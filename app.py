# -*- coding: utf-8 -*-

import ctypes
import ctypes.wintypes as wintypes
import sys

ERROR_ALREADY_EXISTS = 183


def main():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    mutex = kernel32.CreateMutexW(None, False, "Global\\MouseRemapper")
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        print("按键重映射已在运行。")
        return

    from gui import RemapperApp
    app = RemapperApp()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
