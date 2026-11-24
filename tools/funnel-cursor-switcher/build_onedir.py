from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

from equipment_catalog import ACTIVE_EQUIPMENT


ROOT = Path(__file__).resolve().parent
NAME = "FunnelCursorSwitcher"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def copy_runtime_assets(bundle):
    for key in sorted(ACTIVE_EQUIPMENT):
        cursor = ROOT / "カーソル" / key
        flight = ROOT / "飛行アニメ" / key
        sources = [cursor.with_suffix(".cur"), cursor.with_suffix(".png"), flight.with_suffix(".png")]
        for sheet in flight.parent.glob(f"{flight.name}.*.png"):
            if not sheet.stem.endswith("原画"):
                sources.append(sheet)
        for source in sources:
            destination = bundle / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def main():
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("Build with 64-bit Python on Windows.")

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--onedir", "--windowed",
            "--hidden-import", "numpy", "--clean", "--noconfirm", "--name", NAME, f"{NAME}.pyw",
        ],
        cwd=ROOT,
        check=True,
    )

    dist = ROOT / "dist"
    bundle = dist / NAME
    with ZipFile(ROOT / "runtime58.zip") as runtime:
        runtime.extractall(bundle / "_internal" / "trial58")
    with ZipFile(ROOT / "runtime77.zip") as runtime:
        runtime.extractall(bundle / "_internal/fin77")
    copy_runtime_assets(bundle)
    for name in ("VERSION", "README.md"):
        shutil.copy2(ROOT / name, bundle / name)
    archive = shutil.make_archive(
        str(dist / f"{NAME}-v{VERSION}-windows-x64"), "zip", root_dir=dist, base_dir=NAME
    )
    # Keep the existing release workflow and old download name compatible.
    shutil.copy2(archive, dist / f"{NAME}-windows-x64.zip")
    print(archive)


if __name__ == "__main__":
    main()
