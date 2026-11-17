"""Version of the running source or bundled application."""
from pathlib import Path
import sys


def application_title():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
    try:version=(root/'VERSION').read_text(encoding='utf-8').strip()
    except OSError:version='不明'
    return 'Catalog Studio ver'+version
