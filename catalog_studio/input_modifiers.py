"""Read physical Windows modifiers without relying on Tk's motion flags."""
import sys


def physical_alt_down():
    if sys.platform!='win32':return None
    import ctypes
    try:
        query=ctypes.WinDLL('user32',use_last_error=True).GetAsyncKeyState
        query.argtypes=[ctypes.c_int];query.restype=ctypes.c_short
        return bool(query(0x12)&0x8000)
    except (AttributeError,OSError):return None
