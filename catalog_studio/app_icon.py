"""Shared application artwork for source and PyInstaller launches."""
from pathlib import Path
import sys

from PIL import Image, ImageTk


def asset_path(name):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return root / 'assets' / name


def install(window):
    """Keep Tk image references alive for the window and header."""
    with Image.open(asset_path('catalog-studio.png')) as source:
        window.app_icon_images = tuple(
            ImageTk.PhotoImage(source.resize((size, size), Image.Resampling.LANCZOS), master=window)
            for size in (16, 32, 48, 64, 128, 256)
        )
        window.app_header_icon = ImageTk.PhotoImage(
            source.resize((34, 34), Image.Resampling.LANCZOS), master=window)
    window.iconphoto(True, *window.app_icon_images)
