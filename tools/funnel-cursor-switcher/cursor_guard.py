"""Restore the registered Windows cursor if the rendering process terminates."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys

_guard = None

@contextmanager
def cursor_mutex():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateMutexW(None, False, r"Local\FunnelCursorRestoreGuard")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
    try:
        yield
    finally:
        kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)

def owner_path():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FunnelCursorSwitcher" / "cursor-guard-owner"

def start():
    global _guard
    if sys.platform != "win32" or (_guard is not None and _guard.poll() is None):
        return
    owner = owner_path()
    owner.parent.mkdir(parents=True, exist_ok=True)
    with cursor_mutex():
        owner.write_text(str(os.getpid()), encoding="ascii")
    args = [sys.executable]
    if not getattr(sys, "frozen", False):
        args.append(str(Path(__file__).with_name("FunnelCursorSwitcher.pyw")))
    args.extend(["--cursor-guard", str(os.getpid())])
    _guard = subprocess.Popen(args, creationflags=0x08000000)

def watch(parent_pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x00100000, False, parent_pid)
    if handle:
        try:
            kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
        finally:
            kernel.CloseHandle(handle)
    with cursor_mutex():
        owner = owner_path()
        try:
            if owner.read_text(encoding="ascii") != str(parent_pid):
                return
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.SystemParametersInfoW.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT)
            if not user.SystemParametersInfoW(0x0057, 0, None, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            owner.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
