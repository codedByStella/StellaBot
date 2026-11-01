"""Pointer-safe access to the Win32 APIs used by Companion."""

import ctypes
import ctypes.wintypes
import os

_user32 = None
_kernel32 = None

if os.name == "nt":
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _user32.GetForegroundWindow.argtypes = []
    _user32.GetForegroundWindow.restype = ctypes.wintypes.HWND

    _user32.GetAncestor.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.wintypes.UINT,
    ]
    _user32.GetAncestor.restype = ctypes.wintypes.HWND

    _user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int

    _user32.GetWindowTextW.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.wintypes.LPWSTR,
        ctypes.c_int,
    ]
    _user32.GetWindowTextW.restype = ctypes.c_int

    _user32.GetWindowThreadProcessId.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
    _user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD

    _user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
    _user32.IsWindowVisible.restype = ctypes.wintypes.BOOL

    _user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
    _user32.IsIconic.restype = ctypes.wintypes.BOOL

    _user32.GetClientRect.argtypes = [
        ctypes.wintypes.HWND,
        ctypes.POINTER(ctypes.wintypes.RECT),
    ]
    _user32.GetClientRect.restype = ctypes.wintypes.BOOL

    _kernel32.OpenProcess.argtypes = [
        ctypes.wintypes.DWORD,
        ctypes.wintypes.BOOL,
        ctypes.wintypes.DWORD,
    ]
    _kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE

    _kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.wintypes.HANDLE,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.LPWSTR,
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
    _kernel32.QueryFullProcessImageNameW.restype = ctypes.wintypes.BOOL

    _kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    _kernel32.CloseHandle.restype = ctypes.wintypes.BOOL

    _user32.GetLastInputInfo.restype = ctypes.wintypes.BOOL

    _kernel32.GetTickCount.argtypes = []
    _kernel32.GetTickCount.restype = ctypes.wintypes.DWORD
